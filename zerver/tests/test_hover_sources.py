import hashlib
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import orjson
from typing_extensions import override

from hover.actions_connected_accounts import (
    ConnectedAccountSelectorSpec,
    do_create_connected_account,
    do_set_connected_account_approval_state,
    do_upsert_connected_account_grant,
)
from hover.actions_sources import do_attach_source
from hover.actions_spaces import do_create_space, do_launch_space
from hover.clawer_sync import ClawerSource, ClawerSyncError, InMemoryClawerSync, StudioClawerSync
from hover.lib_sources import history_boundary
from hover.models import ConnectedAccount, Source, SpaceAttachment
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.events import fetch_initial_state_data
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models.groups import SystemGroups

SOURCE_DISCOVERY_FIXTURE = Path(__file__).parent / "fixtures" / "hover" / "source_discovery_v1.json"


class HoverSourcesTest(ZulipTestCase):
    ALLOWED_REF = "src_0123456789abcdef0123456789abcdef"
    DENIED_REF = "src_ffffffffffffffffffffffffffffffff"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.actor = self.example_user("hamlet")
        self.realm = self.actor.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        self.category = check_add_channel_folder(
            self.realm,
            "Programs",
            "",
            acting_user=self.example_user("iago"),
        )
        self.space = do_create_space(
            self.actor,
            name="Launch readiness",
            description="",
            category=self.category,
        )
        self.account = do_create_connected_account(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
            display_name="Founder conversations",
            created_by=self.actor,
            owner=self.actor,
        )
        do_set_connected_account_approval_state(
            self.account,
            ConnectedAccount.ApprovalState.APPROVED,
            acting_user=self.example_user("iago"),
        )
        self.grant = do_upsert_connected_account_grant(
            self.account,
            self.actor,
            all_selectors=False,
            selector_specs=[
                ConnectedAccountSelectorSpec(
                    selector_type="whatsapp_group",
                    source_ref=self.ALLOWED_REF,
                    display_name="Leadership group",
                )
            ],
            acting_user=self.example_user("iago"),
        )

    def adapter(self, sources: list[ClawerSource] | None = None) -> InMemoryClawerSync:
        if sources is None:
            sources = [
                ClawerSource(
                    source_ref=self.ALLOWED_REF,
                    provider="whatsapp",
                    source_type="group",
                    display_name="Leadership group",
                )
            ]
        return InMemoryClawerSync(
            {(str(self.realm.uuid), str(self.account.external_account_id)): sources}
        )

    def source_post_data(self, **overrides: object) -> dict[str, str]:
        data: dict[str, object] = {
            "account_id": self.account.id,
            "source_ref": self.ALLOWED_REF,
            "history_window": "today",
            "history_timezone": "America/Los_Angeles",
            "custom_start_date": None,
        }
        data.update(overrides)
        return {key: orjson.dumps(value).decode() for key, value in data.items()}

    def test_discovery_intersects_actor_grant_after_full_scan(self) -> None:
        denied = [
            ClawerSource(
                source_ref=f"src_{number:032x}",
                provider="whatsapp",
                source_type="group",
                display_name=f"Denied {number}",
            )
            for number in range(100, 200)
        ]
        adapter = self.adapter(
            [
                *denied,
                ClawerSource(
                    source_ref=self.ALLOWED_REF,
                    provider="whatsapp",
                    source_type="group",
                    display_name="Leadership group",
                ),
                ClawerSource(
                    source_ref=self.DENIED_REF,
                    provider="github",
                    source_type="repository",
                    display_name="Private repository",
                ),
            ]
        )
        self.login_user(self.actor)
        with patch("hover.views_sources.get_clawer_sync", return_value=adapter):
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources/discover",
                {
                    "account_id": orjson.dumps(self.account.id).decode(),
                    "cursor": "null",
                    "limit": "20",
                    "query": orjson.dumps("").decode(),
                },
            )
        payload = self.assert_json_success(result)
        self.assertEqual(
            [source["source_ref"] for source in payload["sources"]], [self.ALLOWED_REF]
        )
        self.assert_length(adapter.discovery_calls, 2)
        serialized = orjson.dumps(payload).decode()
        for forbidden in [self.DENIED_REF, "@g.us", "phone", "credential", "member"]:
            self.assertNotIn(forbidden, serialized)

    def test_empty_or_denied_local_grant_never_calls_studio(self) -> None:
        adapter = self.adapter()
        do_upsert_connected_account_grant(
            self.account,
            self.actor,
            all_selectors=False,
            selector_specs=[],
            acting_user=self.example_user("iago"),
        )
        self.login_user(self.actor)
        with patch("hover.views_sources.get_clawer_sync", return_value=adapter):
            discovery = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources/discover",
                {
                    "account_id": orjson.dumps(self.account.id).decode(),
                    "cursor": "null",
                    "limit": "20",
                    "query": orjson.dumps("").decode(),
                },
            )
            preview = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources/preview",
                {
                    "account_id": orjson.dumps(self.account.id).decode(),
                    "source_ref": orjson.dumps(self.ALLOWED_REF).decode(),
                },
            )
        self.assertEqual(self.assert_json_success(discovery)["sources"], [])
        self.assertEqual(preview.status_code, 404)
        self.assertEqual(adapter.discovery_calls, [])

    def test_restricted_pagination_cursor_is_bound_to_actor_space_account_and_query(self) -> None:
        do_upsert_connected_account_grant(
            self.account,
            self.actor,
            all_selectors=True,
            selector_specs=[],
            acting_user=self.example_user("iago"),
        )
        sources = [
            ClawerSource(
                source_ref=f"src_{number:032x}",
                provider="whatsapp",
                source_type="group",
                display_name=f"Program {number}",
            )
            for number in range(3)
        ]
        adapter = self.adapter(sources)
        self.login_user(self.actor)
        with patch("hover.views_sources.get_clawer_sync", return_value=adapter):
            first = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources/discover",
                {
                    "account_id": orjson.dumps(self.account.id).decode(),
                    "cursor": "null",
                    "limit": "1",
                    "query": orjson.dumps("Program").decode(),
                },
            )
            first_payload = self.assert_json_success(first)
            self.assertTrue(first_payload["has_more"])
            second = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources/discover",
                {
                    "account_id": orjson.dumps(self.account.id).decode(),
                    "cursor": orjson.dumps(first_payload["next_cursor"]).decode(),
                    "limit": "1",
                    "query": orjson.dumps("Program").decode(),
                },
            )
            changed_query = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources/discover",
                {
                    "account_id": orjson.dumps(self.account.id).decode(),
                    "cursor": orjson.dumps(first_payload["next_cursor"]).decode(),
                    "limit": "1",
                    "query": orjson.dumps("Different").decode(),
                },
            )
        second_payload = self.assert_json_success(second)
        self.assertEqual(second_payload["sources"][0]["source_ref"], sources[1].source_ref)
        self.assert_json_error(changed_query, "Invalid Source discovery cursor.")

    def test_preview_is_canonical_and_safe(self) -> None:
        adapter = self.adapter()
        self.login_user(self.actor)
        with patch("hover.views_sources.get_clawer_sync", return_value=adapter):
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources/preview",
                {
                    "account_id": orjson.dumps(self.account.id).decode(),
                    "source_ref": orjson.dumps(self.ALLOWED_REF).decode(),
                },
            )
        source = self.assert_json_success(result)["source"]
        self.assertEqual(
            set(source),
            {
                "source_ref",
                "provider_key",
                "source_type",
                "display_name",
                "account_id",
                "account_display_name",
            },
        )
        self.assertEqual(source["display_name"], "Leadership group")
        self.assertEqual(source["provider_key"], "whatsapp")

    def test_discovery_and_preview_require_explicit_space_admin(self) -> None:
        member = self.example_user("othello")
        do_upsert_connected_account_grant(
            self.account,
            member,
            all_selectors=True,
            selector_specs=[],
            acting_user=self.example_user("iago"),
        )
        adapter = self.adapter()
        self.login_user(member)
        # Simulate H#8 broadening post-launch Space read access. The endpoint's
        # independent administrator check must still deny both operations.
        self.space.state = "launched"
        with (
            patch("hover.views_sources.access_space_by_id", return_value=self.space),
            patch("hover.views_sources.get_clawer_sync", return_value=adapter),
        ):
            for suffix, data in [
                (
                    "discover",
                    {
                        "account_id": orjson.dumps(self.account.id).decode(),
                        "cursor": "null",
                        "limit": "20",
                        "query": orjson.dumps("").decode(),
                    },
                ),
                (
                    "preview",
                    {
                        "account_id": orjson.dumps(self.account.id).decode(),
                        "source_ref": orjson.dumps(self.ALLOWED_REF).decode(),
                    },
                ),
            ]:
                result = self.client_post(
                    f"/json/hover/spaces/{self.space.id}/sources/{suffix}", data
                )
                self.assert_json_error(result, "Invalid Space ID")
        self.assertEqual(adapter.discovery_calls, [])

    def test_attach_is_local_idempotent_and_does_not_consume_sync(self) -> None:
        adapter = self.adapter()
        self.login_user(self.actor)
        with (
            patch("hover.views_sources.get_clawer_sync", return_value=adapter),
            self.capture_send_event_calls(expected_num_events=1) as events,
        ):
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources",
                self.source_post_data(),
            )
        payload = self.assert_json_success(result)
        attachment = SpaceAttachment.objects.select_related("source").get()
        self.assertTrue(payload["created"])
        self.assertEqual(attachment.state, SpaceAttachment.State.ACTIVE)
        self.assertEqual(
            attachment.history_start_at.isoformat(), payload["attachment"]["history_start_at"]
        )
        self.assertEqual(adapter.sync_calls, [])
        self.assertEqual(events[0]["users"], [self.actor.id])
        event_space = events[0]["event"]["space"]
        self.assertEqual(
            event_space["attachments"][0]["source"]["display_name"], "Leadership group"
        )
        self.assertNotIn(self.ALLOWED_REF, orjson.dumps(event_space).decode())

        first_start = attachment.history_start_at
        adapter.discovery_calls.clear()
        with (
            patch("hover.views_sources.get_clawer_sync", return_value=adapter),
            self.capture_send_event_calls(expected_num_events=0),
        ):
            replay = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources",
                self.source_post_data(),
            )
        self.assertFalse(self.assert_json_success(replay)["created"])
        attachment.refresh_from_db()
        self.assertEqual(attachment.history_start_at, first_start)
        self.assertEqual(adapter.discovery_calls, [])

        with (
            patch("hover.views_sources.get_clawer_sync", return_value=adapter),
            self.capture_send_event_calls(expected_num_events=0),
        ):
            conflict = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources",
                self.source_post_data(history_window="last_30_days"),
            )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(orjson.loads(conflict.content)["error_code"], "history_window_conflict")
        self.assertEqual(adapter.discovery_calls, [])

    def test_attachment_persistence_rechecks_setup_after_launch_race(self) -> None:
        do_upsert_connected_account_grant(
            self.account,
            self.actor,
            all_selectors=True,
            selector_specs=[],
            acting_user=self.example_user("iago"),
        )
        self.login_user(self.actor)
        adapter = self.adapter()
        with patch("hover.views_sources.get_clawer_sync", return_value=adapter):
            self.assert_json_success(
                self.client_post(
                    f"/json/hover/spaces/{self.space.id}/sources",
                    self.source_post_data(),
                )
            )

        raced_ref = "src_abcdef0123456789abcdef0123456789"

        def launch_during_canonical_lookup(**kwargs: object) -> ClawerSource:
            do_launch_space(self.space, acting_user=self.actor)
            return ClawerSource(
                source_ref=raced_ref,
                provider="whatsapp",
                source_type="group",
                display_name="Raced source",
            )

        source_count = Source.objects.count()
        attachment_count = SpaceAttachment.objects.count()
        with patch(
            "hover.actions_sources.canonical_source_for_attachment",
            side_effect=launch_during_canonical_lookup,
        ):
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/sources",
                self.source_post_data(source_ref=raced_ref),
            )
        self.assert_json_error(result, "Invalid Space ID")
        self.assertEqual(Source.objects.count(), source_count)
        self.assertEqual(SpaceAttachment.objects.count(), attachment_count)

    def test_source_identity_is_reused_across_spaces(self) -> None:
        second_space = do_create_space(
            self.actor,
            name="Second program",
            description="",
            category=self.category,
        )
        adapter = self.adapter()
        do_attach_source(
            acting_user=self.actor,
            space=self.space,
            account_id=self.account.id,
            source_ref=self.ALLOWED_REF,
            history_window="today",
            history_timezone="UTC",
            custom_start_date=None,
            clawer_sync=adapter,
        )
        do_attach_source(
            acting_user=self.actor,
            space=second_space,
            account_id=self.account.id,
            source_ref=self.ALLOWED_REF,
            history_window="today",
            history_timezone="UTC",
            custom_start_date=None,
            clawer_sync=adapter,
        )
        self.assertEqual(Source.objects.count(), 1)
        self.assertEqual(SpaceAttachment.objects.count(), 2)

    def test_history_windows_are_exact_local_midnight_utc_boundaries(self) -> None:
        now = datetime(2026, 3, 9, 12, tzinfo=timezone.utc)
        today = history_boundary(
            history_window="today",
            history_timezone="America/Los_Angeles",
            custom_start_date=None,
            now=now,
        )
        self.assertEqual(today.history_start_at, datetime(2026, 3, 9, 7, tzinfo=timezone.utc))
        lookback = history_boundary(
            history_window="last_30_days",
            history_timezone="America/Los_Angeles",
            custom_start_date=None,
            now=now,
        )
        self.assertEqual(lookback.history_start_at, datetime(2026, 2, 7, 8, tzinfo=timezone.utc))
        custom = history_boundary(
            history_window="custom",
            history_timezone="Asia/Kuala_Lumpur",
            custom_start_date=date(2026, 3, 1),
            now=now,
        )
        self.assertEqual(custom.history_start_at, datetime(2026, 2, 28, 16, tzinfo=timezone.utc))
        with self.assertRaisesRegex(JsonableError, "cannot be in the future"):
            history_boundary(
                history_window="custom",
                history_timezone="America/Los_Angeles",
                custom_start_date=date(2026, 3, 10),
                now=now,
            )

    def test_attachment_projection_converges_with_initial_state(self) -> None:
        do_attach_source(
            acting_user=self.actor,
            space=self.space,
            account_id=self.account.id,
            source_ref=self.ALLOWED_REF,
            history_window="today",
            history_timezone="UTC",
            custom_start_date=None,
            clawer_sync=self.adapter(),
        )
        state = fetch_initial_state_data(self.actor, realm=self.realm, event_types={"hover_space"})
        projected = state["hover_spaces"][0]["attachments"][0]
        self.assertEqual(projected["source"]["display_name"], "Leadership group")
        serialized = orjson.dumps(projected).decode()
        self.assertNotIn(self.ALLOWED_REF, serialized)
        self.assertNotIn(str(self.account.external_account_id), serialized)


class StudioClawerSyncTest(ZulipTestCase):
    def test_discovery_contract_is_strict_and_server_authenticated(self) -> None:
        realm_uuid = UUID("28fe59d4-03e8-476f-9bb8-31c55c9cbdcb")
        account_uuid = UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03")
        fixture_bytes = SOURCE_DISCOVERY_FIXTURE.read_bytes()
        expected_checksum = Path(f"{SOURCE_DISCOVERY_FIXTURE}.sha256").read_text().strip()
        self.assertEqual(hashlib.sha256(fixture_bytes).hexdigest(), expected_checksum)
        for forbidden in [b"@g.us", b"phone", b"credential", b"token", b"member"]:
            self.assertNotIn(forbidden, fixture_bytes.lower())
        response = MagicMock()
        response.ok = True
        response.content = fixture_bytes
        response.headers = {"X-Request-Id": "1851666d-6f29-4801-a72f-ee43ab96dd79"}
        response.json.return_value = orjson.loads(fixture_bytes)
        session = MagicMock()
        session.post.return_value = response
        credential = "hvr_srv_" + "a" * 32
        adapter = StudioClawerSync(
            base_url="https://studio.example.test/",
            credentials={str(realm_uuid): credential},
            session=session,
        )
        page = adapter.discover_sources(
            realm_uuid=realm_uuid,
            account_external_id=account_uuid,
            cursor=None,
            limit=100,
            query="leadership",
        )
        self.assertEqual(page.sources[0].source_ref, HoverSourcesTest.ALLOWED_REF)
        session.post.assert_called_once_with(
            f"https://studio.example.test/api/hover/v1/connected-accounts/{account_uuid}/sources/discover",
            json={"limit": 100, "query": "leadership"},
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/json",
            },
        )

        response.json.return_value["unexpected"] = "field"
        with self.assertRaises(ClawerSyncError) as raised:
            adapter.discover_sources(
                realm_uuid=realm_uuid,
                account_external_id=account_uuid,
                cursor=None,
                limit=100,
                query=None,
            )
        self.assertEqual(raised.exception.error_code, "invalid_upstream_contract")

        response.json.return_value.pop("unexpected")
        response.json.return_value["sources"][0]["display_name"] = "15551234567-123@g.us"
        with self.assertRaises(ClawerSyncError) as unsafe_name:
            adapter.discover_sources(
                realm_uuid=realm_uuid,
                account_external_id=account_uuid,
                cursor=None,
                limit=100,
                query=None,
            )
        self.assertEqual(unsafe_name.exception.error_code, "invalid_upstream_contract")

    def test_typed_studio_error_preserves_retry_contract_and_request_id(self) -> None:
        realm_uuid = UUID("28fe59d4-03e8-476f-9bb8-31c55c9cbdcb")
        request_id = "1851666d-6f29-4801-a72f-ee43ab96dd79"
        response = MagicMock()
        response.ok = False
        response.status_code = 429
        response.content = b"{}"
        response.headers = {"X-Request-Id": request_id, "Retry-After": "30"}
        response.json.return_value = {
            "error": {
                "code": "rate_limited",
                "message": "Too many requests.",
                "retryable": True,
                "operation": "source_discovery",
                "request_id": request_id,
                "retry_after_seconds": 30,
            }
        }
        session = MagicMock()
        session.post.return_value = response
        adapter = StudioClawerSync(
            base_url="https://studio.example.test",
            credentials={str(realm_uuid): "hvr_srv_" + "a" * 32},
            session=session,
        )
        with self.assertRaises(ClawerSyncError) as raised:
            adapter.discover_sources(
                realm_uuid=realm_uuid,
                account_external_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
                cursor=None,
                limit=100,
                query=None,
            )
        self.assertEqual(raised.exception.error_code, "rate_limited")
        self.assertEqual(raised.exception.retry_after_seconds, 30)
        self.assertEqual(raised.exception.upstream_request_id, request_id)

    def test_invalid_server_credential_fails_closed_without_request(self) -> None:
        session = MagicMock()
        adapter = StudioClawerSync(
            base_url="https://studio.example.test",
            credentials={"28fe59d4-03e8-476f-9bb8-31c55c9cbdcb": "browser-token"},
            session=session,
        )
        with self.assertRaises(ClawerSyncError) as raised:
            adapter.discover_sources(
                realm_uuid=UUID("28fe59d4-03e8-476f-9bb8-31c55c9cbdcb"),
                account_external_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
                cursor=None,
                limit=100,
                query=None,
            )
        self.assertTrue(raised.exception.retryable)
        session.post.assert_not_called()
