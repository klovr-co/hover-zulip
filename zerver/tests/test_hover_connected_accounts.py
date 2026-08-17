from uuid import UUID

import orjson
from typing_extensions import override

from hover.actions_connected_accounts import (
    ConnectedAccountSelectorSpec,
    do_create_connected_account,
    do_set_connected_account_approval_state,
    do_update_connected_account_health,
    do_upsert_connected_account_grant,
)
from hover.lib_connected_accounts import user_can_use_connected_account
from hover.models import ConnectedAccount, ConnectedAccountGrant
from zerver.lib.events import apply_events, fetch_initial_state_data
from zerver.lib.exceptions import JsonableError
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog
from zerver.models.users import UserProfile


class HoverConnectedAccountTest(ZulipTestCase):
    SOURCE_REF = "src_0123456789abcdef0123456789abcdef"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.realm = self.creator.realm
        self.realm.hover_enabled = True
        self.realm.save(update_fields=["hover_enabled"])
        # Fetch these users after enabling Hover so their related Realm cache
        # matches the database state used by permission helpers.
        self.admin = self.example_user("iago")
        self.grantee = self.example_user("othello")

    def create_account(self) -> ConnectedAccount:
        return do_create_connected_account(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
            display_name="Founder conversations",
            created_by=self.creator,
            owner=self.creator,
        )

    def approve(self, account: ConnectedAccount) -> None:
        do_set_connected_account_approval_state(
            account,
            ConnectedAccount.ApprovalState.APPROVED,
            acting_user=self.admin,
        )

    def selector(self) -> ConnectedAccountSelectorSpec:
        return ConnectedAccountSelectorSpec(
            selector_type="whatsapp_group",
            source_ref=self.SOURCE_REF,
            display_name="Leadership group",
        )

    def test_pending_account_is_private_and_projection_is_secret_free(self) -> None:
        account = self.create_account()
        self.assertEqual(account.approval_state, ConnectedAccount.ApprovalState.PENDING)

        self.login_user(self.creator)
        result = self.client_get("/json/hover/connected_accounts")
        payload = self.assert_json_success(result)
        self.assertEqual(payload["connected_accounts"][0]["id"], account.id)
        self.assertEqual(payload["connected_account_grants"], [])

        self.login_user(self.grantee)
        payload = self.assert_json_success(self.client_get("/json/hover/connected_accounts"))
        self.assertEqual(payload["connected_accounts"], [])

        self.login_user(self.admin)
        payload = self.assert_json_success(self.client_get("/json/hover/connected_accounts"))
        self.assertEqual(payload["connected_accounts"][0]["id"], account.id)
        serialized = orjson.dumps(payload).decode()
        for forbidden in ["token", "credential", "vm_address", "topology", "@g.us", "+1555"]:
            self.assertNotIn(forbidden, serialized.lower())

    def test_selector_grants_are_explicit_and_empty_means_deny(self) -> None:
        account = self.create_account()
        with self.assertRaisesRegex(JsonableError, "Approve this Connected Account"):
            do_upsert_connected_account_grant(
                account,
                self.grantee,
                all_selectors=False,
                selector_specs=[self.selector()],
                acting_user=self.admin,
            )
        self.assertFalse(
            user_can_use_connected_account(
                self.grantee,
                account,
                selector_type="whatsapp_group",
                source_ref=self.SOURCE_REF,
            )
        )

        self.approve(account)
        grant = do_upsert_connected_account_grant(
            account,
            self.grantee,
            all_selectors=False,
            selector_specs=[self.selector()],
            acting_user=self.admin,
        )
        self.assertTrue(
            user_can_use_connected_account(
                self.grantee,
                account,
                selector_type="whatsapp_group",
                source_ref=self.SOURCE_REF,
            )
        )
        self.assertFalse(
            user_can_use_connected_account(
                self.grantee,
                account,
                selector_type="whatsapp_group",
                source_ref="src_ffffffffffffffffffffffffffffffff",
            )
        )

        do_upsert_connected_account_grant(
            account,
            self.grantee,
            all_selectors=False,
            selector_specs=[],
            acting_user=self.admin,
        )
        self.assertFalse(
            user_can_use_connected_account(
                self.grantee,
                account,
                selector_type="whatsapp_group",
                source_ref=self.SOURCE_REF,
            )
        )

        do_upsert_connected_account_grant(
            account,
            self.grantee,
            all_selectors=True,
            selector_specs=[],
            acting_user=self.admin,
        )
        grant.refresh_from_db()
        self.assertTrue(grant.all_selectors)
        self.assertTrue(
            user_can_use_connected_account(
                self.grantee,
                account,
                selector_type="future_capability",
                source_ref="future_abcdefgh12345678",
            )
        )

        account.approval_state = ConnectedAccount.ApprovalState.REVOKED
        account.save(update_fields=["approval_state"])
        self.assertFalse(
            user_can_use_connected_account(
                self.grantee,
                account,
                selector_type="whatsapp_group",
                source_ref=self.SOURCE_REF,
            )
        )

    def test_non_admin_visibility_never_exposes_another_teammates_grant(self) -> None:
        account = self.create_account()
        self.approve(account)
        grant = do_upsert_connected_account_grant(
            account,
            self.grantee,
            all_selectors=False,
            selector_specs=[self.selector()],
            acting_user=self.admin,
        )

        self.login_user(self.creator)
        payload = self.assert_json_success(
            self.client_get(f"/json/hover/connected_accounts/{account.id}")
        )
        self.assertEqual(payload["connected_account_grants"], [])

        self.login_user(self.grantee)
        payload = self.assert_json_success(
            self.client_get(f"/json/hover/connected_accounts/{account.id}")
        )
        self.assertEqual(payload["connected_account_grants"][0]["id"], grant.id)

        self.login_user(self.admin)
        payload = self.assert_json_success(
            self.client_get(f"/json/hover/connected_accounts/{account.id}")
        )
        self.assertEqual(payload["connected_account_grants"][0]["id"], grant.id)

    def test_admin_api_approves_assigns_restricts_revokes_and_restores(self) -> None:
        account = self.create_account()
        self.login_user(self.admin)
        result = self.client_patch(
            f"/json/hover/connected_accounts/{account.id}",
            {"approval_state": orjson.dumps("approved").decode()},
        )
        self.assert_json_success(result)

        grant_payload = {
            "user_id": orjson.dumps(self.grantee.id).decode(),
            "all_selectors": orjson.dumps(False).decode(),
            "selectors": orjson.dumps(
                [
                    {
                        "selector_type": "whatsapp_group",
                        "source_ref": self.SOURCE_REF,
                        "display_name": "Leadership group",
                    }
                ]
            ).decode(),
        }
        result = self.client_post(
            f"/json/hover/connected_accounts/{account.id}/grants", grant_payload
        )
        payload = self.assert_json_success(result)
        grant_id = payload["connected_account_grant"]["id"]
        self.assertEqual(
            payload["connected_account_grant"]["selectors"][0]["source_ref"], self.SOURCE_REF
        )

        result = self.client_delete(
            f"/json/hover/connected_accounts/{account.id}/grants/{grant_id}"
        )
        self.assertEqual(
            self.assert_json_success(result)["connected_account_grant"]["state"], "revoked"
        )

        result = self.client_post(
            f"/json/hover/connected_accounts/{account.id}/grants",
            {**grant_payload, "all_selectors": orjson.dumps(True).decode(), "selectors": "[]"},
        )
        restored = self.assert_json_success(result)["connected_account_grant"]
        self.assertEqual(restored["state"], "active")
        self.assertTrue(restored["all_selectors"])

        audit_payload = orjson.dumps(
            list(
                RealmAuditLog.objects.filter(
                    event_type=AuditLogEventType.HOVER_CONNECTED_ACCOUNT_GRANT_CHANGED
                ).values_list("extra_data", flat=True)
            )
        ).decode()
        self.assertNotIn(self.SOURCE_REF, audit_payload)

        result = self.client_patch(
            f"/json/hover/connected_accounts/{account.id}",
            {"approval_state": orjson.dumps("revoked").decode()},
        )
        self.assertEqual(
            self.assert_json_success(result)["connected_account"]["approval_state"], "revoked"
        )

    def test_non_admin_cannot_delegate_or_broaden_and_raw_jid_is_rejected(self) -> None:
        account = self.create_account()
        self.approve(account)
        self.login_user(self.creator)
        grant_payload = {
            "user_id": orjson.dumps(self.grantee.id).decode(),
            "all_selectors": orjson.dumps(True).decode(),
            "selectors": "[]",
        }
        result = self.client_post(
            f"/json/hover/connected_accounts/{account.id}/grants", grant_payload
        )
        self.assert_json_error(result, "Must be an organization administrator")

        result = self.client_patch(
            f"/json/hover/connected_accounts/{account.id}",
            {"approval_state": orjson.dumps("revoked").decode()},
        )
        self.assert_json_error(result, "Must be an organization administrator")

        self.login_user(self.admin)
        grant_payload["all_selectors"] = orjson.dumps(False).decode()
        grant_payload["selectors"] = orjson.dumps(
            [
                {
                    "selector_type": "whatsapp_group",
                    "source_ref": "15551234567-123@g.us",
                    "display_name": "Raw provider identifier",
                }
            ]
        ).decode()
        result = self.client_post(
            f"/json/hover/connected_accounts/{account.id}/grants", grant_payload
        )
        self.assert_json_error(result, 'selectors[0]["source_ref"] has invalid format')

    def test_cross_realm_account_and_grant_ids_are_indistinguishable(self) -> None:
        account = self.create_account()
        self.approve(account)
        grant = do_upsert_connected_account_grant(
            account,
            self.grantee,
            all_selectors=False,
            selector_specs=[],
            acting_user=self.admin,
        )
        other_admin = self.lear_user("cordelia")
        self.set_user_role(other_admin, UserProfile.ROLE_REALM_ADMINISTRATOR)
        other_admin.realm.hover_enabled = True
        other_admin.realm.save(update_fields=["hover_enabled"])
        self.login_user(other_admin)

        with self.assertLogs(level="WARNING") as logs:
            missing = self.client_get("/json/hover/connected_accounts/999999")
            cross_realm = self.client_get(f"/json/hover/connected_accounts/{account.id}")
            missing_grant = self.client_delete(
                "/json/hover/connected_accounts/999999/grants/999999"
            )
            cross_realm_grant = self.client_delete(
                f"/json/hover/connected_accounts/{account.id}/grants/{grant.id}"
            )

        self.assert_length(logs.output, 4)
        for log in logs.output:
            self.assertIn("attempted to access API on wrong subdomain", log)

        self.assertEqual(missing.status_code, cross_realm.status_code)
        self.assertEqual(missing.content, cross_realm.content)

        self.assertEqual(missing_grant.status_code, cross_realm_grant.status_code)
        self.assertEqual(missing_grant.content, cross_realm_grant.content)

    def test_events_are_targeted_idempotent_and_converge_with_initial_state(self) -> None:
        state = fetch_initial_state_data(
            self.admin, realm=self.realm, event_types={"hover_connected_account"}
        )
        self.assertEqual(state["hover_connected_accounts"], [])
        events = []

        with self.capture_send_event_calls(expected_num_events=1) as calls:
            account = self.create_account()
        events.append(calls[0]["event"])
        self.assertIn(self.creator.id, calls[0]["users"])
        self.assertIn(self.admin.id, calls[0]["users"])

        with self.capture_send_event_calls(expected_num_events=1) as calls:
            self.approve(account)
        events.append(calls[0]["event"])

        with self.capture_send_event_calls(expected_num_events=1) as calls:
            grant = do_upsert_connected_account_grant(
                account,
                self.grantee,
                all_selectors=False,
                selector_specs=[self.selector()],
                acting_user=self.admin,
            )
        events.append(calls[0]["event"])
        self.assertIn(self.grantee.id, calls[0]["users"])
        self.assertNotIn(self.creator.id, calls[0]["users"])

        with self.capture_send_event_calls(expected_num_events=0):
            do_upsert_connected_account_grant(
                account,
                self.grantee,
                all_selectors=False,
                selector_specs=[self.selector()],
                acting_user=self.admin,
            )

        apply_events(
            self.admin,
            state=state,
            events=events,
            fetch_event_types={"hover_connected_account"},
            client_gravatar=False,
            slim_presence=False,
            include_subscribers=False,
            linkifier_url_template=False,
            user_list_incomplete=False,
            include_deactivated_groups=False,
        )
        fresh = fetch_initial_state_data(
            self.admin, realm=self.realm, event_types={"hover_connected_account"}
        )
        self.assertEqual(state["hover_connected_accounts"], fresh["hover_connected_accounts"])
        self.assertEqual(
            state["hover_connected_account_grants"], fresh["hover_connected_account_grants"]
        )
        self.assertEqual(state["hover_connected_account_grants"][0]["id"], grant.id)

    def test_health_and_audit_metadata_are_constrained_and_secret_free(self) -> None:
        account = self.create_account()
        checked_at = account.date_created
        with self.capture_send_event_calls(expected_num_events=1) as calls:
            do_update_connected_account_health(
                account,
                health_status=ConnectedAccount.HealthStatus.DEGRADED,
                checked_at=checked_at,
            )
        event = calls[0]["event"]
        self.assertEqual(event["account"]["health_status"], "degraded")
        self.assertEqual(event["account"]["health_checked_at"], checked_at.isoformat())

        audit_logs = RealmAuditLog.objects.filter(
            event_type__in=[
                AuditLogEventType.HOVER_CONNECTED_ACCOUNT_CREATED,
                AuditLogEventType.HOVER_CONNECTED_ACCOUNT_HEALTH_CHANGED,
            ]
        )
        serialized = orjson.dumps([audit.extra_data for audit in audit_logs]).decode()
        self.assertNotIn(str(account.external_account_id), serialized)
        self.assertNotIn(self.SOURCE_REF, serialized)
        for forbidden in ["token", "credential", "vm", "topology", "jid", "phone"]:
            self.assertNotIn(forbidden, serialized.lower())

        with self.assertRaisesRegex(JsonableError, "Invalid Connected Account health status"):
            do_update_connected_account_health(
                account, health_status="raw_error_text", checked_at=checked_at
            )

    def test_duplicate_external_account_and_invalid_grantees_are_rejected(self) -> None:
        self.create_account()
        with self.assertRaisesRegex(JsonableError, "Connected Account already exists"):
            self.create_account()

        account = ConnectedAccount.objects.get()
        self.approve(account)
        guest = self.example_user("polonius")
        self.set_user_role(guest, UserProfile.ROLE_GUEST)
        with self.assertRaisesRegex(JsonableError, "Invalid user ID"):
            do_upsert_connected_account_grant(
                account,
                guest,
                all_selectors=False,
                selector_specs=[],
                acting_user=self.admin,
            )

        self.assertFalse(ConnectedAccountGrant.objects.filter(account=account, user=guest).exists())
