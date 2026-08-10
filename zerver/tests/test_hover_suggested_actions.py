from datetime import datetime, timezone
from importlib import import_module
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID, uuid4

import orjson
from django.apps import apps
from typing_extensions import override

from hover.actions_memberships import do_confirm_space_member
from hover.actions_spaces import do_create_space, do_launch_space
from hover.actions_suggested_actions import decide_suggested_action
from hover.lib import add_hover_metadata
from hover.models import (
    ConnectedAccount,
    EvidenceLink,
    GeneratedItem,
    Source,
    SpaceAttachment,
    SpaceMembership,
    SuggestedAction,
    SuggestedActionTransition,
    Todo,
    TodoEvent,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.event_schema import check_hover_suggested_action
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class HoverSuggestedActionTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.subscriber = self.example_user("othello")
        self.outsider = self.example_user("cordelia")
        self.realm = self.creator.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        self.space = do_create_space(
            self.creator,
            name="Action lab",
            description="Review accountable work.",
            category=category,
        )
        do_confirm_space_member(
            self.space,
            self.creator,
            role=SpaceMembership.Role.CONTRIBUTOR,
            acting_user=self.creator,
        )
        do_confirm_space_member(
            self.space,
            self.subscriber,
            role=SpaceMembership.Role.SUBSCRIBER,
            acting_user=self.creator,
        )
        account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=uuid4(),
            display_name="Action source",
            created_by=self.creator,
            owner=self.creator,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        source = Source.objects.create(
            realm=self.realm,
            account=account,
            adapter_key="whatsapp",
            provider_key="whatsapp",
            source_type="conversation",
            external_ref="src_0123456789abcdef0123456789abcdef",
            display_name="Action source",
        )
        self.attachment = SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.TODAY,
            history_timezone="UTC",
            history_start_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
            attached_by=self.creator,
        )
        self.space, _ = do_launch_space(self.space, acting_user=self.creator)
        assert self.space.stream is not None
        message_id = self.send_stream_message(
            self.creator,
            self.space.stream.name,
            "## Suggested action\n\nSend the venue plan.",
            "Suggested Actions",
        )
        self.message = Message.objects.get(id=message_id)
        self.original_payload = {
            "contract": "suggested_action",
            "schema_version": "1.0",
            "wording": "Send the venue plan.",
            "proposed_assignee": {
                "kind": "member",
                "ref": "person_0123456789abcdef0123456789abcdef",
                "display_name": "Alex",
            },
            "proposed_due_date": "2026-08-12",
        }
        self.item = GeneratedItem.objects.create(
            realm=self.realm,
            message=self.message,
            attachment=self.attachment,
            publication_id="publication-action",
            idempotency_key="identity-action",
            publication_envelope_hash="a" * 64,
            business_identity="suggestion_fixture",
            output_type=GeneratedItem.OutputType.SUGGESTED_ACTION,
            module_key="suggested_actions",
            module_name="Suggested Actions",
            module_version="v1",
            source_summary="From Action source",
            payload=self.original_payload,
            reviewed_payload=self.original_payload,
        )
        self.action = SuggestedAction.objects.create(
            realm=self.realm,
            space=self.space,
            generated_item=self.item,
            wording="Send the venue plan.",
            proposed_assignee_ref="person_0123456789abcdef0123456789abcdef",
            proposed_assignee_display_name="Alex",
            due_date="2026-08-12",
        )
        self.evidence = EvidenceLink.objects.create(
            generated_item=self.item,
            realm=self.realm,
            source=source,
            evidence_ref="evidence_0123456789abcdef0123456789abcdef",
            position=0,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            display_name="Action source",
        )

    def decide(
        self,
        decision: str,
        *,
        actor: UserProfile | None = None,
        request_id: UUID | None = None,
        expected_version: int | None = None,
        reason: str | None = None,
    ) -> "TestHttpResponse":
        actor = actor or self.subscriber
        self.login_user(actor)
        data: dict[str, str | int] = {
            "decision": decision,
            "request_id": str(request_id or uuid4()),
            "expected_version": (
                expected_version if expected_version is not None else self.action.version
            ),
        }
        if reason is not None:
            data["reason"] = reason
        return self.client_post(
            f"/json/hover/spaces/{self.space.id}/generated-items/{self.item.id}/suggested-action/decisions",
            data,
        )

    def test_approval_is_atomic_idempotent_and_preserves_publication(self) -> None:
        request_id = uuid4()
        original_message = self.message.content
        with self.capture_send_event_calls(expected_num_events=1) as calls:
            first = self.assert_json_success(self.decide("approve", request_id=request_id))
        check_hover_suggested_action("event", {"id": 1, **calls[0]["event"]})
        self.assertCountEqual(calls[0]["users"], [self.creator.id, self.subscriber.id])
        self.assertTrue(first["changed"])
        self.assertEqual(first["suggested_action"]["state"], "approved")
        self.assertEqual(first["suggested_action"]["version"], 2)
        self.assertEqual(first["suggested_action"]["todo"]["state"], "active")
        self.action.refresh_from_db()
        self.assertEqual(self.action.state, SuggestedAction.State.APPROVED)
        self.assertEqual(Todo.objects.count(), 1)
        self.assertEqual(TodoEvent.objects.count(), 1)
        self.assertEqual(SuggestedActionTransition.objects.count(), 1)

        replay = self.assert_json_success(
            self.decide("approve", request_id=request_id, expected_version=1)
        )
        self.assertFalse(replay["changed"])
        self.assertEqual(Todo.objects.count(), 1)
        self.assertEqual(TodoEvent.objects.count(), 1)
        self.assertEqual(SuggestedActionTransition.objects.count(), 1)
        self.item.refresh_from_db()
        self.message.refresh_from_db()
        self.evidence.refresh_from_db()
        self.assertEqual(self.item.payload, self.original_payload)
        self.assertEqual(self.item.publication_envelope_hash, "a" * 64)
        self.assertEqual(self.message.content, original_message)
        self.assertEqual(self.evidence.evidence_ref, "evidence_0123456789abcdef0123456789abcdef")

    def test_not_action_and_restore_append_history(self) -> None:
        dismissed = self.assert_json_success(
            self.decide("not_action", reason="Already covered by the venue team")
        )
        self.assertEqual(dismissed["suggested_action"]["state"], "not_action")
        self.assertEqual(
            dismissed["suggested_action"]["recent_transitions"][0]["reason"],
            "Already covered by the venue team",
        )
        self.action.refresh_from_db()
        restored = self.assert_json_success(
            self.decide("restore", expected_version=self.action.version)
        )
        self.assertEqual(restored["suggested_action"]["state"], "pending")
        self.assertEqual(restored["suggested_action"]["history_count"], 2)
        self.assertEqual(
            list(self.action.transitions.order_by("id").values_list("kind", flat=True)),
            ["not_action", "restore"],
        )
        self.assertFalse(Todo.objects.exists())

    def test_stale_and_illegal_transitions_return_current_projection(self) -> None:
        self.assert_json_success(self.decide("not_action"))
        stale = self.decide("restore", expected_version=1)
        self.assert_json_error(
            stale,
            "This Suggested Action has changed. Review its current state.",
            status_code=409,
        )
        error = orjson.loads(stale.content)
        self.assertEqual(error["suggested_action"]["state"], "not_action")
        self.assertEqual(error["suggested_action"]["version"], 2)
        illegal = self.decide("approve", expected_version=2)
        self.assert_json_error(
            illegal,
            "This Suggested Action has changed. Review its current state.",
            status_code=409,
        )
        self.assertEqual(SuggestedActionTransition.objects.count(), 1)

    def test_non_member_cannot_read_or_decide_action_state(self) -> None:
        denied = self.decide("approve", actor=self.outsider)
        self.assert_json_error(denied, "Invalid generated item ID")
        self.action.refresh_from_db()
        self.assertEqual(self.action.state, SuggestedAction.State.PENDING)
        self.assertFalse(SuggestedActionTransition.objects.exists())

    def test_approval_uses_reviewed_values_but_not_opaque_assignee(self) -> None:
        reviewed = dict(self.original_payload)
        reviewed["wording"] = "Send the final venue plan and safety notes."
        reviewed["proposed_due_date"] = None
        self.item.reviewed_payload = reviewed
        self.item.save(update_fields=["reviewed_payload"])
        response = self.assert_json_success(self.decide("approve"))
        todo = Todo.objects.get()
        self.assertEqual(todo.wording, "Send the final venue plan and safety notes.")
        self.assertIsNone(todo.due_date)
        self.assertIsNone(todo.assignee_id)
        self.assertEqual(
            response["suggested_action"]["source_proposal"]["assignee_ref"],
            "person_0123456789abcdef0123456789abcdef",
        )

    def test_failure_during_approval_rolls_back_every_workflow_row(self) -> None:
        with (
            patch(
                "hover.actions_suggested_actions.TodoEvent.objects.create",
                side_effect=RuntimeError("forced Todo event failure"),
            ),
            self.assertRaisesRegex(RuntimeError, "forced Todo event failure"),
        ):
            decide_suggested_action(
                acting_user=self.subscriber,
                space_id=self.space.id,
                generated_item_id=self.item.id,
                decision="approve",
                request_id=uuid4(),
                expected_version=1,
                reason=None,
            )
        self.action.refresh_from_db()
        self.assertEqual(self.action.state, SuggestedAction.State.PENDING)
        self.assertEqual(self.action.version, 1)
        self.assertFalse(SuggestedActionTransition.objects.exists())
        self.assertFalse(Todo.objects.exists())
        self.assertFalse(TodoEvent.objects.exists())

    def test_migration_backfill_is_strict_review_aware_and_idempotent(self) -> None:
        self.action.delete()
        reviewed = dict(self.original_payload)
        reviewed["wording"] = "Send the reviewed venue plan."
        reviewed["proposed_due_date"] = None
        self.item.reviewed_payload = reviewed
        self.item.save(update_fields=["reviewed_payload"])
        migration = import_module("hover.migrations.0013_suggested_action_workflow")

        migration.backfill_suggested_actions(apps, None)
        action = SuggestedAction.objects.get(generated_item=self.item)
        self.assertEqual(action.wording, "Send the reviewed venue plan.")
        self.assertIsNone(action.due_date)
        self.assertIsNone(action.assignee_id)
        self.assertEqual(
            action.proposed_assignee_ref,
            "person_0123456789abcdef0123456789abcdef",
        )
        migration.backfill_suggested_actions(apps, None)
        self.assertEqual(SuggestedAction.objects.filter(generated_item=self.item).count(), 1)

        action.delete()
        self.item.payload = {}
        self.item.reviewed_payload = {}
        self.item.save(update_fields=["payload", "reviewed_payload"])
        migration.backfill_suggested_actions(apps, None)
        self.assertFalse(SuggestedAction.objects.filter(generated_item=self.item).exists())

        self.item.payload = self.original_payload
        self.item.reviewed_payload = self.original_payload
        self.item.realm = get_realm("zephyr")
        self.item.save(update_fields=["payload", "reviewed_payload", "realm"])
        migration.backfill_suggested_actions(apps, None)
        self.assertFalse(SuggestedAction.objects.filter(generated_item=self.item).exists())

    def test_action_projection_is_limited_to_exact_space_members(self) -> None:
        outsider_message = {"id": self.message.id}
        add_hover_metadata([outsider_message], realm_id=self.realm.id, user_profile=self.outsider)
        self.assertIsNone(outsider_message["hover_generated_item"]["suggested_action"])

        member_message = {"id": self.message.id}
        add_hover_metadata([member_message], realm_id=self.realm.id, user_profile=self.subscriber)
        self.assertEqual(
            member_message["hover_generated_item"]["suggested_action"]["state"],
            "pending",
        )

    def test_h14_review_synchronizes_promoted_values_and_version(self) -> None:
        self.login_user(self.subscriber)
        response = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": orjson.dumps(self.space.stream_id).decode(),
                "topic": self.message.topic_name(),
                "content": "The safety notes are now part of the action.",
                "hover_generated_item_id": self.item.id,
                "hover_response_type": "review",
                "hover_review_field": "wording",
                "hover_review_value": orjson.dumps(
                    "Send the venue plan with safety notes."
                ).decode(),
            },
        )
        self.assert_json_success(response)
        self.item.refresh_from_db()
        self.action.refresh_from_db()
        self.assertEqual(self.item.payload, self.original_payload)
        self.assertEqual(
            self.item.reviewed_payload["wording"], "Send the venue plan with safety notes."
        )
        self.assertEqual(self.action.wording, "Send the venue plan with safety notes.")
        self.assertEqual(self.action.version, 2)
