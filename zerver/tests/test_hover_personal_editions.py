from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID

from typing_extensions import override

from hover.clawer_sync import ClawerSyncError, InMemoryClawerSync
from hover.models import (
    ConnectedAccount,
    GeneratedItem,
    PersonalEdition,
    Source,
    SourceParticipantBinding,
    Space,
    SpaceAttachment,
    SpaceMembership,
    Todo,
)
from hover.publication_contracts import ClawerPublication, ClawerPublicationPage
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class HoverPersonalEditionsTest(ZulipTestCase):
    SOURCE_REF = "src_0123456789abcdef0123456789abcdef"
    EDITION_SOURCE_REF = "src_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    TEAMMATE_REF = "person_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.realm = self.user.realm
        self.realm.hover_enabled = True
        self.realm.save(update_fields=["hover_enabled"])
        category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        stream = self.subscribe(self.user, "AIMTO Events", invite_only=True)
        self.space = Space.objects.create(
            realm=self.realm,
            name="AIMTO Events",
            category=category,
            created_by=self.user,
            state=Space.State.LAUNCHED,
            stream=stream,
        )
        self.membership = SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=self.user,
            role=SpaceMembership.Role.CONTRIBUTOR,
            added_by=self.user,
        )
        self.account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
            display_name="AIMTO conversations",
            owner=self.user,
            created_by=self.user,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        self.source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="whatsapp",
            provider_key="whatsapp",
            provider_name="WhatsApp",
            source_type="group",
            external_ref=self.SOURCE_REF,
            display_name="Venue team",
        )
        self.attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=self.source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.CUSTOM,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            custom_start_date=date(2026, 8, 1),
            attached_by=self.user,
        )
        SourceParticipantBinding.objects.create(
            realm=self.realm,
            source=self.source,
            participant_ref=self.TEAMMATE_REF,
            user=self.user,
            match_basis=SourceParticipantBinding.MatchBasis.VERIFIED_EMAIL,
            observation_basis="obs_0123456789abcdef0123456789abcdef",
        )
        assistant = self.create_test_bot(
            "hover-edition-assistant", self.user, full_name="Hover Assistant"
        )
        self.subscribe(assistant, stream.name, invite_only=True)
        message_id = self.send_stream_message(
            assistant,
            stream.name,
            "Venue access was confirmed for Friday.",
            "Venue readiness",
        )
        GeneratedItem.objects.create(
            realm=self.realm,
            message=Message.objects.get(id=message_id),
            attachment=self.attachment,
            publication_id="update-1",
            idempotency_key="update-identity-1",
            output_type=GeneratedItem.OutputType.PROGRESS_UPDATE,
            module_key="progress_tracker",
            module_name="Progress Tracker",
            module_version="v1",
            source_summary="From Venue team",
        )
        self.adapter = InMemoryClawerSync()
        self.login_user(self.user)

    def publication(
        self, *, edition: str = "morning", include_missing: bool = False
    ) -> ClawerPublication:
        timestamp = "2026-08-11T10:00:00Z"
        references = ["update-1", "missing-update"] if include_missing else ["update-1"]
        item = {
            "title": "The venue handoff is ready",
            "detail": "Start with the confirmed access plan, then share the arrival window.",
            "operational_publication_ids": references,
            "confirmed_todo_refs": ["todo-confirmed-1"],
        }
        personal: dict[str, object] = {
            "edition": edition,
            "teammate_ref": self.TEAMMATE_REF,
            "teammate_display_name": "Hamlet",
            "morning": None,
            "end_of_day": None,
            "operational_publication_ids": references,
            "confirmed_todo_refs": ["todo-confirmed-1"],
        }
        if edition == "morning":
            personal["morning"] = {
                "urgency": [item],
                "unresolved_carryover": [],
                "guidance": [],
                "all_clear_context": ["The remaining confirmed work is moving well."],
            }
            producer_key = "personal_morning_brief"
        else:
            personal["end_of_day"] = {
                "meaningful_movement": [item],
                "completed_work": [],
                "carryover": [],
                "delegated_dependencies": [],
                "tomorrow_preview": [],
            }
            producer_key = "personal_eod_roundup"
        return ClawerPublication.model_validate(
            {
                "publication_id": f"personal-{edition}",
                "idempotency_key": f"personal-identity-{edition}",
                "business_identity": f"personal-business-{edition}",
                "contract": "digest",
                "schema_version": "1.0",
                "producer_key": producer_key,
                "producer_name": "Personal Daily Brief",
                "producing_version": "prompt:personal:v1",
                "run_reference": f"run-{edition}",
                "source_ref": self.EDITION_SOURCE_REF,
                "covered_period": {"start": "2026-08-11T00:00:00Z", "end": timestamp},
                "payload": {
                    "contract": "digest",
                    "schema_version": "1.0",
                    "title": "A good place to start"
                    if edition == "morning"
                    else "Your day in motion",
                    "timezone": "UTC",
                    "operation": "Private generation context that must not render.",
                    "marketing": "Private marketing context that must not render.",
                    "metrics": {"messages": 1, "text": 1, "media": 0, "voice": 0},
                    "generation_context": "personal edition",
                    "personal": personal,
                },
                "evidence_refs": [],
                "disputed_details": [],
                "importance": "normal",
                "occurred_at": timestamp,
                "generated_at": timestamp,
                "published_at": timestamp,
                "lineage_key": None,
                "parent_publication_id": None,
                "material_change": False,
            }
        )

    def set_page(self, *publications: ClawerPublication) -> None:
        self.adapter.personal_edition_pages[
            (
                str(self.realm.uuid),
                str(self.account.external_account_id),
                self.TEAMMATE_REF,
                None,
            )
        ] = ClawerPublicationPage(
            publications=list(publications), next_cursor="hpe1:next", has_more=False
        )

    def get_editions(self) -> "TestHttpResponse":
        with patch("hover.views_personal_editions.get_clawer_sync", return_value=self.adapter):
            return self.client_get("/json/hover/personal-editions")

    def test_ingests_and_projects_only_native_update_links_without_creating_todos(self) -> None:
        self.set_page(self.publication())
        todo_count = Todo.objects.count()

        response = self.get_editions()
        payload = self.assert_json_success(response)

        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(payload["sync_status"], "current")
        morning = payload["editions"]["morning"]
        self.assertEqual(morning["title"], "A good place to start")
        self.assertEqual(morning["sections"]["urgency"][0]["update"]["space_name"], "AIMTO Events")
        self.assertIn("/near/", morning["sections"]["urgency"][0]["update"]["url"])
        self.assertNotIn("operation", morning)
        self.assertNotIn("marketing", morning)
        self.assertNotIn("confirmed_todo_refs", morning["sections"]["urgency"][0])
        self.assertEqual(Todo.objects.count(), todo_count)
        self.assertEqual(PersonalEdition.objects.count(), 1)
        self.assertEqual(
            self.adapter.personal_edition_sync_calls[0]["teammate_ref"], self.TEAMMATE_REF
        )

    def test_omits_passage_when_any_native_update_is_not_authorized(self) -> None:
        self.set_page(self.publication(include_missing=True))
        payload = self.assert_json_success(self.get_editions())
        self.assertEqual(payload["editions"]["morning"]["sections"]["urgency"], [])
        self.assertFalse(payload["editions"]["morning"]["all_clear"])

    def test_removing_confirmed_membership_hides_the_edition_and_stops_sync(self) -> None:
        self.set_page(self.publication())
        self.assert_json_success(self.get_editions())
        self.membership.delete()
        self.adapter.personal_edition_sync_calls.clear()

        payload = self.assert_json_success(self.get_editions())

        self.assertEqual(payload["sync_status"], "empty")
        self.assertIsNone(payload["editions"]["morning"])
        self.assertEqual(self.adapter.personal_edition_sync_calls, [])

    def test_cached_edition_survives_retryable_sync_failure(self) -> None:
        self.set_page(self.publication(edition="end_of_day"))
        self.assert_json_success(self.get_editions())
        error = ClawerSyncError(
            error_code="clawer_unavailable",
            operation="personal_edition_sync",
            http_status_code=503,
            retryable=True,
        )
        with patch.object(self.adapter, "sync_personal_editions", side_effect=error):
            response = self.get_editions()
        payload = self.assert_json_success(response)
        self.assertEqual(payload["sync_status"], "degraded")
        self.assertEqual(
            list(payload["editions"]["end_of_day"]["sections"]),
            [
                "meaningful_movement",
                "completed_work",
                "carryover",
                "delegated_dependencies",
                "tomorrow_preview",
            ],
        )
