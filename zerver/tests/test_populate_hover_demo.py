from collections import Counter

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from hover.models import EvidenceLink, GeneratedItem, Space, SpaceAdministrator
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
        self.assertEqual(space.created_by, self.example_user("iago"))
        self.assertEqual(
            set(SpaceAdministrator.objects.filter(space=space).values_list("user_id", flat=True)),
            {self.example_user("iago").id, self.example_user("hamlet").id},
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
        generated_items = GeneratedItem.objects.filter(realm=realm, message__in=messages)
        self.assertEqual(generated_items.count(), len(DEMO_POSTS))
        self.assertEqual(
            EvidenceLink.objects.filter(generated_item__in=generated_items).count(),
            sum(len(post.evidence_keys) for post in DEMO_POSTS),
        )
        for post, message in zip(DEMO_POSTS, messages, strict=True):
            generated_item = GeneratedItem.objects.get(message=message)
            self.assertEqual(generated_item.module_key, post.module_key)
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

        stale_message_id = self.send_stream_message(
            UserProfile.objects.get(realm=realm, delivery_email="hover-ai@hover.test"),
            "AIMTO Events",
            "Stale generated update from an earlier fixture version.",
            "Summary",
            read_by_sender=False,
        )
        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).count(),
            len(DEMO_POSTS) + 1,
        )

        call_command("populate_hover_demo", "--realm=zulip", "--viewer-email=hamlet@zulip.com")
        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).count(),
            len(DEMO_POSTS),
        )
        self.assertFalse(Message.objects.filter(id=stale_message_id).exists())
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
