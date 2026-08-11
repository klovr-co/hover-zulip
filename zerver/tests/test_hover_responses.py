from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from unittest import mock
from uuid import uuid4

import orjson
from django.http import HttpResponse
from typing_extensions import override

from hover.actions_memberships import do_confirm_space_member
from hover.actions_spaces import do_create_space, do_launch_space
from hover.lib import add_hover_metadata
from hover.models import (
    ConnectedAccount,
    EvidenceLink,
    GeneratedItem,
    Response,
    Revision,
    Source,
    SpaceAttachment,
    SpaceMembership,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock, dummy_handler
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message
from zerver.models.groups import SystemGroups
from zerver.tornado.views import get_events

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class HoverResponseTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.reviewer = self.example_user("othello")
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
            name="Review lab",
            description="Review generated updates.",
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
            self.reviewer,
            role=SpaceMembership.Role.SUBSCRIBER,
            acting_user=self.creator,
        )
        account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            external_account_id=uuid4(),
            display_name="Review source",
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
            display_name="Review source",
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
        root_message_id = self.send_stream_message(
            self.creator,
            self.space.stream.name,
            "The venue is Hall A on Friday.",
            "Event plan",
        )
        self.root_message = Message.objects.get(id=root_message_id)
        self.item = GeneratedItem.objects.create(
            realm=self.realm,
            message=self.root_message,
            attachment=self.attachment,
            output_type=GeneratedItem.OutputType.PROGRESS_UPDATE,
            module_key="progress_tracker",
            module_name="Progress Tracker",
            module_version="v1",
            source_summary="From Review source",
            payload={"venue": "Hall A", "date": "Friday"},
            reviewed_payload={"venue": "Hall A", "date": "Friday"},
        )
        self.evidence = EvidenceLink.objects.create(
            generated_item=self.item,
            realm=self.realm,
            source=source,
            evidence_ref="evidence_0123456789abcdef0123456789abcdef",
            position=0,
            provider_key="whatsapp",
            provider_name="WhatsApp",
            display_name="Original evidence",
        )

    def send_response(
        self,
        *,
        response_type: str,
        content: str,
        field: str | None = None,
        value: str | None = None,
        topic: str = "Event plan",
    ) -> "TestHttpResponse":
        self.login_user(self.reviewer)
        data = {
            "type": "channel",
            "to": orjson.dumps(self.space.stream_id).decode(),
            "topic": topic,
            "content": content,
            "hover_generated_item_id": self.item.id,
            "hover_response_type": response_type,
        }
        if field is not None:
            data["hover_review_field"] = field
        if value is not None:
            data["hover_review_value"] = value
        return self.client_post("/json/messages", data)

    def get_events(self, post_data: dict[str, Any]) -> HttpResponse:
        request = HostRequestMock(post_data, self.reviewer, tornado_handler=dummy_handler)
        return get_events(request, self.reviewer)

    def test_reply_is_native_context_without_state_change(self) -> None:
        result = self.send_response(response_type="reply", content="I will confirm access.")
        response_data = self.assert_json_success(result)
        response = Response.objects.get(message_id=response_data["id"])
        self.assertEqual(response.response_type, Response.ResponseType.REPLY)
        self.assertEqual(response.message.sender, self.reviewer)
        self.assertEqual(response.message.recipient, self.root_message.recipient)
        self.assertEqual(response.message.topic_name(), self.root_message.topic_name())
        self.item.refresh_from_db()
        self.assertEqual(self.item.reviewed_payload, self.item.payload)
        self.assertEqual(Revision.objects.count(), 0)

    def test_explicit_review_applies_once_and_preserves_originals(self) -> None:
        result = self.send_response(
            response_type="review",
            content="Confirmed with the venue team.",
            field="venue",
            value='"Hall B"',
        )
        response_data = self.assert_json_success(result)
        self.assertEqual(
            response_data["hover_response"],
            {"type": "review", "clarification_required": False},
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.payload, {"venue": "Hall A", "date": "Friday"})
        self.assertEqual(self.item.reviewed_payload, {"venue": "Hall B", "date": "Friday"})
        revision = Revision.objects.get()
        self.assertEqual(revision.previous_value, "Hall A")
        self.assertEqual(revision.new_value, "Hall B")
        self.assertEqual(revision.actor, self.reviewer)
        self.assertEqual(revision.reason, "Confirmed with the venue team.")
        self.assertEqual(revision.response.message_id, response_data["id"])
        self.evidence.refresh_from_db()
        self.assertEqual(self.evidence.display_name, "Original evidence")

        message_dict = {"id": response_data["id"]}
        add_hover_metadata([message_dict], realm_id=self.realm.id)
        metadata = message_dict["hover_response"]
        self.assertEqual(metadata["root_message_id"], self.root_message.id)
        self.assertEqual(metadata["generated_item"]["reviewed_payload"]["venue"], "Hall B")
        self.assertEqual(metadata["generated_item"]["revisions"][0]["previous_value"], "Hall A")

    def test_review_message_event_contains_committed_response_metadata(self) -> None:
        registration = self.get_events(
            {
                "apply_markdown": orjson.dumps(True).decode(),
                "client_gravatar": orjson.dumps(True).decode(),
                "event_types": orjson.dumps(["message"]).decode(),
                "user_client": "website",
                "dont_block": orjson.dumps(True).decode(),
            }
        )
        self.assert_json_success(registration)
        queue_id = orjson.loads(registration.content)["queue_id"]

        with self.captureOnCommitCallbacks(execute=True):
            result = self.send_response(
                response_type="review",
                content="Confirmed with the venue team.",
                field="venue",
                value='"Hall B"',
            )
        response_data = self.assert_json_success(result)

        fetched = self.get_events(
            {
                "queue_id": queue_id,
                "user_client": "website",
                "last_event_id": -1,
                "dont_block": orjson.dumps(True).decode(),
            }
        )
        self.assert_json_success(fetched)
        events = orjson.loads(fetched.content)["events"]
        self.assert_length(events, 1)
        message = events[0]["message"]
        self.assertEqual(message["id"], response_data["id"])
        self.assertEqual(message["hover_response"]["type"], "review")
        self.assertEqual(message["hover_response"]["root_message_id"], self.root_message.id)
        self.assertEqual(
            message["hover_response"]["generated_item"]["reviewed_payload"]["venue"],
            "Hall B",
        )

    def test_response_exists_before_message_event_is_queued(self) -> None:
        event_saw_response = False

        def check_response_before_queue(
            _realm: object, event: dict[str, Any], _users: object
        ) -> None:
            nonlocal event_saw_response
            event_saw_response = Response.objects.filter(message_id=event["message"]).exists()

        with mock.patch(
            "zerver.actions.message_send.send_event_on_commit",
            side_effect=check_response_before_queue,
        ):
            result = self.send_response(response_type="reply", content="Event ordering check.")

        self.assert_json_success(result)
        self.assertTrue(event_saw_response)

    def test_ambiguous_review_requests_clarification_without_mutation(self) -> None:
        result = self.send_response(
            response_type="review",
            content="This needs to change, but I am not sure which field.",
        )
        response_data = self.assert_json_success(result)
        response = Response.objects.get(message_id=response_data["id"])
        self.assertTrue(response.clarification_required)
        self.item.refresh_from_db()
        self.assertEqual(self.item.reviewed_payload, self.item.payload)
        self.assertFalse(Revision.objects.exists())

    def test_typo_field_is_ambiguous_not_silently_added(self) -> None:
        result = self.send_response(
            response_type="review",
            content="Move the venue.",
            field="veune",
            value='"Hall B"',
        )
        response_data = self.assert_json_success(result)
        self.assertTrue(response_data["hover_response"]["clarification_required"])
        self.item.refresh_from_db()
        self.assertNotIn("veune", self.item.reviewed_payload)

    def test_non_member_and_wrong_topic_cannot_link_response(self) -> None:
        before_count = Message.objects.count()
        self.login_user(self.outsider)
        denied = self.client_post(
            "/json/messages",
            {
                "type": "channel",
                "to": orjson.dumps(self.space.stream_id).decode(),
                "topic": "Event plan",
                "content": "Unauthorized review",
                "hover_generated_item_id": self.item.id,
                "hover_response_type": "review",
            },
        )
        self.assert_json_error(denied, "Invalid generated item ID")
        self.assertEqual(Message.objects.count(), before_count)

        wrong_topic = self.send_response(
            response_type="reply", content="Wrong thread", topic="Another topic"
        )
        self.assert_json_error(
            wrong_topic, "Hover responses must be sent beneath their generated update."
        )
        self.assertEqual(Message.objects.count(), before_count)
        self.assertFalse(Response.objects.exists())
