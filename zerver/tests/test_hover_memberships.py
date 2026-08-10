from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import orjson
from typing_extensions import override

from hover.actions_memberships import (
    do_confirm_space_member,
    do_remove_space_member,
    refresh_space_membership_suggestions,
)
from hover.actions_spaces import do_add_space_administrator, do_create_space, do_launch_space
from hover.lib_spaces import get_accessible_spaces, get_space_data
from hover.models import (
    ConnectedAccount,
    Source,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
    SpaceMembershipSuggestion,
)
from hover.observations import ResolvedIdentityObservation
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, Recipient, Stream, Subscription, UserProfile
from zerver.models.groups import SystemGroups, UserGroup
from zerver.models.realm_audit_logs import RealmAuditLog


class HoverMembershipsTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.realm = self.creator.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        self.member = self.example_user("othello")
        self.other_member = self.example_user("cordelia")
        self.member.realm = self.realm
        self.other_member.realm = self.realm
        self.category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        self.space = do_create_space(
            self.creator,
            name="Launch readiness",
            description="Prepare the program before launch.",
            category=self.category,
        )

    def add_ready_attachment(self) -> SpaceAttachment:
        account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="provider",
            provider_name="Provider",
            external_account_id=uuid4(),
            display_name="Program account",
            created_by=self.creator,
            owner=self.creator,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        source = Source.objects.create(
            realm=self.realm,
            account=account,
            adapter_key="provider",
            provider_key="provider",
            source_type="conversation",
            external_ref="src_0123456789abcdef0123456789abcdef",
            display_name="Program source",
        )
        return SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.TODAY,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            custom_start_date=None,
            attached_by=self.creator,
        )

    def confirm_member(
        self, user: UserProfile, role: str = SpaceMembership.Role.SUBSCRIBER
    ) -> SpaceMembership:
        return do_confirm_space_member(self.space, user, role=role, acting_user=self.creator)

    def test_resolved_observations_create_only_safe_internal_pending_suggestions(self) -> None:
        outsider = self.lear_user("cordelia")
        observations = [
            ResolvedIdentityObservation(
                user_id=self.member.id,
                match_basis="verified_email",
                observation_basis="obs_0123456789abcdef0123456789abcdef",
                suggested_role="contributor",
            ),
            ResolvedIdentityObservation(
                user_id=self.other_member.id,
                match_basis="verified_phone",
                observation_basis="obs_abcdef0123456789abcdef0123456789",
            ),
            ResolvedIdentityObservation(
                user_id=outsider.id,
                match_basis="verified_phone",
                observation_basis="obs_ffffffffffffffffffffffffffffffff",
            ),
            ResolvedIdentityObservation(
                user_id=None,
                match_basis="verified_email",
                observation_basis="obs_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            ),
        ]
        with self.capture_send_event_calls(expected_num_events=1) as events:
            changed = refresh_space_membership_suggestions(
                self.space, observations, acting_user=self.creator
            )

        self.assertEqual(events[0]["users"], [self.creator.id])
        self.assertCountEqual(
            [suggestion.user_id for suggestion in changed], [self.member.id, self.other_member.id]
        )
        self.assertFalse(
            SpaceMembership.objects.filter(space=self.space, user=self.member).exists()
        )
        self.assertFalse(get_accessible_spaces(self.member).filter(id=self.space.id).exists())
        projected = get_space_data(self.space)
        serialized = str(projected)
        self.assertNotIn("observation_basis", serialized)
        self.assertNotIn("0123456789abcdef0123456789abcdef", serialized)
        self.assertFalse(
            SpaceMembershipSuggestion.objects.filter(space=self.space, user_id=outsider.id).exists()
        )

    def test_admin_confirmation_role_change_removal_and_admin_promotion(self) -> None:
        suggestion = refresh_space_membership_suggestions(
            self.space,
            [
                ResolvedIdentityObservation(
                    user_id=self.member.id,
                    match_basis="verified_email",
                    observation_basis="obs_0123456789abcdef0123456789abcdef",
                )
            ],
            acting_user=self.creator,
        )[0]
        membership = do_confirm_space_member(
            self.space,
            self.member,
            role=SpaceMembership.Role.CONTRIBUTOR,
            acting_user=self.creator,
        )
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.state, SpaceMembershipSuggestion.State.CONFIRMED)
        self.assertEqual(get_space_data(self.space)["membership_suggestions"], [])
        self.assertEqual(membership.role, SpaceMembership.Role.CONTRIBUTOR)

        do_confirm_space_member(
            self.space,
            self.member,
            role=SpaceMembership.Role.SUBSCRIBER,
            acting_user=self.creator,
        )
        membership.refresh_from_db()
        self.assertEqual(membership.role, SpaceMembership.Role.SUBSCRIBER)
        do_add_space_administrator(self.space, self.member, acting_user=self.creator)
        self.assertTrue(
            SpaceAdministrator.objects.filter(space=self.space, user=self.member).exists()
        )

        pending = refresh_space_membership_suggestions(
            self.space,
            [
                ResolvedIdentityObservation(
                    user_id=self.other_member.id,
                    match_basis="verified_phone",
                    observation_basis="obs_abcdef0123456789abcdef0123456789",
                )
            ],
            acting_user=self.creator,
        )[0]
        do_remove_space_member(self.space, self.other_member, acting_user=self.creator)
        pending.refresh_from_db()
        self.assertEqual(pending.state, SpaceMembershipSuggestion.State.REMOVED)
        self.assertFalse(
            SpaceMembership.objects.filter(space=self.space, user=self.other_member).exists()
        )

    def test_manual_unobserved_member_and_setup_privacy(self) -> None:
        membership = do_confirm_space_member(
            self.space,
            self.member,
            role=SpaceMembership.Role.SUBSCRIBER,
            acting_user=self.creator,
        )
        self.assertEqual(membership.role, SpaceMembership.Role.SUBSCRIBER)
        self.assertFalse(
            SpaceMembershipSuggestion.objects.filter(space=self.space, user=self.member).exists()
        )
        # A confirmed membership still grants no visibility during private Setup.
        self.assertFalse(get_accessible_spaces(self.member).filter(id=self.space.id).exists())
        do_remove_space_member(self.space, self.member, acting_user=self.creator)
        self.assertFalse(get_accessible_spaces(self.member).filter(id=self.space.id).exists())

    def test_membership_mutation_responses_use_fresh_projection(self) -> None:
        refresh_space_membership_suggestions(
            self.space,
            [
                ResolvedIdentityObservation(
                    user_id=self.member.id,
                    match_basis="verified_email",
                    observation_basis="obs_0123456789abcdef0123456789abcdef",
                )
            ],
            acting_user=self.creator,
        )
        self.login_user(self.creator)

        result = self.client_post(
            f"/json/hover/spaces/{self.space.id}/members",
            {
                "user_id": orjson.dumps(self.member.id).decode(),
                "role": orjson.dumps(SpaceMembership.Role.CONTRIBUTOR).decode(),
            },
        )
        self.assert_json_success(result)
        confirmed_space = orjson.loads(result.content)["space"]
        self.assertEqual(confirmed_space["membership_suggestions"], [])
        self.assertEqual(
            next(
                membership
                for membership in confirmed_space["memberships"]
                if membership["user_id"] == self.member.id
            )["role"],
            SpaceMembership.Role.CONTRIBUTOR,
        )

        result = self.client_delete(
            f"/json/hover/spaces/{self.space.id}/members/{self.member.id}"
        )
        self.assert_json_success(result)
        removed_space = orjson.loads(result.content)["space"]
        self.assertNotIn(
            self.member.id,
            [membership["user_id"] for membership in removed_space["memberships"]],
        )

    def test_launch_is_atomic_quiet_idempotent_and_uses_exact_confirmed_cohort(self) -> None:
        self.add_ready_attachment()
        self.confirm_member(self.member, SpaceMembership.Role.CONTRIBUTOR)
        before_messages = Message.objects.count()

        launched, created = do_launch_space(self.space, acting_user=self.creator)
        self.assertTrue(created)
        self.assertEqual(launched.state, Space.State.LAUNCHED)
        assert launched.stream is not None
        subscriber_ids = set(
            Subscription.objects.filter(
                recipient=launched.stream.recipient, active=True
            ).values_list("user_profile_id", flat=True)
        )
        self.assertEqual(subscriber_ids, {self.creator.id, self.member.id})
        self.assertEqual(Message.objects.count(), before_messages)
        self.assertTrue(get_accessible_spaces(self.member).filter(id=self.space.id).exists())

        replayed, replay_created = do_launch_space(self.space, acting_user=self.creator)
        self.assertFalse(replay_created)
        self.assertEqual(replayed.stream_id, launched.stream_id)
        self.assertEqual(Stream.objects.filter(hover_space=self.space).count(), 1)
        self.assertEqual(
            Subscription.objects.filter(recipient=launched.stream.recipient, active=True).count(), 2
        )

    def test_launch_validation_and_failure_roll_back_every_native_object(self) -> None:
        with self.assertRaisesRegex(JsonableError, "Attach at least one active Source"):
            do_launch_space(self.space, acting_user=self.creator)
        self.add_ready_attachment()
        counts = {
            "streams": Stream.objects.count(),
            "recipients": Recipient.objects.count(),
            "subscriptions": Subscription.objects.count(),
            "groups": UserGroup.objects.count(),
            "audits": RealmAuditLog.objects.count(),
        }
        with (
            patch("hover.actions_spaces.bulk_add_subscriptions", side_effect=RuntimeError("boom")),
            self.assertRaisesRegex(RuntimeError, "boom"),
        ):
            do_launch_space(self.space, acting_user=self.creator)

        self.space.refresh_from_db()
        self.assertEqual(self.space.state, Space.State.SETUP)
        self.assertIsNone(self.space.stream_id)
        self.assertEqual(Stream.objects.count(), counts["streams"])
        self.assertEqual(Recipient.objects.count(), counts["recipients"])
        self.assertEqual(Subscription.objects.count(), counts["subscriptions"])
        self.assertEqual(UserGroup.objects.count(), counts["groups"])
        self.assertEqual(RealmAuditLog.objects.count(), counts["audits"])

    def test_launch_rejects_mixed_active_and_pending_attachments(self) -> None:
        active_attachment = self.add_ready_attachment()
        pending_source = Source.objects.create(
            realm=self.realm,
            account=active_attachment.source.account,
            adapter_key="provider",
            provider_key="provider",
            source_type="conversation",
            external_ref="src_abcdef0123456789abcdef0123456789",
            display_name="Pending source",
        )
        SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=pending_source,
            state=SpaceAttachment.State.PENDING_SYNC,
            history_window=SpaceAttachment.HistoryWindow.TODAY,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            attached_by=self.creator,
        )

        with self.assertRaisesRegex(JsonableError, "not ready for launch"):
            do_launch_space(self.space, acting_user=self.creator)
        self.space.refresh_from_db()
        self.assertEqual(self.space.state, Space.State.SETUP)
        self.assertIsNone(self.space.stream_id)

    def test_launch_rejects_pending_work_and_existing_channel_collision(self) -> None:
        self.add_ready_attachment()
        refresh_space_membership_suggestions(
            self.space,
            [
                ResolvedIdentityObservation(
                    user_id=self.member.id,
                    match_basis="verified_phone",
                    observation_basis="obs_0123456789abcdef0123456789abcdef",
                )
            ],
            acting_user=self.creator,
        )
        with self.assertRaisesRegex(JsonableError, "Resolve all pending"):
            do_launch_space(self.space, acting_user=self.creator)
        do_remove_space_member(self.space, self.member, acting_user=self.creator)
        create_stream_if_needed(self.realm, "LAUNCH READINESS")
        with self.assertRaisesRegex(JsonableError, "already uses this Space name"):
            do_launch_space(self.space, acting_user=self.creator)
