from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Stream, Subscription, UserProfile
from zerver.models.realms import get_realm


class PopulateHoverDemoTest(ZulipTestCase):
    @override_settings(DEVELOPMENT=False)
    def test_command_is_rejected_outside_development(self) -> None:
        with self.assertRaisesRegex(CommandError, "only available in development"):
            call_command("populate_hover_demo", "--realm=zulip")

    def test_command_builds_native_aimto_space_idempotently(self) -> None:
        call_command("populate_hover_demo", "--realm=zulip")

        realm = get_realm("zulip")
        stream = Stream.objects.select_related("folder", "recipient").get(
            realm=realm, name="AIMTO Events"
        )
        self.assertEqual(stream.folder.name, "Events")
        self.assertIn("human coordination", stream.description.lower())
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=self.example_user("hamlet"), recipient=stream.recipient, active=True
            ).exists()
        )

        messages = Message.objects.filter(recipient=stream.recipient).order_by("id")
        self.assertEqual(messages.count(), 6)
        self.assertEqual(
            set(messages.values_list("subject", flat=True)),
            {"Event operations", "Event readiness", "Promotion", "Volunteer coordination"},
        )

        update = messages.get(sender__delivery_email="hover-ai@hover.test")
        self.assertIn("Event readiness update", update.content)
        self.assertIn("WhatsApp · Mentors & Volunteers", update.content)
        self.assertIn("WhatsApp · 500 volunteers @ Learnathon", update.content)
        self.assertIn("https://github.com/ashvinpraveen/learnaimto", update.content)
        self.assertIn("https://www.instagram.com/aimto_26/", update.content)
        self.assertIn("Event readiness update", update.rendered_content)
        self.assertTrue(
            UserProfile.objects.filter(
                realm=realm, delivery_email="hover-ai@hover.test", is_bot=True
            ).exists()
        )

        call_command("populate_hover_demo", "--realm=zulip")
        self.assertEqual(Message.objects.filter(recipient=stream.recipient).count(), 6)
