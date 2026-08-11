import datetime
from collections import Counter

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    EvidenceLink,
    GeneratedItem,
    ModuleInstallation,
    Source,
    SourceCapability,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
)
from hover.publication_contracts import SuggestedActionPayload
from zerver.lib.test_classes import ZulipTestCase
from zerver.management.commands.populate_hover_demo import DEMO_POSTS, MODULE_NAMES
from zerver.models import Message, ScheduledMessage, Stream, Subscription, UserMessage, UserProfile
from zerver.models.realms import get_realm


class PopulateHoverDemoTest(ZulipTestCase):
    @override_settings(DEVELOPMENT=False)
    def test_command_is_rejected_outside_development(self) -> None:
        with self.assertRaisesRegex(CommandError, "only available in development"):
            call_command("populate_hover_demo", "--realm=zulip")

    def test_command_builds_native_aimto_space_idempotently(self) -> None:
        call_command("populate_hover_demo", "--realm=zulip", "--viewer-email=hamlet@zulip.com")

        realm = get_realm("zulip")
        stream = Stream.objects.select_related("folder", "recipient").get(
            realm=realm, name="AIMTO Events"
        )
        assert stream.folder is not None
        self.assertEqual(stream.folder.name, "Events")
        self.assertTrue(stream.invite_only)
        self.assertFalse(stream.history_public_to_subscribers)
        self.assertFalse(stream.is_web_public)
        self.assertTrue(realm.hover_enabled)
        space = Space.objects.get(realm=realm, name="AIMTO Events")
        self.assertEqual(space.state, Space.State.LAUNCHED)
        self.assertEqual(space.category, stream.folder)
        self.assertEqual(space.stream, stream)
        owner = realm.get_human_admin_users().order_by("id").first()
        assert owner is not None
        self.assertEqual(space.created_by, owner)
        self.assertEqual(
            set(SpaceAdministrator.objects.filter(space=space).values_list("user_id", flat=True)),
            {owner.id, self.example_user("hamlet").id},
        )
        self.assertEqual(
            dict(
                SpaceMembership.objects.filter(space=space).values_list(
                    "user__delivery_email", "role"
                )
            ),
            {
                owner.delivery_email: SpaceMembership.Role.CONTRIBUTOR,
                "hamlet@zulip.com": SpaceMembership.Role.SUBSCRIBER,
            },
        )
        self.assertIn("source-backed hover updates", stream.description.lower())
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=self.example_user("hamlet"), recipient=stream.recipient, active=True
            ).exists()
        )
        self.assertFalse(
            Subscription.objects.filter(
                user_profile=self.example_user("othello"), recipient=stream.recipient, active=True
            ).exists()
        )

        messages = Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).order_by(
            "id"
        )
        self.assertEqual(messages.count(), len(DEMO_POSTS))
        attachments = SpaceAttachment.objects.filter(space=space).select_related("source__account")
        self.assertEqual(attachments.count(), 5)
        self.assertFalse(attachments.exclude(state=SpaceAttachment.State.ACTIVE).exists())
        source_ids = set(attachments.values_list("source_id", flat=True))
        self.assert_length(source_ids, 5)
        self.assertEqual(SourceCapability.objects.filter(source_id__in=source_ids).count(), 5)
        self.assertEqual(
            set(
                SourceCapability.objects.filter(source_id__in=source_ids).values_list(
                    "capability", flat=True
                )
            ),
            {"message_history"},
        )
        account_ids = set(attachments.values_list("source__account_id", flat=True))
        self.assert_length(account_ids, 3)
        self.assertFalse(
            ConnectedAccount.objects.filter(id__in=account_ids)
            .exclude(
                approval_state=ConnectedAccount.ApprovalState.APPROVED,
                health_status=ConnectedAccount.HealthStatus.HEALTHY,
            )
            .exists()
        )
        self.assertEqual(
            ConnectedAccountGrant.objects.filter(
                account_id__in=account_ids,
                user_id__in=[owner.id, self.example_user("hamlet").id],
                state=ConnectedAccountGrant.State.ACTIVE,
                all_selectors=True,
            ).count(),
            6,
        )
        source_projection = "\n".join(
            "|".join(fields)
            for fields in Source.objects.filter(id__in=source_ids)
            .order_by("id")
            .values_list("external_ref", "display_name", "external_url")
        )
        self.assertNotIn("+60", source_projection)
        self.assertNotIn("@g.us", source_projection)
        self.assertNotIn("@lid", source_projection)
        self.assertTrue(
            all(
                len(source_ref) == 36 and source_ref.startswith("src_")
                for source_ref in Source.objects.filter(id__in=source_ids).values_list(
                    "external_ref", flat=True
                )
            )
        )

        installations = ModuleInstallation.objects.filter(space=space).select_related(
            "version__definition"
        )
        self.assertEqual(installations.count(), len(MODULE_NAMES))
        self.assertFalse(installations.exclude(state=ModuleInstallation.State.ENABLED).exists())
        self.assertEqual(
            set(installations.values_list("version__definition__stable_key", flat=True)),
            set(MODULE_NAMES),
        )
        self.assertEqual(
            installations.filter(triggers__supported_trigger__kind="manual").count(), 6
        )
        self.assertEqual(installations.filter(bindings__isnull=False).distinct().count(), 6)

        generated_items = GeneratedItem.objects.filter(
            realm=realm, message__in=messages
        ).select_related("attachment__source")
        self.assertEqual(generated_items.count(), len(DEMO_POSTS))
        self.assertEqual(
            EvidenceLink.objects.filter(generated_item__in=generated_items).count(),
            sum(len(post.evidence_keys) for post in DEMO_POSTS),
        )
        for post_number, (post, message) in enumerate(
            zip(DEMO_POSTS, messages, strict=True), start=1
        ):
            generated_item = GeneratedItem.objects.get(message=message)
            self.assertEqual(generated_item.module_key, post.module_key)
            self.assertEqual(generated_item.module_version, "1.0.0")
            self.assertEqual(
                generated_item.publication_id, f"aimto-demo-publication-{post_number:02}"
            )
            self.assertEqual(generated_item.idempotency_key, f"aimto-demo-v1-{post_number:02}")
            self.assertEqual(
                generated_item.business_identity,
                f"aimto-demo:{post.module_key}:{post_number:02}",
            )
            self.assertEqual(generated_item.lineage_key, generated_item.business_identity)
            self.assert_length(generated_item.publication_envelope_hash, 64)
            self.assertEqual(generated_item.payload["contract"], generated_item.output_type)
            self.assertEqual(generated_item.payload["schema_version"], "1.0")
            if hasattr(generated_item, "reviewed_payload"):
                self.assertEqual(generated_item.reviewed_payload, generated_item.payload)
            self.assertEqual(generated_item.covered_end_at, post.sent_at)
            self.assertEqual(
                generated_item.occurred_at, post.sent_at - datetime.timedelta(minutes=5)
            )
            self.assertEqual(
                generated_item.generated_at, post.sent_at - datetime.timedelta(minutes=1)
            )
            self.assertEqual(generated_item.published_at, post.sent_at)
            attachment = generated_item.attachment
            assert attachment is not None
            self.assertEqual(
                attachment.source_id,
                generated_item.evidence_links.get(position=0).source_id,
            )
            self.assertFalse(generated_item.evidence_links.filter(source__isnull=True).exists())
            self.assertEqual(
                list(generated_item.evidence_links.values_list("position", flat=True)),
                list(range(len(post.evidence_keys))),
            )
        self.assertFalse(messages.filter(search_tsvector__isnull=True).exists())
        self.assertEqual(
            {message.topic_name() for message in messages},
            set(MODULE_NAMES.values()),
        )
        self.assertEqual(
            set(messages.values_list("sender__delivery_email", flat=True)),
            {"hover-ai@hover.test"},
        )

        module_counts = Counter(post.module_key for post in DEMO_POSTS)
        self.assertEqual(
            module_counts,
            {
                "conversation_digest": 3,
                "progress_tracker": 4,
                "suggested_actions": 3,
                "decisions": 3,
                "marketing_digest": 3,
                "topic_analysis": 2,
            },
        )
        for module_key, module_name in MODULE_NAMES.items():
            module_messages = [
                message for message in messages if message.topic_name() == module_name
            ]
            self.assert_length(module_messages, module_counts[module_key])

        suggested_actions = [
            message for message in messages if message.topic_name() == "Suggested Actions"
        ]
        self.assert_length(suggested_actions, 3)
        self.assertTrue(
            all("Status: Awaiting confirmation" in message.content for message in suggested_actions)
        )
        for message in suggested_actions:
            item = GeneratedItem.objects.get(message=message)
            proposal = SuggestedActionPayload.model_validate(item.payload)
            self.assertEqual(proposal.contract, "suggested_action")
            self.assertEqual(item.reviewed_payload, item.payload)

        marketing_posts = [
            message for message in messages if message.topic_name() == "Marketing Digest"
        ]
        self.assertTrue(
            any(
                "https://github.com/ashvinpraveen/learnaimto" in post.content
                for post in marketing_posts
            )
        )
        self.assertTrue(
            any("https://www.instagram.com/aimto_26/" in post.content for post in marketing_posts)
        )
        self.assertTrue(
            any("https://luma.com/zkxj8z7b" in post.content for post in marketing_posts)
        )
        self.assertFalse(
            any("AICB lobby poster delivery" in post.content for post in marketing_posts)
        )

        progress_posts = [
            message for message in messages if message.topic_name() == "Progress Tracker"
        ]
        poster_progress = next(
            message for message in progress_posts if "AICB lobby poster delivery" in message.content
        )
        self.assertIn("**Owner**\nMaxine.", poster_progress.content)
        self.assertIn("Status: In progress", poster_progress.content)
        self.assertIn("16:9 and 9:16", poster_progress.content)
        self.assertIn("WhatsApp · Resident Lounge", poster_progress.content)

        all_content = "\n".join(messages.values_list("content", flat=True))
        self.assertNotIn("+60", all_content)
        self.assertIn("Mandarin", all_content)
        self.assertIn("Malay", all_content)
        self.assertIn("Tamil", all_content)
        self.assertIn("16:9", all_content)
        self.assertIn("9:16", all_content)
        hover_user = UserProfile.objects.get(
            realm=realm, delivery_email="hover-ai@hover.test", is_bot=True
        )
        self.assertEqual(hover_user.full_name, "Hover")

        self.assertEqual(
            list(messages.values_list("date_sent", flat=True)),
            [post.sent_at for post in DEMO_POSTS],
        )

        hamlet = self.example_user("hamlet")
        user_messages = UserMessage.objects.filter(
            user_profile=hamlet, message__recipient=stream.recipient
        ).select_related("message")
        for_you_messages = [
            user_message.message for user_message in user_messages if not user_message.flags.read
        ]
        self.assert_length(for_you_messages, sum(post.for_you for post in DEMO_POSTS))
        self.assertEqual(
            {message.topic_name() for message in for_you_messages},
            {MODULE_NAMES[post.module_key] for post in DEMO_POSTS if post.for_you},
        )
        saved_messages = [
            user_message.message for user_message in user_messages if user_message.flags.starred
        ]
        self.assert_length(saved_messages, sum(post.saved for post in DEMO_POSTS))

        reminders = ScheduledMessage.objects.filter(
            sender=hamlet,
            delivery_type=ScheduledMessage.REMIND,
            delivered=False,
        ).order_by("id")
        self.assertEqual(reminders.count(), 0)
        reminder_ids = list(reminders.values_list("id", flat=True))
        live_record_ids = {
            "sources": set(source_ids),
            "attachments": set(attachments.values_list("id", flat=True)),
            "installations": set(installations.values_list("id", flat=True)),
        }

        stale_message_id = self.send_stream_message(
            UserProfile.objects.get(realm=realm, delivery_email="hover-ai@hover.test"),
            "AIMTO Events",
            "Stale generated update from an earlier fixture version.",
            "Summary",
            read_by_sender=False,
        )
        teammate_message_id = self.send_stream_message(
            self.example_user("hamlet"),
            "AIMTO Events",
            "Keep this teammate follow-up when the fixture is refreshed.",
            "Summary",
        )
        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).count(),
            len(DEMO_POSTS) + 2,
        )

        call_command("populate_hover_demo", "--realm=zulip", "--viewer-email=hamlet@zulip.com")
        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).count(),
            len(DEMO_POSTS) + 1,
        )
        self.assertFalse(Message.objects.filter(id=stale_message_id).exists())
        self.assertTrue(Message.objects.filter(id=teammate_message_id).exists())
        self.assertEqual(
            set(SpaceAttachment.objects.filter(space=space).values_list("source_id", flat=True)),
            live_record_ids["sources"],
        )
        self.assertEqual(
            set(SpaceAttachment.objects.filter(space=space).values_list("id", flat=True)),
            live_record_ids["attachments"],
        )
        self.assertEqual(
            set(ModuleInstallation.objects.filter(space=space).values_list("id", flat=True)),
            live_record_ids["installations"],
        )
        self.assertEqual(
            list(
                ScheduledMessage.objects.filter(
                    sender=hamlet,
                    delivery_type=ScheduledMessage.REMIND,
                    delivered=False,
                )
                .order_by("id")
                .values_list("id", flat=True)
            ),
            reminder_ids,
        )

    def test_command_rejects_unknown_viewer(self) -> None:
        with self.assertRaisesRegex(CommandError, "No user with email nobody@example.com"):
            call_command(
                "populate_hover_demo", "--realm=zulip", "--viewer-email=nobody@example.com"
            )
