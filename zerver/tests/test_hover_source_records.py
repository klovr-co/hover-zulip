import hashlib
from collections.abc import Callable
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import UUID

import orjson
from typing_extensions import override

from hover.clawer_sync import ClawerSyncError, InMemoryClawerSync, StudioClawerSync
from hover.lib_spaces import get_space_data
from hover.models import (
    ConnectedAccount,
    EvidenceLink,
    GeneratedItem,
    Source,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
)
from hover.source_record_contracts import ClawerSourceRecordPage
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, UserMessage

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

SOURCE_REF = "src_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SOURCE_RECORD_FIXTURE = Path(__file__).parent / "fixtures" / "hover" / "source_records_v1.json"


def capture_hover_telemetry(
    test_method: Callable[["HoverSourceRecordsTest"], None],
) -> Callable[["HoverSourceRecordsTest"], None]:
    @wraps(test_method)
    def wrapped(self: "HoverSourceRecordsTest") -> None:
        with self.assertLogs("zulip.hover.telemetry", level="INFO") as telemetry:
            test_method(self)
        for line in telemetry.output:
            self.assertRegex(
                line,
                (
                    r"^INFO:zulip\.hover\.telemetry:Hover telemetry "
                    r"event=source_records outcome=[a-z_]+"
                    r"(?: [a-z_]+=(?:[a-z0-9_]+|[0-9]+|true|false))*$"
                ),
            )

    return wrapped


def source_record_page(*, has_more: bool = True) -> ClawerSourceRecordPage:
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
                    "timestamp": "2026-08-10T00:00:00Z",
                    "content": {
                        "text": "<b>plain text</b>",
                        "voice_transcript": None,
                        "media_description": None,
                    },
                    "media": None,
                    "reply_context": None,
                },
                {
                    "record_ref": "record_22222222222222222222222222222222",
                    "source_ref": SOURCE_REF,
                    "sender": {
                        "ref": "person_cccccccccccccccccccccccccccccccc",
                        "display_name": "Sam",
                    },
                    "timestamp": "2026-08-10T08:30:00Z",
                    "content": {
                        "text": None,
                        "voice_transcript": "Voice update",
                        "media_description": "Voice note",
                    },
                    "media": {
                        "type": "audio",
                        "mime_type": "audio/ogg",
                        "byte_size": 2048,
                        "available": False,
                    },
                    "reply_context": {
                        "record_ref": "record_11111111111111111111111111111111",
                        "sender_display_name": "Alex",
                        "timestamp": "2026-08-10T00:00:00Z",
                        "excerpt": "plain text",
                    },
                },
            ],
            "next_cursor": "hr1.older" if has_more else "",
            "has_more": has_more,
        }
    )


class HoverSourceRecordsTest(ZulipTestCase):
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
        stream, _ = create_stream_if_needed(self.realm, "Record history", invite_only=True)
        self.space = Space.objects.create(
            realm=self.realm,
            name="Record history",
            category=category,
            created_by=self.member,
            state=Space.State.LAUNCHED,
            stream=stream,
        )
        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=self.member,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.member,
        )
        self.account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
            display_name="Founder conversations",
            owner=self.member,
            created_by=self.member,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        self.source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="whatsapp",
            provider_key="whatsapp",
            source_type="group",
            external_ref=SOURCE_REF,
            display_name="Leadership group",
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
        self.url = f"/json/hover/spaces/{self.space.id}/sources/{self.attachment.id}/records/browse"
        self.adapter = InMemoryClawerSync()
        self.adapter.source_record_pages[
            (str(self.realm.uuid), str(self.account.external_account_id), SOURCE_REF, None, None)
        ] = source_record_page()
        self.login_user(self.member)

    def post(self, **overrides: object) -> "TestHttpResponse":
        data: dict[str, object] = {"limit": 20, "query": ""}
        data.update(overrides)
        return self.client_post(
            self.url, {key: orjson.dumps(value).decode() for key, value in data.items()}
        )

    @capture_hover_telemetry
    def test_authorized_browse_is_sanitized_read_only_and_cursor_bound(self) -> None:
        message_count = Message.objects.count()
        user_message_count = UserMessage.objects.count()
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            response = self.post()
        payload = self.assert_json_success(response)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertTrue(payload["has_more"])
        self.assertEqual(payload["records"][0]["sender_display_name"], "Alex")
        self.assertEqual(payload["records"][1]["media"]["mime_type"], "audio/ogg")
        self.assertEqual(payload["records"][1]["reply_context"]["excerpt"], "plain text")
        serialized = orjson.dumps(payload).decode()
        self.assertNotIn(SOURCE_REF, serialized)
        self.assertNotIn("person_", serialized)
        self.assertEqual(Message.objects.count(), message_count)
        self.assertEqual(UserMessage.objects.count(), user_message_count)

        cursor = payload["next_cursor"]
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            changed_query = self.post(cursor=cursor, query="different")
        self.assert_json_error(changed_query, "Invalid Source record cursor.")

    @capture_hover_telemetry
    def test_denials_are_uniform_and_do_not_call_studio(self) -> None:
        self.login_user(self.other)
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            denied = self.post()
        self.assertEqual(denied.status_code, 404)
        self.assert_json_error(denied, "Source not found.", status_code=404)
        self.assertEqual(self.adapter.source_record_calls, [])

        outsider = self.lear_user("cordelia")
        self.login_user(outsider)
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            cross_organization = self.client_post(
                self.url,
                {"limit": orjson.dumps(20).decode(), "query": orjson.dumps("").decode()},
                subdomain="lear",
            )
        self.assertEqual(cross_organization.status_code, 404)
        self.assert_json_error(cross_organization, "Source not found.", status_code=404)
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
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            guest_denied = self.post()
        self.assertEqual(guest_denied.status_code, 404)
        self.assert_json_error(guest_denied, "Source not found.", status_code=404)
        self.assertEqual(self.adapter.source_record_calls, [])

        self.login_user(self.member)
        self.attachment.state = SpaceAttachment.State.PENDING_SYNC
        self.attachment.save(update_fields=["state"])
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            pending = self.post()
        self.assertEqual(pending.status_code, 404)
        self.assert_json_error(pending, "Source not found.", status_code=404)
        self.assertEqual(self.adapter.source_record_calls, [])

    @capture_hover_telemetry
    def test_detached_history_remains_browseable(self) -> None:
        self.attachment.state = SpaceAttachment.State.DETACHED
        self.attachment.detached_at = datetime(2026, 8, 11, tzinfo=timezone.utc)
        self.attachment.detached_by = self.member
        self.attachment.save(update_fields=["state", "detached_at", "detached_by"])
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            payload = self.assert_json_success(self.post())
        self.assertEqual(payload["source"]["state"], "detached")
        projected = get_space_data(self.space)["attachments"][0]
        self.assertEqual(projected["state"], "detached")
        self.assertTrue(projected["can_browse_records"])

    def test_retryable_failure_telemetry_uses_fixed_class_without_request_details(self) -> None:
        private_request_sentinel = "PRIVATE_UPSTREAM_REQUEST_SENTINEL"
        error = ClawerSyncError(
            error_code="clawer_unavailable",
            operation="source_records",
            http_status_code=503,
            retryable=True,
            upstream_request_id=private_request_sentinel,
        )
        with (
            patch.object(self.adapter, "browse_source_records", side_effect=error),
            patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter),
            self.assertLogs("zulip.hover.telemetry", level="INFO") as telemetry,
            self.assertLogs("django.request", level="ERROR") as request_logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.post()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            request_logs.output,
            [f"ERROR:django.request:Service Unavailable: {self.url}"],
        )
        joined = "\n".join(telemetry.output)
        self.assertIn("event=source_records outcome=retryable_failure", joined)
        self.assertNotIn(private_request_sentinel, joined)

    @capture_hover_telemetry
    def test_permanent_evidence_deletion_is_separate_confirmed_org_admin_action(self) -> None:
        assert self.space.stream is not None
        self.subscribe(self.member, self.space.stream.name, invite_only=True)
        message_id = self.send_stream_message(
            self.member,
            self.space.stream.name,
            "Generated post retained after evidence deletion.",
            "Evidence",
        )
        item = GeneratedItem.objects.create(
            realm=self.realm,
            message=Message.objects.get(id=message_id),
            attachment=self.attachment,
            output_type=GeneratedItem.OutputType.FEED_UPDATE,
            module_key="activity_digest",
            module_name="Activity Digest",
            module_version="v1",
            source_summary="Leadership group",
        )
        EvidenceLink.objects.create(
            generated_item=item,
            realm=self.realm,
            source=self.source,
            evidence_ref="record_11111111111111111111111111111111",
            position=0,
            provider_key=self.source.provider_key,
            provider_name=self.source.provider_name,
            display_name=self.source.display_name,
        )
        self.attachment.state = SpaceAttachment.State.DETACHED
        self.attachment.detached_at = datetime(2026, 8, 11, tzinfo=timezone.utc)
        self.attachment.detached_by = self.member
        self.attachment.save(update_fields=["state", "detached_at", "detached_by"])
        SpaceAdministrator.objects.create(
            realm=self.realm,
            space=self.space,
            user=self.member,
            added_by=self.member,
        )
        delete_url = f"/json/hover/spaces/{self.space.id}/sources/{self.attachment.id}/evidence"
        confirmation = f"DELETE {self.source.display_name}"

        denied = self.client_delete(
            delete_url, {"confirmation": orjson.dumps(confirmation).decode()}
        )
        self.assert_json_error(
            denied, "Only an Organization Admin may permanently delete evidence."
        )
        self.assertTrue(EvidenceLink.objects.filter(generated_item=item).exists())

        realm_admin = self.example_user("iago")
        self.login_user(realm_admin)
        wrong = self.client_delete(
            delete_url, {"confirmation": orjson.dumps("DELETE wrong").decode()}
        )
        self.assert_json_error(wrong, "Evidence deletion confirmation did not match.")
        deleted = self.assert_json_success(
            self.client_delete(delete_url, {"confirmation": orjson.dumps(confirmation).decode()})
        )
        self.assertTrue(deleted["changed"])
        self.assertEqual(deleted["deleted_evidence_link_count"], 1)
        self.assertFalse(EvidenceLink.objects.filter(generated_item=item).exists())
        self.assertTrue(GeneratedItem.objects.filter(id=item.id).exists())
        self.assertTrue(Message.objects.filter(id=message_id, sender=self.member).exists())
        self.attachment.refresh_from_db()
        self.assertIsNotNone(self.attachment.evidence_deleted_at)
        projected = get_space_data(self.space)["attachments"][0]
        self.assertEqual(projected["state"], "detached")
        self.assertTrue(projected["evidence_deleted"])
        self.assertFalse(projected["can_browse_records"])

        replay = self.assert_json_success(
            self.client_delete(delete_url, {"confirmation": orjson.dumps(confirmation).decode()})
        )
        self.assertFalse(replay["changed"])
        self.login_user(self.member)
        with patch("hover.views_source_records.get_clawer_sync", return_value=self.adapter):
            denied_browse = self.post()
        self.assertEqual(denied_browse.status_code, 404)
        self.assert_json_error(denied_browse, "Source not found.", status_code=404)

    @capture_hover_telemetry
    def test_membership_revocation_during_remote_call_fails_closed(self) -> None:
        adapter = self.adapter
        original = adapter.browse_source_records

        def revoke(**kwargs: object) -> ClawerSourceRecordPage:
            SpaceMembership.objects.filter(space=self.space, user=self.member).delete()
            return original(**kwargs)  # type: ignore[arg-type]

        adapter.browse_source_records = revoke  # type: ignore[method-assign]
        with patch("hover.views_source_records.get_clawer_sync", return_value=adapter):
            response = self.post()
        self.assertEqual(response.status_code, 404)
        self.assert_json_error(response, "Source not found.", status_code=404)


class StudioSourceRecordsContractTest(ZulipTestCase):
    def test_studio_adapter_uses_fixed_route_and_rejects_private_fields(self) -> None:
        realm_uuid = UUID("28fe59d4-03e8-476f-9bb8-31c55c9cbdcb")
        account_uuid = UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03")
        fixture_bytes = SOURCE_RECORD_FIXTURE.read_bytes()
        expected_checksum = Path(f"{SOURCE_RECORD_FIXTURE}.sha256").read_text().strip()
        self.assertEqual(hashlib.sha256(fixture_bytes).hexdigest(), expected_checksum)
        valid = orjson.loads(fixture_bytes)["response"]
        response = MagicMock()
        response.ok = True
        response.content = orjson.dumps(valid)
        response.headers = {"X-Request-Id": "1851666d-6f29-4801-a72f-ee43ab96dd79"}
        response.json.return_value = valid
        session = MagicMock()
        session.post.return_value = response
        adapter = StudioClawerSync(
            base_url="https://studio.example.test",
            credentials={str(realm_uuid): "hvr_srv_" + "a" * 32},
            session=session,
        )
        page = adapter.browse_source_records(
            realm_uuid=realm_uuid,
            account_external_id=account_uuid,
            source_ref=SOURCE_REF,
            start_at="2026-08-10T00:00:00+00:00",
            cursor=None,
            limit=20,
            query="venue",
        )
        self.assert_length(page.records, 5)
        session.post.assert_called_once_with(
            f"https://studio.example.test/api/hover/v1/connected-accounts/{account_uuid}/records/browse",
            json={
                "source_ref": SOURCE_REF,
                "start_at": "2026-08-10T00:00:00+00:00",
                "limit": 20,
                "query": "venue",
            },
            headers={
                "Accept": "application/json",
                "Authorization": "Bearer hvr_srv_" + "a" * 32,
                "Content-Type": "application/json",
            },
        )

        invalid = source_record_page().model_dump(mode="json")
        invalid["records"][0]["sender_phone"] = "+60000000000"
        response.json.return_value = invalid
        with self.assertRaises(ClawerSyncError) as raised:
            adapter.browse_source_records(
                realm_uuid=realm_uuid,
                account_external_id=account_uuid,
                source_ref=SOURCE_REF,
                start_at="2026-08-10T00:00:00+00:00",
                cursor=None,
                limit=20,
                query=None,
            )
        self.assertEqual(raised.exception.error_code, "invalid_upstream_contract")

    def test_shared_fixture_drives_in_memory_adapter_and_search(self) -> None:
        fixture = orjson.loads(SOURCE_RECORD_FIXTURE.read_bytes())
        page = ClawerSourceRecordPage.model_validate(fixture["response"])
        search_page = ClawerSourceRecordPage.model_validate(fixture["search"]["response"])
        adapter = InMemoryClawerSync()
        realm_uuid = UUID("28fe59d4-03e8-476f-9bb8-31c55c9cbdcb")
        account_uuid = UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03")
        adapter.source_record_pages[
            (str(realm_uuid), str(account_uuid), SOURCE_REF, None, None)
        ] = page
        adapter.source_record_pages[
            (str(realm_uuid), str(account_uuid), SOURCE_REF, None, "venue handoff")
        ] = search_page

        returned = adapter.browse_source_records(
            realm_uuid=realm_uuid,
            account_external_id=account_uuid,
            source_ref=SOURCE_REF,
            start_at=fixture["request"]["start_at"],
            cursor=None,
            limit=fixture["request"]["limit"],
            query=None,
        )
        searched = adapter.browse_source_records(
            realm_uuid=realm_uuid,
            account_external_id=account_uuid,
            source_ref=SOURCE_REF,
            start_at=fixture["request"]["start_at"],
            cursor=None,
            limit=5,
            query=fixture["search"]["query"],
        )
        self.assertEqual(returned, page)
        self.assertEqual(searched.records[0].record_ref, page.records[1].record_ref)
