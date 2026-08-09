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
from zerver.actions.user_settings import do_change_full_name
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


# Source-derived demo updates use one assistant identity and one configured
# publication topic; external sender identities remain part of source evidence.
HOVER_AI_EMAIL = "hover-ai@hover.test"
HOVER_DISPLAY_NAME = "Hover"
SUMMARY_TOPIC = "Summary"


@dataclass(frozen=True)
class DemoPost:
    content: str
    sent_at: datetime.datetime
    for_you: bool = False
    todo_note: str | None = None
    todo_due_after: datetime.timedelta | None = None


def demo_time(day: int, hour: int, minute: int) -> datetime.datetime:
    return datetime.datetime(2026, 8, day, hour, minute, tzinfo=datetime.timezone.utc)


DEMO_POSTS = [
    DemoPost(
        content=(
            "Monday's **9:00 PM volunteer briefing** is confirmed. Please react once you've "
            "read the floor plan so we know every zone has an owner before event day.\n\n"
            "**Source reviewed**\n\n"
            "- **WhatsApp · All Learn-a-thon Mentors & Volunteers**"
        ),
        sent_at=demo_time(7, 1, 18),
        for_you=True,
        todo_note="AIMTO · Publish the volunteer briefing agenda",
        todo_due_after=datetime.timedelta(hours=8),
    ),
    DemoPost(
        content=(
            "Day 1 coverage is now filled: three volunteers have taken the open slots. We still "
            "need to confirm Mandarin, Malay, and Tamil support across registration and the builder "
            "area.\n\n"
            "**Source reviewed**\n\n"
            "- **WhatsApp · 500 volunteers @ Learnathon**"
        ),
        sent_at=demo_time(7, 6, 42),
    ),
    DemoPost(
        content=(
            "Sticker quantities are locked at **1,500**: 900 beginner, 300 medium, 300 pro, plus "
            "50 mentor stickers. The remaining floor-plan question is ownership of the blue "
            "discovery and community zone.\n\n"
            "**Source reviewed**\n\n"
            "- **WhatsApp · All Learn-a-thon Mentors & Volunteers**"
        ),
        sent_at=demo_time(8, 2, 5),
        for_you=True,
        todo_note="AIMTO · Assign the blue zone owner",
        todo_due_after=datetime.timedelta(days=1, hours=3),
    ),
    DemoPost(
        content=(
            "The lobby artwork needs both **16:9** and **9:16** versions, with **FREE** prominent. "
            "The university leaderboard and certificate page give us a stronger outreach story.\n\n"
            "**Source reviewed**\n\n"
            "- **WhatsApp · Resident Lounge**"
        ),
        sent_at=demo_time(8, 8, 30),
        todo_note="AIMTO · Approve final lobby assets",
        todo_due_after=datetime.timedelta(days=2),
    ),
    DemoPost(
        content=(
            "The website work is moving: certificate and university leaderboard updates are in, "
            "and the homepage refresh is ready for a final event-details pass.\n\n"
            "**Source reviewed**\n\n"
            "- [GitHub · LearnAIMTO](https://github.com/ashvinpraveen/learnaimto)"
        ),
        sent_at=demo_time(9, 3, 20),
    ),
    DemoPost(
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

    def get_or_create_hover_user(self, *, realm: Realm, owner: UserProfile) -> UserProfile:
        try:
            hover_user = get_user_by_delivery_email(HOVER_AI_EMAIL, realm)
        except UserProfile.DoesNotExist:
            return do_create_user(
                HOVER_AI_EMAIL,
                "hover-demo",
                realm,
                HOVER_DISPLAY_NAME,
                bot_type=UserProfile.DEFAULT_BOT,
                bot_owner=owner,
                acting_user=owner,
            )

        if hover_user.full_name != HOVER_DISPLAY_NAME:
            do_change_full_name(hover_user, HOVER_DISPLAY_NAME, acting_user=owner, notify=True)
        return hover_user

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
            subject=SUMMARY_TOPIC,
        ).order_by("id")
        message = candidates.filter(content=post.content).first()

        if message is None:
            send_request = internal_prep_stream_message(
                sender,
                stream,
                SUMMARY_TOPIC,
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
                "Source-backed Hover updates and teammate collaboration for the AIMTO Learn-a-thon."
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

        hover_user = self.get_or_create_hover_user(realm=realm, owner=owner)

        subscribers_by_id = {hover_user.id: hover_user}
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
            posts_and_messages.append(
                (
                    post,
                    self.reconcile_demo_message(
                        post,
                        stream=stream,
                        sender=hover_user,
                        owner=owner,
                    ),
                )
            )

        current_message_ids = [message.id for _post, message in posts_and_messages]
        stale_messages = list(
            Message.objects.filter(recipient=stream.recipient).exclude(id__in=current_message_ids)
        )
        if stale_messages:
            do_delete_messages(stream.realm, stale_messages, acting_user=owner)

        self.populate_home_views(viewer=viewer, posts_and_messages=posts_and_messages)

        self.stdout.write(
            self.style.SUCCESS(
                f"AIMTO Events is ready with {len(DEMO_POSTS)} native Hover posts, "
                "3 For You items, and 3 Todos "
                f"in {realm.string_id}."
            )
        )
