from datetime import datetime, timedelta, timezone
from uuid import uuid4

from typing_extensions import override

from hover.actions_memberships import do_confirm_space_member
from hover.actions_spaces import do_create_space, do_launch_space
from hover.lib_awareness import get_awareness_projection
from hover.models import (
    ConnectedAccount,
    GeneratedItem,
    Source,
    Space,
    SpaceAttachment,
    SpaceMembership,
    SuggestedAction,
    Todo,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, UserMessage
from zerver.models.groups import SystemGroups


class HoverAwarenessTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.viewer = self.example_user("hamlet")
        self.peer = self.example_user("othello")
        self.outsider = self.example_user("cordelia")
        self.creator = self.example_user("iago")
        # Use the same cached Realm instance that the Space creator consults
        # when evaluating the organization permission below.
        self.realm = self.creator.realm
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["can_create_spaces_group"])
        self.category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.creator
        )
        self.now = datetime(2026, 8, 11, 9, tzinfo=timezone.utc)

    def make_space(self, name: str, *, role: str) -> tuple[SpaceAttachment, Space]:
        space = do_create_space(self.creator, name=name, description="", category=self.category)
        for user in (self.viewer, self.peer):
            do_confirm_space_member(space, user, role=role, acting_user=self.creator)
        account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="github",
            provider_name="GitHub",
            external_account_id=uuid4(),
            display_name=f"{name} account",
            created_by=self.creator,
            owner=self.creator,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        source = Source.objects.create(
            realm=self.realm,
            account=account,
            adapter_key="github",
            provider_key="github",
            source_type="repository",
            external_ref=f"src_{uuid4().hex}",
            display_name=f"{name} repository",
        )
        attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.TODAY,
            history_timezone="UTC",
            history_start_at=self.now,
            attached_by=self.creator,
        )
        space, _ = do_launch_space(space, acting_user=self.creator)
        # The attachment cached the pre-launch Space instance before the
        # launch transaction attached its native stream.
        attachment.space = space
        return attachment, space

    def make_item(
        self,
        attachment: SpaceAttachment,
        *,
        title: str,
        importance: str = "normal",
        minutes: int = 0,
        lineage_key: str | None = None,
        material_change: bool = False,
        output_type: str = GeneratedItem.OutputType.FEED_UPDATE,
    ) -> GeneratedItem:
        space = attachment.space
        assert space.stream is not None
        message_id = self.send_stream_message(
            self.creator, space.stream.name, title, "Developments"
        )
        message = Message.objects.get(id=message_id)
        occurred_at = self.now + timedelta(minutes=minutes)
        Message.objects.filter(id=message_id).update(date_sent=occurred_at)
        message.date_sent = occurred_at
        if output_type == GeneratedItem.OutputType.SUGGESTED_ACTION:
            payload = {
                "contract": "suggested_action",
                "wording": title,
                "proposed_assignee": None,
                "proposed_due_date": None,
            }
        else:
            payload = {"contract": "feed_update", "title": title, "summary": title}
        return GeneratedItem.objects.create(
            realm=self.realm,
            message=message,
            attachment=attachment,
            output_type=output_type,
            module_key="activity_digest",
            module_name="Activity Digest",
            module_version="v1",
            source_summary=f"From {attachment.source.display_name}",
            payload=payload,
            reviewed_payload=payload,
            importance=importance,
            occurred_at=occurred_at,
            published_at=occurred_at,
            lineage_key=lineage_key,
            material_change=material_change,
        )

    def test_for_you_ranking_and_subscriber_noise_boundary(self) -> None:
        contributor_attachment, _ = self.make_space(
            "Contributor work", role=SpaceMembership.Role.CONTRIBUTOR
        )
        subscriber_attachment, _ = self.make_space(
            "Subscriber awareness", role=SpaceMembership.Role.SUBSCRIBER
        )
        normal = self.make_item(contributor_attachment, title="Routine contributor update")
        mentioned = self.make_item(
            contributor_attachment, title="Directly relevant update", minutes=1
        )
        subscriber_normal = self.make_item(
            subscriber_attachment, title="Routine subscriber update", minutes=2
        )
        subscriber_important = self.make_item(
            subscriber_attachment, title="Important subscriber update", importance="high", minutes=3
        )
        mention_row = UserMessage.objects.get(
            user_profile=self.viewer, message_id=mentioned.message_id
        )
        mention_row.flags |= UserMessage.flags.mentioned
        mention_row.save(update_fields=["flags"])

        projection = get_awareness_projection(self.viewer, surface="for_you")

        self.assertEqual(
            [item["message_id"] for item in projection],
            [mentioned.message_id, subscriber_important.message_id, normal.message_id],
        )
        self.assertNotIn(subscriber_normal.message_id, {item["message_id"] for item in projection})
        self.assertIn("mention", projection[0]["reasons"])
        self.assertIn("important", projection[1]["reasons"])

    def test_team_pulse_is_shared_and_permission_filtered(self) -> None:
        attachment, space = self.make_space("Shared work", role=SpaceMembership.Role.CONTRIBUTOR)
        routine = self.make_item(attachment, title="Routine update")
        important = self.make_item(attachment, title="Shared blocker", importance="urgent")
        mention_row = UserMessage.objects.get(
            user_profile=self.viewer, message_id=important.message_id
        )
        mention_row.flags |= UserMessage.flags.mentioned
        mention_row.save(update_fields=["flags"])

        viewer_projection = get_awareness_projection(self.viewer, surface="team_pulse")
        peer_projection = get_awareness_projection(self.peer, surface="team_pulse")

        self.assertEqual(
            [(item["message_id"], item["rank"], item["reasons"]) for item in viewer_projection],
            [(item["message_id"], item["rank"], item["reasons"]) for item in peer_projection],
        )
        self.assertEqual([item["message_id"] for item in viewer_projection], [important.message_id])
        self.assertEqual(get_awareness_projection(self.outsider, surface="team_pulse"), [])

        SpaceMembership.objects.filter(space=space, user=self.viewer).delete()
        self.assertEqual(get_awareness_projection(self.viewer, surface="team_pulse"), [])
        self.assertFalse(
            any(item["message_id"] == routine.message_id for item in viewer_projection)
        )

    def test_linked_development_projects_latest_reviewed_state_and_native_read_state(self) -> None:
        attachment, _ = self.make_space("Lineage work", role=SpaceMembership.Role.CONTRIBUTOR)
        earlier = self.make_item(
            attachment, title="Original plan", importance="high", lineage_key="plan", minutes=1
        )
        latest = self.make_item(
            attachment,
            title="Latest plan",
            importance="high",
            lineage_key="plan",
            minutes=2,
            material_change=True,
        )
        latest.reviewed_payload = {
            "contract": "feed_update",
            "title": "Latest plan",
            "summary": "Confirmed by the team",
        }
        latest.save(update_fields=["reviewed_payload"])
        unread = UserMessage.objects.get(user_profile=self.viewer, message_id=latest.message_id)
        unread.flags &= ~UserMessage.flags.read
        unread.save(update_fields=["flags"])

        projection = get_awareness_projection(self.viewer, surface="for_you")

        self.assertNotIn(earlier.message_id, {item["message_id"] for item in projection})
        projected = next(item for item in projection if item["message_id"] == latest.message_id)
        self.assertEqual(
            projected["hover_generated_item"]["reviewed_payload"]["summary"],
            "Confirmed by the team",
        )
        self.assertEqual(projected["hover_generated_item"]["lineage"]["history_count"], 2)
        self.assertTrue(projected["is_unread"])

    def test_todo_assignment_and_suggested_action_ownership_are_live_inputs(self) -> None:
        attachment, _ = self.make_space("Action work", role=SpaceMembership.Role.CONTRIBUTOR)
        assigned_item = self.make_item(
            attachment,
            title="Deliver the venue plan",
            output_type=GeneratedItem.OutputType.SUGGESTED_ACTION,
        )
        assigned_action = SuggestedAction.objects.create(
            realm=self.realm,
            space=attachment.space,
            generated_item=assigned_item,
            state=SuggestedAction.State.APPROVED,
            wording="Deliver the venue plan",
            assignee=self.peer,
        )
        todo = Todo.objects.create(
            realm=self.realm,
            space=attachment.space,
            suggested_action=assigned_action,
            wording=assigned_action.wording,
            assignee=self.viewer,
            created_by=self.creator,
        )
        owned_item = self.make_item(
            attachment,
            title="Confirm the volunteer roster",
            minutes=1,
            output_type=GeneratedItem.OutputType.SUGGESTED_ACTION,
        )
        SuggestedAction.objects.create(
            realm=self.realm,
            space=attachment.space,
            generated_item=owned_item,
            wording="Confirm the volunteer roster",
            assignee=self.viewer,
        )

        for_you = get_awareness_projection(self.viewer, surface="for_you")

        self.assertEqual(
            [item["message_id"] for item in for_you[:2]],
            [assigned_item.message_id, owned_item.message_id],
        )
        self.assertIn("assignment", for_you[0]["reasons"])
        self.assertNotIn("ownership", for_you[0]["reasons"])
        self.assertIn("ownership", for_you[1]["reasons"])
        self.assertEqual(
            for_you[0]["hover_generated_item"]["suggested_action"]["todo"]["id"],
            todo.id,
        )

        viewer_pulse = get_awareness_projection(self.viewer, surface="team_pulse")
        peer_pulse = get_awareness_projection(self.peer, surface="team_pulse")
        self.assertEqual(
            [(item["message_id"], item["rank"]) for item in viewer_pulse],
            [(item["message_id"], item["rank"]) for item in peer_pulse],
        )
        self.assertEqual([item["message_id"] for item in viewer_pulse], [assigned_item.message_id])
        self.assertIn("active_todo", viewer_pulse[0]["reasons"])

    def test_awareness_endpoint(self) -> None:
        attachment, _ = self.make_space("Endpoint work", role=SpaceMembership.Role.CONTRIBUTOR)
        item = self.make_item(attachment, title="Endpoint item", importance="high")
        self.login_user(self.viewer)

        result = self.client_get('/json/hover/awareness?surface="for_you"')

        payload = self.assert_json_success(result)
        self.assertEqual(payload["surface"], "for_you")
        self.assertEqual(payload["items"][0]["message_id"], item.message_id)
        self.assertEqual(payload["items"][0]["sender_id"], self.creator.id)
