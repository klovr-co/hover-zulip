from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.management.commands.populate_hover_demo import DEMO_POSTS
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
        self.assertEqual(messages.count(), 7)
        self.assertEqual({message.topic_name() for message in messages}, {"Summary"})
        self.assertEqual(
            set(messages.values_list("sender__delivery_email", flat=True)),
            {"hover-ai@hover.test"},
        )

        update = messages.get(content__contains="Event readiness update")
        self.assertIn("Event readiness update", update.content)
        self.assertIn("WhatsApp · Mentors & Volunteers", update.content)
        self.assertIn("WhatsApp · 500 volunteers @ Learnathon", update.content)
        self.assertIn("WhatsApp · Resident Lounge (AIMTO excerpts)", update.content)
        self.assertIn("https://github.com/ashvinpraveen/learnaimto", update.content)
        self.assertIn("https://www.instagram.com/aimto_26/", update.content)
        assert update.rendered_content is not None
        self.assertIn("Event readiness update", update.rendered_content)
        hover_user = UserProfile.objects.get(
            realm=realm, delivery_email="hover-ai@hover.test", is_bot=True
        )
        self.assertEqual(hover_user.full_name, "Hover")

        daily_brief = messages.get(content__contains="Your AIMTO daily brief")
        self.assertIn("Good morning, @**King Hamlet**", daily_brief.content)
        self.assertIn("A good place to start", daily_brief.content)
        self.assertIn("You do not need to reopen those decisions today", daily_brief.content)

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
        self.assert_length(for_you_messages, 4)
        self.assertEqual({message.topic_name() for message in for_you_messages}, {"Summary"})
        saved_messages = [
            user_message.message for user_message in user_messages if user_message.flags.starred
        ]
        self.assertEqual(saved_messages, [update])

        reminders = ScheduledMessage.objects.filter(
            sender=hamlet,
            delivery_type=ScheduledMessage.REMIND,
            delivered=False,
        ).order_by("id")
        self.assertEqual(reminders.count(), 3)
        self.assertEqual(
            set(reminders.values_list("reminder_note", flat=True)),
            {
                "AIMTO · Publish the volunteer briefing agenda",
                "AIMTO · Assign the blue zone owner",
                "AIMTO · Approve final lobby assets",
            },
        )
        self.assertTrue(
            all(reminder.scheduled_timestamp > timezone_now() for reminder in reminders)
        )
        reminder_ids = list(reminders.values_list("id", flat=True))

        stale_message_id = self.send_stream_message(
            UserProfile.objects.get(realm=realm, delivery_email="hover-ai@hover.test"),
            "AIMTO Events",
            "Stale generated update from an earlier fixture version.",
            "Summary",
            read_by_sender=False,
        )
        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).count(), 8
        )

        call_command("populate_hover_demo", "--realm=zulip", "--viewer-email=hamlet@zulip.com")
        self.assertEqual(
            Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).count(), 7
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
