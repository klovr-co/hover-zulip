from datetime import date, datetime, timedelta, timezone
from io import StringIO
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import orjson
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone as django_timezone
from typing_extensions import override

from hover.actions_connected_accounts import do_set_connected_account_approval_state
from hover.actions_memberships import do_remove_space_member
from hover.clawer_sync import ClawerSyncError, InMemoryClawerSync, StudioClawerSync
from hover.models import (
    ConnectedAccount,
    ParticipantSelectorReconciliation,
    Source,
    SourceParticipantBinding,
    Space,
    SpaceAttachment,
    SpaceMembership,
)
from hover.participant_selector_reconciliation import (
    desired_participant_refs,
    due_participant_reconciliation_ids,
    reconcile_participant_selector_row,
    schedule_participant_selector_reconciliation,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile


class HoverParticipantSelectorReconciliationTest(ZulipTestCase):
    PARTICIPANT_REF = "person_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    OTHER_PARTICIPANT_REF = "person_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.admin = self.example_user("iago")
        self.realm = self.user.realm
        self.realm.hover_enabled = True
        self.realm.save(update_fields=["hover_enabled"])
        self.category = check_add_channel_folder(
            self.realm, "Selector programs", "", acting_user=self.admin
        )
        self.account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
            display_name="Operations conversations",
            owner=self.user,
            created_by=self.user,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
            connection_kind=ConnectedAccount.ConnectionKind.REMOTE_STUDIO,
        )
        self.source = Source.objects.create(
            realm=self.realm,
            account=self.account,
            adapter_key="clawer_sync",
            provider_key="whatsapp",
            provider_name="WhatsApp",
            source_type="group",
            external_ref="src_0123456789abcdef0123456789abcdef",
            display_name="Operations",
        )
        SourceParticipantBinding.objects.create(
            realm=self.realm,
            source=self.source,
            participant_ref=self.PARTICIPANT_REF,
            user=self.user,
            match_basis=SourceParticipantBinding.MatchBasis.VERIFIED_EMAIL,
            observation_basis="obs_0123456789abcdef0123456789abcdef",
        )

    def create_launched_space(
        self,
        *,
        name: str,
        user: UserProfile | None = None,
        source: Source | None = None,
    ) -> Space:
        member = user or self.user
        selected_source = source or self.source
        stream = self.subscribe(member, name, invite_only=True)
        space = Space.objects.create(
            realm=member.realm,
            name=name,
            category=(
                self.category
                if member.realm_id == self.realm.id
                else check_add_channel_folder(
                    member.realm, f"{name} programs", "", acting_user=member
                )
            ),
            created_by=member,
            state=Space.State.LAUNCHED,
            stream=stream,
        )
        SpaceMembership.objects.create(
            realm=member.realm,
            space=space,
            user=member,
            role=SpaceMembership.Role.CONTRIBUTOR,
            added_by=member,
        )
        SpaceAttachment.objects.create(
            realm=member.realm,
            space=space,
            source=selected_source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.CUSTOM,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            custom_start_date=date(2026, 8, 1),
            attached_by=member,
        )
        return space

    def reconcile(self, adapter: InMemoryClawerSync) -> None:
        row = ParticipantSelectorReconciliation.objects.get(account=self.account)
        result = reconcile_participant_selector_row(
            reconciliation_id=row.id,
            clawer_sync=adapter,
        )
        self.assertTrue(result.success)
        self.assertTrue(result.current)

    def test_provisions_complete_deduplicated_account_set_without_cross_realm_refs(self) -> None:
        self.create_launched_space(name="Selector launch one")
        self.create_launched_space(name="Selector launch two")

        other_user = self.mit_user("sipbtest")
        other_realm = other_user.realm
        other_account = ConnectedAccount.objects.create(
            realm=other_realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=uuid4(),
            display_name="Other organization conversations",
            owner=other_user,
            created_by=other_user,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        other_source = Source.objects.create(
            realm=other_realm,
            account=other_account,
            adapter_key="clawer_sync",
            provider_key="whatsapp",
            provider_name="WhatsApp",
            source_type="group",
            external_ref="src_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            display_name="Other operations",
        )
        SourceParticipantBinding.objects.create(
            realm=other_realm,
            source=other_source,
            participant_ref=self.OTHER_PARTICIPANT_REF,
            user=other_user,
            match_basis=SourceParticipantBinding.MatchBasis.VERIFIED_PHONE,
            observation_basis="obs_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        self.create_launched_space(
            name="Other realm selector launch", user=other_user, source=other_source
        )

        self.assertEqual(desired_participant_refs(self.account), [self.PARTICIPANT_REF])
        self.assertEqual(desired_participant_refs(other_account), [self.OTHER_PARTICIPANT_REF])
        schedule_participant_selector_reconciliation(self.account.id)
        adapter = InMemoryClawerSync()
        self.reconcile(adapter)
        self.assertEqual(
            adapter.participant_reconcile_calls[0]["participant_refs"],
            [self.PARTICIPANT_REF],
        )

    def test_shared_participant_survives_one_space_removal_then_is_revoked(self) -> None:
        first_space = self.create_launched_space(name="Shared selector one")
        second_space = self.create_launched_space(name="Shared selector two")
        schedule_participant_selector_reconciliation(self.account.id)
        adapter = InMemoryClawerSync()
        self.reconcile(adapter)

        do_remove_space_member(first_space, self.user, acting_user=self.admin)
        self.assertEqual(
            ParticipantSelectorReconciliation.objects.get(account=self.account).state,
            ParticipantSelectorReconciliation.State.PENDING,
        )
        self.reconcile(adapter)
        self.assertEqual(
            adapter.participant_reconcile_calls[-1]["participant_refs"],
            [self.PARTICIPANT_REF],
        )

        do_remove_space_member(second_space, self.user, acting_user=self.admin)
        self.reconcile(adapter)
        self.assertEqual(adapter.participant_reconcile_calls[-1]["participant_refs"], [])

    def test_membership_change_during_remote_call_leaves_new_generation_pending(self) -> None:
        space = self.create_launched_space(name="Racing selector launch")
        schedule_participant_selector_reconciliation(self.account.id)
        row = ParticipantSelectorReconciliation.objects.get(account=self.account)
        initial_generation = row.generation
        adapter = InMemoryClawerSync()

        def remove_member_during_request(**kwargs: object) -> None:
            adapter.participant_reconcile_calls.append(kwargs)
            do_remove_space_member(space, self.user, acting_user=self.admin)

        with patch.object(
            adapter,
            "reconcile_participant_selectors",
            side_effect=remove_member_during_request,
        ):
            result = reconcile_participant_selector_row(
                reconciliation_id=row.id,
                clawer_sync=adapter,
            )
        self.assertTrue(result.success)
        self.assertFalse(result.current)
        self.assertEqual(
            adapter.participant_reconcile_calls[-1]["participant_refs"],
            [self.PARTICIPANT_REF],
        )
        row.refresh_from_db()
        self.assertGreater(row.generation, initial_generation)
        self.assertEqual(row.state, ParticipantSelectorReconciliation.State.PENDING)
        self.assertIsNone(row.lease_token)

        self.reconcile(adapter)
        self.assertEqual(adapter.participant_reconcile_calls[-1]["participant_refs"], [])
        row.refresh_from_db()
        self.assertEqual(row.state, ParticipantSelectorReconciliation.State.CURRENT)

    def test_revoked_hover_account_reconciles_empty_set(self) -> None:
        self.create_launched_space(name="Revoked account selector launch")
        do_set_connected_account_approval_state(
            self.account,
            ConnectedAccount.ApprovalState.REVOKED,
            acting_user=self.admin,
        )
        adapter = InMemoryClawerSync()
        self.reconcile(adapter)
        self.assertEqual(adapter.participant_reconcile_calls[-1]["participant_refs"], [])

    def test_outage_persists_backoff_and_retries(self) -> None:
        self.create_launched_space(name="Retry selector launch")
        schedule_participant_selector_reconciliation(self.account.id)
        row = ParticipantSelectorReconciliation.objects.get(account=self.account)
        adapter = InMemoryClawerSync()
        outage = ClawerSyncError(
            error_code="clawer_unavailable",
            operation="participant_selector_reconcile",
            http_status_code=503,
            retryable=True,
            retry_after_seconds=30,
        )
        with patch.object(adapter, "reconcile_participant_selectors", side_effect=outage):
            result = reconcile_participant_selector_row(
                reconciliation_id=row.id,
                clawer_sync=adapter,
            )
        self.assertFalse(result.success)
        row.refresh_from_db()
        self.assertEqual(row.state, ParticipantSelectorReconciliation.State.BACKOFF)
        self.assertEqual(row.attempts, 1)
        self.assertEqual(row.last_error_code, "clawer_unavailable")
        self.assertGreater(row.next_attempt_at, django_timezone.now())

        schedule_participant_selector_reconciliation(self.account.id)
        self.reconcile(adapter)
        row.refresh_from_db()
        self.assertEqual(row.state, ParticipantSelectorReconciliation.State.CURRENT)
        self.assertEqual(row.attempts, 0)

        row.state = ParticipantSelectorReconciliation.State.LEASED
        row.lease_token = uuid4()
        row.lease_expires_at = django_timezone.now()
        row.save(update_fields=["state", "lease_token", "lease_expires_at"])
        self.assertIn(row.id, due_participant_reconciliation_ids(limit=100))

    def test_concurrent_worker_does_not_replace_an_active_lease(self) -> None:
        self.create_launched_space(name="Leased selector launch")
        schedule_participant_selector_reconciliation(self.account.id)
        row = ParticipantSelectorReconciliation.objects.get(account=self.account)
        lease_token = uuid4()
        row.state = ParticipantSelectorReconciliation.State.LEASED
        row.lease_token = lease_token
        row.lease_expires_at = django_timezone.now() + timedelta(minutes=1)
        row.save(update_fields=["state", "lease_token", "lease_expires_at"])
        adapter = InMemoryClawerSync()

        result = reconcile_participant_selector_row(
            reconciliation_id=row.id,
            clawer_sync=adapter,
        )

        self.assertTrue(result.success)
        self.assertFalse(result.current)
        self.assertEqual(adapter.participant_reconcile_calls, [])
        row.refresh_from_db()
        self.assertEqual(row.state, ParticipantSelectorReconciliation.State.LEASED)
        self.assertEqual(row.lease_token, lease_token)

    def test_repair_command_logs_only_internal_ids_and_counts(self) -> None:
        self.create_launched_space(name="Content free selector launch")
        adapter = InMemoryClawerSync()
        stdout = StringIO()
        stderr = StringIO()
        with patch(
            "zerver.management.commands.reconcile_hover_participant_selectors.get_clawer_sync",
            return_value=adapter,
        ):
            call_command(
                "reconcile_hover_participant_selectors",
                account_id=self.account.id,
                stdout=stdout,
                stderr=stderr,
            )
        output = stdout.getvalue() + stderr.getvalue()
        self.assertIn(f"account={self.account.id} participant_count=1", output)
        self.assertNotIn(self.PARTICIPANT_REF, output)
        self.assertNotIn("hamlet@zulip.com", output)
        self.assertNotIn("+15551234567", output)

    def test_repair_command_keeps_failures_content_free(self) -> None:
        self.create_launched_space(name="Failed selector launch")
        adapter = InMemoryClawerSync()
        outage = ClawerSyncError(
            error_code="clawer_timeout",
            operation="participant_selector_reconcile",
            http_status_code=504,
            retryable=True,
        )
        stdout = StringIO()
        stderr = StringIO()
        with (
            patch.object(adapter, "reconcile_participant_selectors", side_effect=outage),
            patch(
                "zerver.management.commands.reconcile_hover_participant_selectors.get_clawer_sync",
                return_value=adapter,
            ),
            self.assertRaises(CommandError),
        ):
            call_command(
                "reconcile_hover_participant_selectors",
                account_id=self.account.id,
                stdout=stdout,
                stderr=stderr,
            )
        output = stdout.getvalue() + stderr.getvalue()
        self.assertIn(f"account={self.account.id} error=clawer_timeout", output)
        self.assertNotIn(self.PARTICIPANT_REF, output)
        self.assertNotIn("hamlet@zulip.com", output)


class StudioParticipantSelectorClientContractTest(ZulipTestCase):
    def test_uses_fixed_put_route_and_strict_count_contract(self) -> None:
        realm_uuid = UUID("28fe59d4-03e8-476f-9bb8-31c55c9cbdcb")
        account_uuid = UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03")
        participant_ref = "person_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        response = MagicMock()
        response.ok = True
        response.content = orjson.dumps({"participant_count": 1})
        response.headers = {"X-Request-Id": "1851666d-6f29-4801-a72f-ee43ab96dd79"}
        response.json.return_value = {"participant_count": 1}
        session = MagicMock()
        session.put.return_value = response
        credential = "hvr_srv_" + "a" * 32
        adapter = StudioClawerSync(
            base_url="https://studio.example.test/",
            credentials={str(realm_uuid): credential},
            session=session,
        )

        adapter.reconcile_participant_selectors(
            realm_uuid=realm_uuid,
            account_external_id=account_uuid,
            participant_refs=[participant_ref],
        )
        session.put.assert_called_once_with(
            f"https://studio.example.test/api/hover/v1/connected-accounts/{account_uuid}/participant-selectors/reconcile",
            json={"participant_refs": [participant_ref]},
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/json",
            },
        )
        session.post.assert_not_called()

        response.json.return_value = {"participant_count": 0}
        with self.assertRaises(ClawerSyncError) as raised:
            adapter.reconcile_participant_selectors(
                realm_uuid=realm_uuid,
                account_external_id=account_uuid,
                participant_refs=[participant_ref],
            )
        self.assertEqual(raised.exception.error_code, "invalid_upstream_contract")

    def test_rejects_nonopaque_duplicate_unsorted_and_oversized_refs_locally(self) -> None:
        adapter = StudioClawerSync(
            base_url="https://studio.example.test/",
            credentials={"28fe59d4-03e8-476f-9bb8-31c55c9cbdcb": "hvr_srv_" + "a" * 32},
            session=MagicMock(),
        )
        kwargs = {
            "realm_uuid": UUID("28fe59d4-03e8-476f-9bb8-31c55c9cbdcb"),
            "account_external_id": UUID("d38c68c4-d70f-44ec-a17e-c7c845f91c03"),
        }
        for refs in [
            ["+15551234567"],
            ["person_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "person_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
            ["person_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"] * 2,
            [f"person_{number:032x}" for number in range(1_001)],
        ]:
            with self.subTest(refs_count=len(refs)), self.assertRaises(ValueError):
                adapter.reconcile_participant_selectors(participant_refs=refs, **kwargs)
