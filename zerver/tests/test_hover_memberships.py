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
from hover.clawer_sync import InMemoryClawerSync
from hover.lib_spaces import get_accessible_spaces, get_space_data
from hover.models import (
    ConnectedAccount,
    Source,
    SourceParticipantBinding,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
    SpaceMembershipSuggestion,
)
from hover.observations import ResolvedIdentityObservation
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.message_flags import do_update_message_flags
from zerver.lib.events import fetch_initial_state_data
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, Recipient, Stream, Subscription, UserMessage, UserProfile
from zerver.models.groups import SystemGroups, UserGroup, UserGroupMembership
from zerver.models.realm_audit_logs import RealmAuditLog


class HoverMembershipsTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.realm = self.creator.realm
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["can_create_spaces_group"])
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
        projected = get_space_data(self.space, viewer=self.creator)
        serialized = str(projected)
        self.assertNotIn("observation_basis", serialized)
        self.assertNotIn("0123456789abcdef0123456789abcdef", serialized)
        self.assertFalse(
            SpaceMembershipSuggestion.objects.filter(space=self.space, user_id=outsider.id).exists()
        )

    def test_verified_observation_persists_only_opaque_source_participant_binding(self) -> None:
        attachment = self.add_ready_attachment()
        observation = ResolvedIdentityObservation(
            user_id=self.member.id,
            match_basis="verified_email",
            observation_basis="obs_0123456789abcdef0123456789abcdef",
            source_ref=attachment.source.external_ref,
            participant_ref=f"person_{'a' * 32}",
        )
        refresh_space_membership_suggestions(self.space, [observation], acting_user=self.creator)
        binding = SourceParticipantBinding.objects.get()
        self.assertEqual(binding.source, attachment.source)
        self.assertEqual(binding.user, self.member)
        self.assertEqual(binding.participant_ref, observation.participant_ref)
        self.assertEqual(binding.match_basis, "verified_email")
        self.assertNotIn("@", str(binding.__dict__))

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
        self.assertEqual(
            get_space_data(self.space, viewer=self.creator)["membership_suggestions"], []
        )
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

        result = self.client_delete(f"/json/hover/spaces/{self.space.id}/members/{self.member.id}")
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

    def test_launched_removal_revokes_every_projection_and_readd_is_idempotent(self) -> None:
        self.add_ready_attachment()
        self.confirm_member(self.member, SpaceMembership.Role.CONTRIBUTOR)
        self.space, _created = do_launch_space(self.space, acting_user=self.creator)
        assert self.space.stream is not None
        historic_message_id = self.send_stream_message(
            self.member,
            self.space.stream.name,
            "Authored before membership removal.",
            "Audit history",
        )
        do_update_message_flags(self.member, "add", "starred", [historic_message_id])

        do_remove_space_member(self.space, self.member, acting_user=self.creator)

        self.assertFalse(
            SpaceMembership.objects.filter(space=self.space, user=self.member).exists()
        )
        self.assertFalse(
            Subscription.objects.get(
                recipient=self.space.stream.recipient, user_profile=self.member
            ).active
        )
        self.assertFalse(
            UserGroupMembership.objects.filter(
                user_group_id=self.space.stream.can_send_message_group_id,
                user_profile=self.member,
            ).exists()
        )
        self.assertEqual(Message.objects.get(id=historic_message_id).sender, self.member)
        historic_user_message = UserMessage.objects.get(
            user_profile=self.member, message_id=historic_message_id
        )
        self.assertTrue(historic_user_message.flags & UserMessage.flags.starred.mask)
        with self.assertRaisesRegex(JsonableError, "Invalid message"):
            access_message(
                self.member,
                historic_message_id,
                is_modifying_message=False,
            )

        self.login_user(self.member)
        self.assertEqual(
            self.assert_json_success(self.client_get("/json/hover/spaces"))["spaces"], []
        )
        self.assert_json_error(
            self.client_get(f"/json/hover/spaces/{self.space.id}"), "Invalid Space ID"
        )
        self.assertEqual(
            fetch_initial_state_data(self.member, realm=self.realm, event_types={"hover_space"})[
                "hover_spaces"
            ],
            [],
        )
        self.assertEqual(
            self.assert_json_success(self.client_get('/json/hover/awareness?surface="for_you"'))[
                "items"
            ],
            [],
        )
        with patch("hover.views_search.get_clawer_sync", return_value=InMemoryClawerSync()):
            search = self.assert_json_success(
                self.client_post("/json/hover/search", {"query": orjson.dumps("Authored").decode()})
            )
        self.assertEqual(search["knowledge"], [])
        self.assertEqual(search["sources"], [])
        self.assertEqual(
            self.assert_json_success(self.client_get("/json/hover/todos"))["todos"], []
        )
        personal_editions = self.assert_json_success(
            self.client_get("/json/hover/personal-editions")
        )
        self.assertEqual(personal_editions["sync_status"], "empty")
        self.assertIsNone(personal_editions["editions"]["morning"])
        self.assertIsNone(personal_editions["editions"]["end_of_day"])

        self.login_user(self.creator)
        for _attempt in range(2):
            result = self.client_post(
                f"/json/hover/spaces/{self.space.id}/members",
                {
                    "user_id": orjson.dumps(self.member.id).decode(),
                    "role": orjson.dumps(SpaceMembership.Role.CONTRIBUTOR).decode(),
                },
            )
            self.assert_json_success(result)
        self.assertEqual(
            SpaceMembership.objects.filter(space=self.space, user=self.member).count(), 1
        )
        self.assertEqual(
            Subscription.objects.filter(
                recipient=self.space.stream.recipient, user_profile=self.member
            ).count(),
            1,
        )
        self.assertTrue(
            Subscription.objects.get(
                recipient=self.space.stream.recipient, user_profile=self.member
            ).active
        )
        self.assertEqual(
            UserGroupMembership.objects.filter(
                user_group_id=self.space.stream.can_send_message_group_id,
                user_profile=self.member,
            ).count(),
            1,
        )
        self.assertEqual(Message.objects.get(id=historic_message_id).sender, self.member)
        self.assertEqual(
            access_message(
                self.member,
                historic_message_id,
                is_modifying_message=False,
            ).id,
            historic_message_id,
        )

        changed_role = self.client_post(
            f"/json/hover/spaces/{self.space.id}/members",
            {
                "user_id": orjson.dumps(self.member.id).decode(),
                "role": orjson.dumps(SpaceMembership.Role.SUBSCRIBER).decode(),
            },
        )
        self.assert_json_success(changed_role)
        self.assertFalse(
            UserGroupMembership.objects.filter(
                user_group_id=self.space.stream.can_send_message_group_id,
                user_profile=self.member,
            ).exists()
        )
        self.assertTrue(
            Subscription.objects.get(
                recipient=self.space.stream.recipient, user_profile=self.member
            ).active
        )

    def test_cross_organization_cannot_mutate_launched_membership(self) -> None:
        self.add_ready_attachment()
        self.confirm_member(self.member)
        self.space, _created = do_launch_space(self.space, acting_user=self.creator)
        outsider = self.lear_user("cordelia")
        self.login_user(outsider)
        result = self.client_delete(
            f"/json/hover/spaces/{self.space.id}/members/{self.member.id}",
            subdomain="lear",
        )
        self.assert_json_error(result, "Invalid Space ID")
        self.assertTrue(SpaceMembership.objects.filter(space=self.space, user=self.member).exists())

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
        with self.assertRaisesRegex(JsonableError, "Another Space already uses this name"):
            do_launch_space(self.space, acting_user=self.creator)
