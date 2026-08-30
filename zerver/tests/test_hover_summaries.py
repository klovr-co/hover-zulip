from datetime import time, timedelta
from typing import Any
from uuid import uuid4

import orjson
from django.core.exceptions import ValidationError
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from hover.actions_modules import do_disable_module, ensure_prebuilt_module_catalog
from hover.actions_spaces import do_create_space, do_launch_space
from hover.actions_summaries import SummaryInputSpec, do_create_summary, do_update_summary
from hover.lib import add_hover_metadata
from hover.lib_spaces import get_space_data, space_projection_queryset
from hover.models import (
    ConnectedAccount,
    EvidenceLink,
    GeneratedInputSnapshot,
    GeneratedItem,
    ModuleInstallation,
    ModuleVersion,
    Source,
    SpaceAttachment,
    SpaceMembership,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.streams import bulk_remove_subscriptions
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import access_stream_by_id
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import Message, Subscription
from zerver.models.groups import SystemGroups


class HoverSummariesTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.other_member = self.example_user("othello")
        self.realm = self.creator.realm
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["can_create_spaces_group"])
        category = check_add_channel_folder(
            self.realm, "Programs", "", acting_user=self.example_user("iago")
        )
        self.space = do_create_space(
            self.creator,
            name="Summary authorization",
            description="",
            category=category,
        )
        SpaceMembership.objects.create(
            realm=self.realm,
            space=self.space,
            user=self.other_member,
            role=SpaceMembership.Role.SUBSCRIBER,
            added_by=self.creator,
        )
        account = ConnectedAccount.objects.create(
            realm=self.realm,
            provider_key="github",
            provider_name="GitHub",
            external_account_id=uuid4(),
            display_name="Repositories",
            created_by=self.creator,
            owner=self.creator,
            approval_state=ConnectedAccount.ApprovalState.APPROVED,
        )
        source = Source.objects.create(
            realm=self.realm,
            account=account,
            adapter_key="clawer_sync",
            provider_key="github",
            provider_name="GitHub",
            source_type="repository",
            external_ref=f"src_{'a' * 32}",
            display_name="hover",
        )
        SpaceAttachment.objects.create(
            realm=self.realm,
            space=self.space,
            source=source,
            state=SpaceAttachment.State.ACTIVE,
            history_window=SpaceAttachment.HistoryWindow.LAST_30_DAYS,
            history_timezone="UTC",
            history_start_at=timezone_now() - timedelta(days=30),
            destination_topic="GitHub activity",
            attached_by=self.creator,
        )
        self.space, _created = do_launch_space(self.space, acting_user=self.creator)
        assert self.space.stream is not None
        self.parent_stream = self.space.stream
        ensure_prebuilt_module_catalog(self.realm)
        self.version = ModuleVersion.objects.get(
            definition__realm=self.realm,
            definition__stable_key="conversation_digest",
        )
        self.citation_id = self.send_stream_message(
            self.creator,
            self.parent_stream.name,
            topic_name="Launch plan",
            content="Ship the native topic list.",
        )

    def create_summary(self) -> ModuleInstallation:
        return do_create_summary(
            acting_user=self.creator,
            space=self.space,
            version_id=self.version.id,
            label="Daily launch brief",
            inputs=[
                SummaryInputSpec(
                    topic_name="Launch plan",
                    kind="regular",
                    attachment_id=None,
                )
            ],
            local_time=time(9, 0),
            timezone="Asia/Kuala_Lumpur",
            member_ids=[self.creator.id],
        )

    def test_create_uses_an_independent_private_stream_and_sanitized_projection(self) -> None:
        installation = self.create_summary()
        assert installation.summary_stream is not None
        summary_stream = installation.summary_stream
        self.assertTrue(summary_stream.invite_only)
        self.assertFalse(summary_stream.history_public_to_subscribers)
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=self.creator,
                recipient=summary_stream.recipient,
                active=True,
            ).exists()
        )
        self.assertFalse(
            Subscription.objects.filter(
                user_profile=self.other_member,
                recipient=summary_stream.recipient,
                active=True,
            ).exists()
        )
        access_stream_by_id(self.creator, summary_stream.id)
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.other_member, summary_stream.id)

        projected = space_projection_queryset().get(id=self.space.id)
        creator_data = get_space_data(projected, viewer=self.creator)
        other_data = get_space_data(projected, viewer=self.other_member)
        self.assertEqual(creator_data["topic_descriptors"][-1]["kind"], "summary")
        self.assertNotIn("Daily launch brief", orjson.dumps(other_data).decode())

    def test_grouped_evidence_uses_generation_snapshot_and_rejects_rogue_citation(self) -> None:
        installation = self.create_summary()
        assert installation.summary_stream is not None
        summary_message_id = self.send_stream_message(
            self.creator,
            installation.summary_stream.name,
            topic_name=installation.label,
            content="Daily overview",
        )
        generated_item = GeneratedItem.objects.create(
            realm=self.realm,
            message_id=summary_message_id,
            installation=installation,
            output_type=GeneratedItem.OutputType.DIGEST,
            module_key="conversation_digest",
            module_name="Conversation Digest",
            module_version=self.version.version,
            source_summary="From Launch plan",
        )
        GeneratedInputSnapshot.objects.create(
            generated_item=generated_item,
            stream=self.parent_stream,
            topic_name="Launch plan",
            kind="regular",
            position=0,
        )
        citation = Message.objects.get(id=self.citation_id)
        link = EvidenceLink(
            generated_item=generated_item,
            realm=self.realm,
            citation_message=citation,
            position=0,
            provider_key="",
            provider_name="",
            display_name="",
        )
        link.full_clean()
        link.save()

        message_dict: dict[str, Any] = {"id": generated_item.message_id}
        add_hover_metadata(
            [message_dict], realm_id=self.realm.id, user_profile=self.creator
        )
        self.assertEqual(
            message_dict["hover_generated_item"]["evidence_url"],
            f"/json/hover/spaces/{self.space.id}/generated-items/{generated_item.id}/evidence",
        )

        self.login_user(self.creator)
        payload = self.assert_json_success(
            self.client_post(
                f"/json/hover/spaces/{self.space.id}/generated-items/{generated_item.id}/evidence"
            )
        )
        self.assertEqual(payload["groups"][0]["topic"]["topic_name"], "Launch plan")
        self.assertEqual(payload["groups"][0]["messages"][0]["message_id"], self.citation_id)
        self.assertEqual(payload["forbidden_count"], 0)

        rogue_id = self.send_stream_message(
            self.creator,
            self.parent_stream.name,
            topic_name="Undeclared topic",
            content="Not an input",
        )
        rogue = EvidenceLink(
            generated_item=generated_item,
            realm=self.realm,
            citation_message_id=rogue_id,
            position=1,
            provider_key="",
            provider_name="",
            display_name="",
        )
        with self.assertRaisesRegex(ValidationError, "generation-time input"):
            rogue.full_clean()

        bulk_remove_subscriptions(
            self.realm,
            [self.creator],
            [self.parent_stream],
            acting_user=self.example_user("iago"),
        )
        assert installation.summary_stream is not None
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.creator, installation.summary_stream.id)
        withdrawn = self.client_post(
            f"/json/hover/spaces/{self.space.id}/generated-items/{generated_item.id}/evidence"
        )
        self.assert_json_error(withdrawn, "Invalid message(s)")

    def test_update_and_disable_reconcile_native_authorization(self) -> None:
        installation = self.create_summary()
        assert installation.summary_stream is not None
        updated = do_update_summary(
            acting_user=self.creator,
            installation=installation,
            label="Team launch brief",
            inputs=[
                SummaryInputSpec(
                    topic_name="Launch plan",
                    kind="regular",
                    attachment_id=None,
                )
            ],
            local_time=time(10, 30),
            timezone="UTC",
            member_ids=[self.creator.id, self.other_member.id],
        )
        self.assertEqual(updated.label, "Team launch brief")
        self.assertEqual(updated.policy_revision, 2)
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=self.other_member,
                recipient=installation.summary_stream.recipient,
                active=True,
            ).exists()
        )
        access_stream_by_id(self.other_member, installation.summary_stream.id)

        do_update_summary(
            acting_user=self.creator,
            installation=updated,
            label="Team launch brief",
            inputs=[
                SummaryInputSpec(
                    topic_name="Launch plan",
                    kind="regular",
                    attachment_id=None,
                )
            ],
            local_time=time(10, 30),
            timezone="UTC",
            member_ids=[self.creator.id],
        )
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.other_member, installation.summary_stream.id)

        do_disable_module(updated, acting_user=self.creator)
        with self.assertRaises(JsonableError):
            access_stream_by_id(self.creator, installation.summary_stream.id)
