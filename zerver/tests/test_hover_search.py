from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import UUID

import orjson
from django.db import connection
from typing_extensions import override

from hover.clawer_sync import ClawerSyncError, InMemoryClawerSync
from hover.models import (
    ConnectedAccount,
    GeneratedItem,
    IntegrationMessageProvenance,
    IntegrationRouteAssociation,
    Source,
    Space,
    SpaceAttachment,
    SpaceMembership,
)
from hover.source_record_contracts import ClawerSourceRecordPage
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.message_flags import do_update_message_flags
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message
from zerver.models.users import UserProfile

SOURCE_REF = "src_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def search_page() -> ClawerSourceRecordPage:
    return ClawerSourceRecordPage.model_validate(
        {
            "schema_version": "1.0",
            "records": [
                {
                    "record_ref": "record_11111111111111111111111111111111",
                    "source_ref": SOURCE_REF,
                    "sender": {
                        "ref": "person_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                        "display_name": "Alex",
                    },
                    "timestamp": "2026-08-10T08:30:00Z",
                    "content": {
                        "text": "The venue handoff is confirmed.",
                        "voice_transcript": None,
                        "media_description": None,
                    },
                    "media": None,
                    "reply_context": None,
                }
            ],
            "next_cursor": "",
            "has_more": False,
        }
    )


class HoverSearchTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.member = self.example_user("hamlet")
        self.other = self.example_user("othello")
        self.realm = self.member.realm
        self.realm.hover_enabled = True
        self.realm.save(update_fields=["hover_enabled"])
        category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        stream = self.subscribe(self.member, "Searchable Space", invite_only=True)
        self.subscribe(self.other, stream.name, invite_only=True)
        self.space = Space.objects.create(
            realm=self.realm,
            name="Searchable Space",
            category=category,
            created_by=self.member,
            state=Space.State.LAUNCHED,
            stream=stream,
        )
        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=self.member,
            role=SpaceMembership.Role.CONTRIBUTOR,
            added_by=self.member,
        )
        self.account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
            display_name="AIMTO conversations",
            owner=self.member,
            created_by=self.member,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        self.source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="whatsapp",
            provider_key="whatsapp",
            provider_name="WhatsApp",
            source_type="group",
            external_ref=SOURCE_REF,
            display_name="Venue team",
        )
        self.attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=self.source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.CUSTOM,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
            custom_start_date=date(2026, 8, 10),
            attached_by=self.member,
        )
        self.human_message_id = self.send_stream_message(
            self.member,
            stream.name,
            "Venue handoff notes from the working session.",
            "Event plan",
        )
        assistant = self.create_test_bot(
            "hover-search-assistant", self.member, full_name="Hover Assistant"
        )
        self.subscribe(assistant, stream.name, invite_only=True)
        generated_message_id = self.send_stream_message(
            assistant,
            stream.name,
            "Venue handoff is ready for the team.",
            "Progress",
        )
        GeneratedItem.objects.create(
            realm=self.realm,
            message=Message.objects.get(id=generated_message_id),
            attachment=self.attachment,
            output_type=GeneratedItem.OutputType.PROGRESS_UPDATE,
            module_key="progress_tracker",
            module_name="Progress Tracker",
            module_version="v1",
            source_summary="Venue team",
        )
        do_update_message_flags(self.member, "add", "starred", [generated_message_id])

        unrelated_stream = self.subscribe(self.member, "Unrelated private", invite_only=True)
        self.send_stream_message(
            self.member, unrelated_stream.name, "Venue handoff must stay out.", "Private"
        )
        integration_bot = self.create_test_bot(
            "search-source",
            self.member,
            full_name="Source integration",
            bot_type=UserProfile.INCOMING_WEBHOOK_BOT,
        )
        self.subscribe(integration_bot, stream.name, invite_only=True)
        raw_message_id = self.send_stream_message(
            integration_bot,
            stream.name,
            "Venue handoff raw integration evidence.",
            "Source events",
        )
        route = IntegrationRouteAssociation.objects.create(
            realm=self.realm,
            attachment=self.attachment,
            bot=integration_bot,
            stream=stream,
            configured_by=self.member,
        )
        IntegrationMessageProvenance.objects.create(
            message_id=raw_message_id,
            realm=self.realm,
            association=route,
            attachment=self.attachment,
            source=self.source,
            provider_key=self.source.provider_key,
            provider_name=self.source.provider_name,
            source_type=self.source.source_type,
            display_name=self.source.display_name,
            external_url="",
        )
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE zerver_message SET
                search_tsvector =
                    to_tsvector('zulip.english_us_search', subject || rendered_content),
                search_pgroonga = escape_html(subject) || ' ' || rendered_content
                """
            )

        self.adapter = InMemoryClawerSync()
        self.adapter.source_record_pages[
            (
                str(self.realm.uuid),
                str(self.account.external_account_id),
                SOURCE_REF,
                None,
                "venue handoff",
            )
        ] = search_page()
        self.login_user(self.member)

    def search(self, query: str = "venue handoff"):
        return self.client_post("/json/hover/search", {"query": orjson.dumps(query).decode()})

    def test_search_prioritizes_native_knowledge_and_labels_source_evidence(self) -> None:
        with patch("hover.views_search.get_clawer_sync", return_value=self.adapter):
            response = self.search()
        payload = self.assert_json_success(response)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            [result["kind"] for result in payload["knowledge"]], ["generated", "human"]
        )
        self.assertEqual(payload["knowledge"][0]["module_name"], "Progress Tracker")
        self.assertTrue(payload["knowledge"][0]["saved"])
        self.assertTrue(payload["knowledge"][0]["saveable"])
        self.assertIn(
            f"/near/{payload['knowledge'][0]['message_id']}", payload["knowledge"][0]["url"]
        )
        self.assertEqual(payload["sources"][0]["kind"], "source")
        self.assertFalse(payload["sources"][0]["saveable"])
        self.assertNotIn("message_id", payload["sources"][0])
        serialized = orjson.dumps(payload).decode()
        self.assertNotIn(SOURCE_REF, serialized)
        self.assertNotIn("must stay out", serialized)
        self.assertNotIn("raw integration evidence", serialized)

    def test_membership_revocation_during_source_search_removes_every_result(self) -> None:
        original = self.adapter.browse_source_records

        def revoke(**kwargs: object) -> ClawerSourceRecordPage:
            SpaceMembership.objects.filter(space=self.space, user=self.member).delete()
            return original(**kwargs)  # type: ignore[arg-type]

        self.adapter.browse_source_records = revoke  # type: ignore[method-assign]
        with patch("hover.views_search.get_clawer_sync", return_value=self.adapter):
            payload = self.assert_json_success(self.search())
        self.assertEqual(payload["knowledge"], [])
        self.assertEqual(payload["sources"], [])

    def test_saved_state_is_private_to_the_current_teammate(self) -> None:
        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=self.other,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.member,
        )
        self.login_user(self.other)
        with patch("hover.views_search.get_clawer_sync", return_value=self.adapter):
            payload = self.assert_json_success(self.search())
        self.assert_length(payload["knowledge"], 2)
        self.assertFalse(payload["knowledge"][0]["saved"])

    def test_source_failure_keeps_native_results_and_reports_partial_state(self) -> None:
        def unavailable(**_kwargs: object) -> ClawerSourceRecordPage:
            raise ClawerSyncError(
                error_code="clawer_unavailable",
                operation="source_records",
                http_status_code=503,
                retryable=True,
            )

        self.adapter.browse_source_records = unavailable  # type: ignore[method-assign]
        with patch("hover.views_search.get_clawer_sync", return_value=self.adapter):
            payload = self.assert_json_success(self.search())
        self.assert_length(payload["knowledge"], 2)
        self.assertEqual(payload["sources"], [])
        self.assertEqual(payload["source_unavailable_count"], 1)

    def test_nonmember_guest_and_inactive_user_search_nothing(self) -> None:
        self.login_user(self.other)
        with patch("hover.views_search.get_clawer_sync", return_value=self.adapter):
            other_payload = self.assert_json_success(self.search())
        self.assertEqual(other_payload["knowledge"], [])
        self.assertEqual(other_payload["sources"], [])
        self.assertEqual(self.adapter.source_record_calls, [])

        guest = self.example_user("polonius")
        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=guest,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.member,
        )
        self.login_user(guest)
        with patch("hover.views_search.get_clawer_sync", return_value=self.adapter):
            guest_payload = self.assert_json_success(self.search())
        self.assertEqual(guest_payload["knowledge"], [])
        self.assertEqual(guest_payload["sources"], [])
        self.assertEqual(self.adapter.source_record_calls, [])

        self.member.is_active = False
        self.member.save(update_fields=["is_active"])
        # The library check is also used by event-driven callers after login
        # state has been established, so exercise it without a second login.
        from hover.lib_search import search_hover_knowledge

        inactive = search_hover_knowledge(
            user_profile=self.member,
            query="venue handoff",
            clawer_sync=self.adapter,
        )
        self.assertEqual(inactive["knowledge"], [])
        self.assertEqual(inactive["sources"], [])

    def test_empty_and_too_long_queries_are_bounded(self) -> None:
        with patch("hover.views_search.get_clawer_sync", return_value=self.adapter):
            empty = self.assert_json_success(self.search("   "))
        self.assertEqual(empty["query"], "")
        self.assertEqual(self.adapter.source_record_calls, [])
        too_long = self.search("x" * 101)
        self.assertEqual(too_long.status_code, 400)
