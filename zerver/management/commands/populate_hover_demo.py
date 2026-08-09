from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.create_user import do_create_user
from zerver.actions.message_send import do_send_messages, internal_prep_stream_message
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_stream_folder,
    do_change_stream_permission,
)
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.streams import create_stream_if_needed
from zerver.models import ChannelFolder, Message, Realm, Subscription, UserProfile
from zerver.models.users import get_user_by_delivery_email


HOVER_AI_EMAIL = "hover-ai@hover.test"


@dataclass(frozen=True)
class DemoPost:
    sender_email: str
    sender_name: str
    topic: str
    content: str
    is_bot: bool = False


DEMO_POSTS = [
    DemoPost(
        sender_email="aisha@hover.test",
        sender_name="Aisha Rahman",
        topic="Volunteer coordination",
        content=(
            "Monday's **9:00 PM volunteer briefing** is confirmed. Please react once you've "
            "read the floor plan so we know every zone has an owner before event day."
        ),
    ),
    DemoPost(
        sender_email="daniel@hover.test",
        sender_name="Daniel Tan",
        topic="Volunteer coordination",
        content=(
            "Day 1 coverage is now filled: three volunteers have taken the open slots. We still "
            "need to confirm Mandarin, Malay, and Tamil support across registration and the builder "
            "area."
        ),
    ),
    DemoPost(
        sender_email="mei@hover.test",
        sender_name="Mei Lin",
        topic="Event operations",
        content=(
            "Sticker quantities are locked at **1,500**: 900 beginner, 300 medium, 300 pro, plus "
            "50 mentor stickers. The remaining floor-plan question is ownership of the blue "
            "discovery and community zone."
        ),
    ),
    DemoPost(
        sender_email="aisha@hover.test",
        sender_name="Aisha Rahman",
        topic="Promotion",
        content=(
            "The lobby artwork needs both **16:9** and **9:16** versions, with **FREE** prominent. "
            "The university leaderboard and certificate page give us a stronger outreach story."
        ),
    ),
    DemoPost(
        sender_email="daniel@hover.test",
        sender_name="Daniel Tan",
        topic="Event operations",
        content=(
            "The website work is moving: certificate and university leaderboard updates are in, "
            "and the homepage refresh is ready for a final event-details pass."
        ),
    ),
    DemoPost(
        sender_email=HOVER_AI_EMAIL,
        sender_name="Hover AI",
        topic="Event readiness",
        is_bot=True,
        content="""## Event readiness update

**12 August · Campus Ampang**

> **Readiness: On track, with two coordination gaps.** Volunteer coverage improved and the public website is moving, but language coverage and one floor-plan zone still need owners.

### What changed

- **Volunteer coverage:** The three open Day 1 roles are filled. The wider mentor group has also grown since the initial call for ten more volunteers.
- **Event operations:** The floor plan now covers registration, the dream wall, builder support, debug/deploy, workshops, and two show-and-tells. Sticker production is locked at 1,500 plus 50 mentor stickers.
- **Public delivery:** Recent LearnAIMTO work added the certificate page, university leaderboard, homepage refresh, partner logos, and event metadata.
- **Promotion:** Outreach is converging on inclusive, multilingual positioning and lobby artwork that makes the free entry unmistakable.

### Needs attention

- Confirm **Mandarin, Malay, and Tamil** coverage at registration and in the builder area.
- Assign a final owner and purpose to the **blue discovery/community zone**.

### Next best actions

1. Publish the Monday 9:00 PM briefing agenda with named zone owners.
2. Lock the 16:9 and 9:16 lobby assets after one final event-details check.
3. Use the leaderboard and certificate flow in the next university outreach push.

**Sources reviewed**

- **WhatsApp · Mentors & Volunteers** — briefing, staffing, floor plan, language coverage, and stickers
- **WhatsApp · 500 volunteers @ Learnathon** — Day 1 assignments and subgroup coordination
- **WhatsApp · Resident Lounge (AIMTO excerpts)** — lobby formats and inclusive promotion direction
- [GitHub · LearnAIMTO](https://github.com/ashvinpraveen/learnaimto) — public-site delivery
- [Instagram · @aimto_26](https://www.instagram.com/aimto_26/) — linked promotion source; post contents not inferred

_AI-generated from linked sources. Verify details before acting._""",
    ),
]


class Command(ZulipBaseCommand):
    help = "Create the sanitized AIMTO Events Hover demo in an existing development realm."

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        self.add_realm_args(parser, required=True)
        parser.add_argument(
            "--viewer-email",
            help="Subscribe this existing user to the private demo Space (defaults to its owner).",
        )

    def get_or_create_demo_user(
        self, post: DemoPost, *, realm: Realm, owner: UserProfile
    ) -> UserProfile:
        try:
            return get_user_by_delivery_email(post.sender_email, realm)
        except UserProfile.DoesNotExist:
            pass

        return do_create_user(
            post.sender_email,
            "hover-demo",
            realm,
            post.sender_name,
            bot_type=UserProfile.DEFAULT_BOT if post.is_bot else None,
            bot_owner=owner if post.is_bot else None,
            acting_user=owner,
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEVELOPMENT:
            raise CommandError("populate_hover_demo is only available in development.")

        realm = self.get_realm(options)
        assert realm is not None

        owner = realm.get_human_admin_users().order_by("id").first()
        if owner is None:
            raise CommandError("The demo realm needs an active human administrator.")

        viewer = owner
        if options["viewer_email"] is not None:
            try:
                viewer = get_user_by_delivery_email(options["viewer_email"], realm)
            except UserProfile.DoesNotExist:
                raise CommandError(
                    f"No user with email {options['viewer_email']} exists in {realm.string_id}."
                )

        folder = ChannelFolder.objects.filter(
            realm=realm, name__iexact="Events", is_archived=False
        ).first()
        if folder is None:
            folder = check_add_channel_folder(
                realm,
                "Events",
                "Time-bound programs and live experiences.",
                acting_user=owner,
            )

        stream, _created = create_stream_if_needed(
            realm,
            "AIMTO Events",
            stream_description=(
                "Human coordination and source-backed AI updates for the AIMTO Learn-a-thon."
            ),
            invite_only=True,
            folder=folder,
            acting_user=owner,
        )
        if stream.folder_id != folder.id:
            do_change_stream_folder(stream, folder, acting_user=owner)
        if not stream.invite_only or stream.history_public_to_subscribers or stream.is_web_public:
            do_change_stream_permission(
                stream,
                invite_only=True,
                history_public_to_subscribers=False,
                is_web_public=False,
                acting_user=owner,
            )

        users_by_email: dict[str, UserProfile] = {}
        for post in DEMO_POSTS:
            users_by_email[post.sender_email] = self.get_or_create_demo_user(
                post, realm=realm, owner=owner
            )

        subscribers_by_id = {user.id: user for user in users_by_email.values()}
        subscribers_by_id[owner.id] = owner
        subscribers_by_id[viewer.id] = viewer
        subscribers = list(subscribers_by_id.values())

        existing_subscribers = [
            subscription.user_profile
            for subscription in Subscription.objects.filter(
                recipient=stream.recipient, active=True
            ).select_related("user_profile")
        ]
        extra_subscribers = [
            user for user in existing_subscribers if user.id not in subscribers_by_id
        ]
        if extra_subscribers:
            bulk_remove_subscriptions(realm, extra_subscribers, [stream], acting_user=owner)
        bulk_add_subscriptions(realm, [stream], subscribers, acting_user=owner)

        pending_messages = []
        for post in DEMO_POSTS:
            sender = users_by_email[post.sender_email]
            if Message.objects.filter(
                recipient=stream.recipient,
                sender=sender,
                subject=post.topic,
                content=post.content,
            ).exists():
                continue
            pending_messages.append(
                internal_prep_stream_message(sender, stream, post.topic, post.content)
            )

        if pending_messages:
            do_send_messages(pending_messages)

        self.stdout.write(
            self.style.SUCCESS(
                f"AIMTO Events is ready with {len(DEMO_POSTS)} native Hover posts in {realm.string_id}."
            )
        )
