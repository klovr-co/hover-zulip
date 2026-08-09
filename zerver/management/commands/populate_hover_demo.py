import datetime
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.create_user import do_create_user
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.message_send import do_send_messages, internal_prep_stream_message
from zerver.actions.reminders import do_delete_reminder, schedule_reminder_for_message
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_stream_folder,
    do_change_stream_permission,
)
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.streams import create_stream_if_needed
from zerver.models import (
    ChannelFolder,
    Message,
    Realm,
    ScheduledMessage,
    Stream,
    Subscription,
    UserProfile,
)
from zerver.models.clients import get_client
from zerver.models.users import get_user_by_delivery_email


HOVER_AI_EMAIL = "hover-ai@hover.test"


@dataclass(frozen=True)
class DemoPost:
    sender_email: str
    sender_name: str
    topic: str
    content: str
    sent_at: datetime.datetime
    is_bot: bool = False
    for_you: bool = False
    todo_note: str | None = None
    todo_due_after: datetime.timedelta | None = None


def demo_time(day: int, hour: int, minute: int) -> datetime.datetime:
    return datetime.datetime(2026, 8, day, hour, minute, tzinfo=datetime.timezone.utc)


DEMO_POSTS = [
    DemoPost(
        sender_email="aisha@hover.test",
        sender_name="Aisha Rahman",
        topic="Volunteer coordination",
        content=(
            "Monday's **9:00 PM volunteer briefing** is confirmed. Please react once you've "
            "read the floor plan so we know every zone has an owner before event day."
        ),
        sent_at=demo_time(7, 1, 18),
        for_you=True,
        todo_note="AIMTO · Publish the volunteer briefing agenda",
        todo_due_after=datetime.timedelta(hours=8),
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
        sent_at=demo_time(7, 6, 42),
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
        sent_at=demo_time(8, 2, 5),
        for_you=True,
        todo_note="AIMTO · Assign the blue zone owner",
        todo_due_after=datetime.timedelta(days=1, hours=3),
    ),
    DemoPost(
        sender_email="aisha@hover.test",
        sender_name="Aisha Rahman",
        topic="Promotion",
        content=(
            "The lobby artwork needs both **16:9** and **9:16** versions, with **FREE** prominent. "
            "The university leaderboard and certificate page give us a stronger outreach story."
        ),
        sent_at=demo_time(8, 8, 30),
        todo_note="AIMTO · Approve final lobby assets",
        todo_due_after=datetime.timedelta(days=2),
    ),
    DemoPost(
        sender_email="daniel@hover.test",
        sender_name="Daniel Tan",
        topic="Event operations",
        content=(
            "The website work is moving: certificate and university leaderboard updates are in, "
            "and the homepage refresh is ready for a final event-details pass."
        ),
        sent_at=demo_time(9, 3, 20),
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
        sent_at=demo_time(10, 0, 15),
        for_you=True,
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

    def reconcile_demo_message(
        self,
        post: DemoPost,
        *,
        stream: Stream,
        sender: UserProfile,
        owner: UserProfile,
    ) -> Message:
        candidates = Message.objects.filter(
            recipient=stream.recipient,
            sender=sender,
            subject=post.topic,
        ).order_by("id")
        message = candidates.filter(content=post.content).first()

        if message is None:
            send_request = internal_prep_stream_message(
                sender,
                stream,
                post.topic,
                post.content,
                forged=True,
                forged_timestamp=post.sent_at.timestamp(),
                acting_user=owner,
            )
            assert send_request is not None
            message_id = do_send_messages([send_request])[0].message_id
            message = Message.objects.get(id=message_id)
        elif message.date_sent != post.sent_at:
            Message.objects.filter(id=message.id).update(date_sent=post.sent_at)
            message.date_sent = post.sent_at

        stale_messages = list(candidates.exclude(id=message.id))
        if stale_messages:
            do_delete_messages(stream.realm, stale_messages, acting_user=owner)

        return message

    def populate_home_views(
        self,
        *,
        viewer: UserProfile,
        posts_and_messages: list[tuple[DemoPost, Message]],
    ) -> None:
        message_ids = [message.id for _post, message in posts_and_messages]
        for_you_message_ids = [
            message.id for post, message in posts_and_messages if post.for_you
        ]

        do_update_message_flags(viewer, "add", "read", message_ids)
        do_update_message_flags(viewer, "remove", "read", for_you_message_ids)

        desired_todos = [
            (post, message)
            for post, message in posts_and_messages
            if post.todo_note is not None and post.todo_due_after is not None
        ]
        desired_notes = [post.todo_note for post, _message in desired_todos]
        existing_reminders = ScheduledMessage.objects.filter(
            sender=viewer,
            delivery_type=ScheduledMessage.REMIND,
            delivered=False,
            reminder_note__in=desired_notes,
        ).order_by("id")
        reminders_by_note: dict[str, list[ScheduledMessage]] = {}
        for reminder in existing_reminders:
            assert reminder.reminder_note is not None
            reminders_by_note.setdefault(reminder.reminder_note, []).append(reminder)

        client = get_client("Internal")
        for post, message in desired_todos:
            assert post.todo_note is not None
            assert post.todo_due_after is not None
            matching_reminders = reminders_by_note.get(post.todo_note, [])
            current_reminder = next(
                (
                    reminder
                    for reminder in matching_reminders
                    if reminder.reminder_target_message_id == message.id
                ),
                None,
            )
            for reminder in matching_reminders:
                if reminder.id != getattr(current_reminder, "id", None):
                    do_delete_reminder(viewer, reminder)

            if current_reminder is None:
                schedule_reminder_for_message(
                    viewer,
                    client,
                    message.id,
                    timezone_now() + post.todo_due_after,
                    post.todo_note,
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

        posts_and_messages = []
        for post in DEMO_POSTS:
            sender = users_by_email[post.sender_email]
            posts_and_messages.append(
                (
                    post,
                    self.reconcile_demo_message(
                        post,
                        stream=stream,
                        sender=sender,
                        owner=owner,
                    ),
                )
            )

        self.populate_home_views(viewer=viewer, posts_and_messages=posts_and_messages)

        self.stdout.write(
            self.style.SUCCESS(
                f"AIMTO Events is ready with {len(DEMO_POSTS)} native Hover posts, "
                "3 For You items, and 3 Todos "
                f"in {realm.string_id}."
            )
        )
