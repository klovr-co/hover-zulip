import datetime
import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import orjson
from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from django.db import connection, transaction
from typing_extensions import override

from hover.actions_modules import do_install_module, ensure_prebuilt_module_catalog
from hover.models import (
    ConnectedAccount,
    ConnectedAccountGrant,
    EvidenceLink,
    GeneratedItem,
    ModuleVersion,
    Source,
    SourceCapability,
    Space,
    SpaceAdministrator,
    SpaceAttachment,
    SpaceMembership,
    SuggestedAction,
)
from hover.publication_contracts import (
    AnalysisFinding,
    AnalysisPayload,
    ClawerPublication,
    CoveredPeriod,
    DecisionPayload,
    DigestMetrics,
    DigestPayload,
    ProgressUpdatePayload,
    PublicationPayload,
    SuggestedActionPayload,
)
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.create_user import do_create_user
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.message_send import do_send_messages, internal_prep_stream_message
from zerver.actions.reminders import do_delete_reminder
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_stream_folder,
    do_change_stream_permission,
)
from zerver.actions.user_settings import do_change_full_name
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.message import access_message
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
from zerver.models.users import get_user_by_delivery_email

# Source-derived demo updates use one assistant identity and one native topic
# per AI module; external sender identities remain part of source evidence.
HOVER_AI_EMAIL = "hover-ai@hover.test"
HOVER_DISPLAY_NAME = "Hover"

HoverModuleKey = Literal[
    "conversation_digest",
    "progress_tracker",
    "suggested_actions",
    "decisions",
    "marketing_digest",
    "topic_analysis",
]
PublicationContract = Literal[
    "digest", "progress_update", "suggested_action", "decision", "analysis"
]

MODULE_NAMES: dict[HoverModuleKey, str] = {
    "conversation_digest": "Conversation Digest",
    "progress_tracker": "Progress Tracker",
    "suggested_actions": "Suggested Actions",
    "decisions": "Decisions",
    "marketing_digest": "Marketing Digest",
    "topic_analysis": "Topic Analysis",
}

MODULE_OUTPUT_TYPES: dict[HoverModuleKey, PublicationContract] = {
    "conversation_digest": "digest",
    "progress_tracker": "progress_update",
    "suggested_actions": "suggested_action",
    "decisions": "decision",
    "marketing_digest": "digest",
    "topic_analysis": "analysis",
}
MODULE_VERSION = "1.0.0"

EVIDENCE_SOURCES = {
    "mentors_volunteers": {
        "provider_key": "whatsapp",
        "provider_name": "WhatsApp",
        "source_type": "group_chat",
        "display_name": "All Learn-a-thon Mentors & Volunteers",
        "url": "",
    },
    "resident_lounge": {
        "provider_key": "whatsapp",
        "provider_name": "WhatsApp",
        "source_type": "group_chat",
        "display_name": "Resident Lounge",
        "url": "",
    },
    "volunteers_500": {
        "provider_key": "whatsapp",
        "provider_name": "WhatsApp",
        "source_type": "group_chat",
        "display_name": "500 volunteers @ Learnathon",
        "url": "",
    },
    "github": {
        "provider_key": "github",
        "provider_name": "GitHub",
        "source_type": "repository",
        "display_name": "LearnAIMTO",
        "url": "https://github.com/ashvinpraveen/learnaimto",
    },
    "instagram": {
        "provider_key": "instagram",
        "provider_name": "Instagram",
        "source_type": "social_profile",
        "display_name": "@aimto_26",
        "url": "https://www.instagram.com/aimto_26/",
    },
}

LEGACY_DEMO_TODO_NOTES = {
    "AIMTO · Publish the volunteer briefing agenda",
    "AIMTO · Assign the blue zone owner",
    "AIMTO · Approve final lobby assets",
}


@dataclass(frozen=True)
class DemoPost:
    module_key: HoverModuleKey
    content: str
    sent_at: datetime.datetime
    evidence_keys: tuple[str, ...]
    for_you: bool = False
    saved: bool = False
    suggested_action_payload: dict[str, object] | None = None


def demo_post(
    module_key: HoverModuleKey,
    content: str,
    sent_at: datetime.datetime,
    evidence_keys: tuple[str, ...],
    *,
    for_you: bool = False,
    saved: bool = False,
    suggested_action_payload: dict[str, object] | None = None,
) -> DemoPost:
    return DemoPost(
        module_key=module_key,
        content=content,
        sent_at=sent_at,
        evidence_keys=evidence_keys,
        for_you=for_you,
        saved=saved,
        suggested_action_payload=suggested_action_payload,
    )


def demo_time(day: int, hour: int, minute: int) -> datetime.datetime:
    return datetime.datetime(2026, 8, day, hour, minute, tzinfo=datetime.timezone.utc)


def opaque_demo_id(namespace: str, value: str) -> str:
    return hashlib.sha256(f"hover-aimto-demo:{namespace}:{value}".encode()).hexdigest()[:32]


def demo_payload(post: DemoPost) -> PublicationPayload:
    title = post.content.partition("\n")[0].removeprefix("## ")
    if post.module_key in {"conversation_digest", "marketing_digest"}:
        return DigestPayload(
            contract="digest",
            schema_version="1.0",
            title=title,
            timezone="UTC",
            operation=post.content,
            marketing="The native update preserves the sanitized source-backed briefing.",
            metrics=DigestMetrics(
                messages=len(post.evidence_keys),
                text=len(post.evidence_keys),
                media=0,
                voice=0,
            ),
            generation_context="Sanitized AIMTO development demo",
        )
    if post.module_key == "progress_tracker":
        status: Literal["blocked", "in_progress"] = (
            "blocked" if "Status: At risk" in post.content else "in_progress"
        )
        return ProgressUpdatePayload(
            contract="progress_update",
            schema_version="1.0",
            title=title,
            status=status,
            updates=[post.content],
            resolved_items=[],
            blockers=(
                ["The source history does not yet confirm the required assignment."]
                if status == "blocked"
                else []
            ),
        )
    if post.module_key == "decisions":
        return DecisionPayload(
            contract="decision",
            schema_version="1.0",
            title=title,
            decision=post.content,
            rationale="The native update records the sanitized supporting evidence.",
            lifecycle="active",
            supersedes_publication_id=None,
            reverses_publication_id=None,
        )
    if post.module_key == "suggested_actions":
        return SuggestedActionPayload(
            contract="suggested_action",
            schema_version="1.0",
            wording=post.content,
            proposed_assignee=None,
            proposed_due_date=None,
        )
    return AnalysisPayload(
        contract="analysis",
        schema_version="1.0",
        title=title,
        timezone="UTC",
        summary=post.content,
        findings=[
            AnalysisFinding(
                title="Source-backed finding",
                detail="The native update preserves the sanitized analysis and uncertainty.",
            )
        ],
        generation_context="Sanitized AIMTO development demo",
        sentiment=None,
    )


DEMO_POSTS = [
    demo_post(
        "conversation_digest",
        """## Mentors & Volunteers · coordination took shape

**Main thread**
The group moved from an initial floor-plan walkthrough into volunteer recruitment, zone preferences, language support, materials, and a shared briefing.

**What meaningfully changed**

- The organizer asked for about **10 more volunteers** on 5 August; the group had **17 volunteers** by the evening of 6 August and another large intake joined on 7 August.
- Orange, purple/pink, green, blue, and stage areas were explained. Tharshen offered to cover orange and purple, or green if needed, but Lizzie said final placement would be sorted after more people joined.
- A **Monday 9:00 PM** volunteer briefing was announced for detailed roles.

**Confirmed**
Orange is registration and the dream wall; purple/pink is the main builder-support area; green is debug/deploy; the stage hosts workshops and two show-and-tells. Outreach copy and the public site link are ready to share.

**Still unresolved**
The blue zone remains tentative, final zone ownership is unpublished, and the chat asks for Mandarin-, Malay-, and Tamil-speaking volunteers without confirming coverage.

**Why AIMTO should care**
Recruitment momentum is strong, but the briefing needs to turn offers into a named operating plan for a deliberately broad, beginner-friendly audience.

**Source reviewed**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — 5–8 August 2026""",
        demo_time(8, 14, 20),
        ("mentors_volunteers",),
    ),
    demo_post(
        "progress_tracker",
        """## Progress · Floor plan and zone ownership

> **Status: In progress**

**Current status**
Four operating areas have a clear purpose; the blue discovery/community area is still tentative.

**What changed**
The organizer translated the floor plan into registration/dream wall, builder support, debug/deploy, stage programming, and a possible community-discovery area.

**Completed work**
Orange, purple/pink, green, and stage responsibilities are described. Tharshen volunteered for orange and purple, with green as a fallback.

**Blocker or dependency**
Lizzie deferred final placement until more volunteers joined. No final owner or final purpose is recorded for blue.

**Next milestone**
Publish named zone leads during the Monday 9:00 PM briefing.

**Supporting source**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — floor-plan thread, 5 August 2026""",
        demo_time(8, 14, 32),
        ("mentors_volunteers",),
        for_you=True,
    ),
    demo_post(
        "conversation_digest",
        """## 500 volunteers · Day 1 coverage closed quickly

**Main thread**
This subgroup was created for 500 Global / malaysian.ai volunteers to coordinate their own practical details while keeping the main mentors group as the source of overall event direction.

**What meaningfully changed**
A request for **three Day 1 volunteers** moved from open to filled in under an hour: Andrew, Bede, and Gracie offered full-day availability that matched the request.

**Confirmed**
The roles cover event setup and attendance for the private Day 1 event. Lunch is provided, and the subgroup can coordinate items such as lunch and sticker distribution.

**Still unresolved**
Detailed instructions were promised but are not present in the export. Gabriel offered partial Tuesday availability, which Lizzie indicated might not fit the role.

**Why AIMTO should care**
The staffing ask is closed, but the accepted volunteers still need one concise handoff so subgroup logistics do not diverge from the main event plan.

**Source reviewed**

- **WhatsApp · 500 volunteers @ Learnathon** — 8 August 2026""",
        demo_time(8, 15, 5),
        ("volunteers_500",),
    ),
    demo_post(
        "decisions",
        """## Decision · Keep overall coordination in the main group

> **Lifecycle: Active**

**Decision**
Use “All Learnathon Volunteers/Mentors” for overall event updates and coordination; use the 500 / malaysian.ai subgroup only for team-specific details such as lunch and sticker distribution.

**When**
8 August 2026, when the subgroup was opened.

**Participants / conversation**
Lizzie set the operating boundary for members of **500 volunteers @ Learnathon**.

**Rationale**
Volunteers are coming from several organizers, so the main group needs to remain the common coordination channel.

**Supporting evidence**

- **WhatsApp · 500 volunteers @ Learnathon** — subgroup welcome and scope""",
        demo_time(8, 15, 18),
        ("volunteers_500",),
    ),
    demo_post(
        "progress_tracker",
        """## Progress · Volunteer staffing and coverage

> **Status: On track**

**Current status**
Recruitment expanded materially, and the separate three-person Day 1 requirement is filled.

**What changed**
The main group reported 17 volunteers on 6 August, then added a sizeable new cohort on 7 August. On 8 August, the 500 subgroup filled all three requested Day 1 roles.

**Completed work**
Andrew, Bede, and Gracie supplied the three full-day Day 1 commitments. The main mentors group also has named offers for several Learn-a-thon zones.

**Blocker or dependency**
The exports do not show a final role roster or coverage map for Day 2.

**Next milestone**
Convert availability into named zone assignments at the volunteer briefing.

**Supporting sources**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — recruitment and group growth
- **WhatsApp · 500 volunteers @ Learnathon** — Day 1 call for three people""",
        demo_time(8, 15, 31),
        ("mentors_volunteers", "volunteers_500"),
    ),
    demo_post(
        "decisions",
        """## Decision · Fill the three Day 1 volunteer slots

> **Lifecycle: Active**

**Decision**
Proceed with Andrew, Bede, and Gracie for the three requested Day 1 setup and attendance roles.

**When**
8 August 2026, between 8:15 PM and 8:58 PM.

**Participants / conversation**
Lizzie requested three people; Andrew, Bede, and Gracie each confirmed availability. Lizzie acknowledged the final offer with “awesome”.

**Rationale**
Their offers satisfy the stated requirement for three volunteers. Gabriel's partial-day offer was discussed separately and was not treated as one of the three full commitments.

**Supporting evidence**

- **WhatsApp · 500 volunteers @ Learnathon** — Day 1 staffing thread""",
        demo_time(8, 15, 44),
        ("volunteers_500",),
        saved=True,
    ),
    demo_post(
        "decisions",
        """## Decision · Hold the volunteer briefing Monday at 9:00 PM

> **Lifecycle: Active**

**Decision**
Run the volunteer briefing call on **Monday at 9:00 PM** and use it to walk through roles in more detail.

**When**
8 August 2026 at 10:11 PM.

**Participants / conversation**
Lizzie announced the time to All Learn-a-thon Mentors & Volunteers and asked everyone to react once read.

**Rationale**
The floor plan is known, but detailed role allocation still needs a shared coordination moment.

**Supporting evidence**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — briefing announcement""",
        demo_time(8, 15, 58),
        ("mentors_volunteers",),
        for_you=True,
    ),
    demo_post(
        "suggested_actions",
        """## Suggested action · Publish the volunteer briefing agenda

> **Status: Awaiting confirmation**

**Proposed action**
Post a short agenda before the Monday 9:00 PM call: zone walkthrough, named leads, language coverage, arrivals, and escalation path.

**Why Hover is suggesting it**
The time is confirmed and the call will cover roles, but no agenda or final role roster appears in the source history.

**Suggested teammate**
Lizzie, because she scheduled the call and has been coordinating volunteer placements.

**Suggested due date**
Monday, 10 August · 8:00 PM — one hour before the confirmed briefing.

**Supporting WhatsApp evidence**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — briefing announcement and floor-plan thread""",
        demo_time(8, 16, 12),
        ("mentors_volunteers",),
        for_you=True,
        suggested_action_payload={
            "contract": "suggested_action",
            "schema_version": "1.0",
            "wording": "Post the volunteer briefing agenda before the Monday 9:00 PM call.",
            "proposed_assignee": {
                "kind": "member",
                "ref": "person_11111111111111111111111111111111",
                "display_name": "Lizzie",
            },
            "proposed_due_date": "2026-08-10",
        },
    ),
    demo_post(
        "suggested_actions",
        """## Suggested action · Assign the blue zone owner and purpose

> **Status: Awaiting confirmation**

**Proposed action**
Choose one owner for the blue zone and decide whether it is primarily discovery support, community introductions, or both.

**Why Hover is suggesting it**
The zone is explicitly marked TBD. Other areas have clear functions, while a volunteer's offer to cover orange/purple/green does not resolve blue.

**Suggested teammate**
Lizzie, because she said final zone placement would be sorted after recruitment expanded.

**Suggested due date**
During the Monday 9:00 PM briefing, before the role roster is shared.

**Supporting WhatsApp evidence**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — floor plan and placement follow-up""",
        demo_time(8, 16, 26),
        ("mentors_volunteers",),
        for_you=True,
        suggested_action_payload={
            "contract": "suggested_action",
            "schema_version": "1.0",
            "wording": "Assign the blue zone owner and decide its purpose.",
            "proposed_assignee": {
                "kind": "member",
                "ref": "person_11111111111111111111111111111111",
                "display_name": "Lizzie",
            },
            "proposed_due_date": "2026-08-10",
        },
    ),
    demo_post(
        "marketing_digest",
        """## Worth sharing · LearnAIMTO has a public, open-source front door

**Why this is remarkable**
[learn.aimto.my](https://learn.aimto.my/) is now more than an event-information page: the community can use it to introduce true beginners to the Learn-a-thon and contribute improvements through its public repository.

**The news**

- Ashvin publicly shared the site and [GitHub repository](https://github.com/ashvinpraveen/learnaimto) on 1 August, inviting feedback, forks, and contributions.
- The public experience now includes beginner guidance, project inspiration, registration paths, FAQs, a university leaderboard, and certificates.
- The open-source route gives collaborators something concrete to improve and gives outreach partners one consistent destination to share.

**Amplification angle**
Share the launch as a community-built invitation: people can attend without coding experience, explore what they could build, or contribute directly to the event experience.

**Source boundary**
[Instagram · @aimto_26](https://www.instagram.com/aimto_26/) is linked for monitoring or publication; no account-post content is inferred here.

**Sources reviewed**

- **WhatsApp · Resident Lounge** — site feedback and repository link
- [GitHub · LearnAIMTO](https://github.com/ashvinpraveen/learnaimto)
- [Instagram · @aimto_26](https://www.instagram.com/aimto_26/) — linked destination only""",
        demo_time(9, 2, 40),
        ("resident_lounge", "github", "instagram"),
    ),
    demo_post(
        "marketing_digest",
        """## Worth sharing · The university challenge is visible live

**Why this is remarkable**
University participation now has a public scoreboard and a tangible outcome for every builder, giving campus communities a reason to rally together rather than treating the Learn-a-thon as another generic event invitation.

**The news**

- Janelle shared outreach copy featuring rewards for the top two universities, an official certificate for every project submission, free AI credits, and mentor guidance.
- The [live leaderboard](https://learn.aimto.my/leaderboard) gives communities a visible result to follow and share.
- The message was cleared for broad sharing, including university groups and LinkedIn. An AIMTO Instagram post was proposed but is not confirmed in the export.

**Amplification angle**
Invite each university to move its name up the leaderboard while emphasizing that beginners can still leave with a completed project and certificate.

**Sources reviewed**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — shareable university message
- **WhatsApp · Resident Lounge** — campaign framing and Instagram proposal
- [GitHub · LearnAIMTO](https://github.com/ashvinpraveen/learnaimto)
- [Instagram · @aimto_26](https://www.instagram.com/aimto_26/) — proposed destination, publication not confirmed""",
        demo_time(9, 9, 45),
        ("mentors_volunteers", "resident_lounge", "github", "instagram"),
    ),
    demo_post(
        "conversation_digest",
        """## Resident Lounge · promotion moved into final production

**Main thread**
The AIMTO conversation combined public-site feedback, open-source delivery, lobby creative, beginner positioning, and university outreach.

**What meaningfully changed**
The LearnAIMTO repository accumulated public-facing improvements, the leaderboard and certificate routes landed, and lobby artwork moved from concept comparisons to a request for final **16:9 and 9:16** versions.

**Confirmed**
The AICB placement is intended to attract building tenants and visitors to the Learn-a-thon. PNG is preferred, “FREE” should be more obvious, and the message should work for people who do not know how to start with AI.

**Still unresolved**
The export ends while Maxine is generating final visuals. It does not show final asset approval, final copy, or a published Instagram post.

**Why AIMTO should care**
The operational ask is now a final creative handoff: preserve consistent event details across two ratios while keeping the beginner promise unmistakable.

**Sources reviewed**

- **WhatsApp · Resident Lounge** — 1–10 August 2026
- [GitHub · LearnAIMTO](https://github.com/ashvinpraveen/learnaimto)
- [Instagram · @aimto_26](https://www.instagram.com/aimto_26/) — linked for monitoring only""",
        demo_time(9, 10, 5),
        ("resident_lounge", "github", "instagram"),
    ),
    demo_post(
        "marketing_digest",
        """## Worth sharing · Supabase CEO Show & Tell opened publicly

**Why this is remarkable**
Paul Copplestone, Supabase co-founder and CEO, is joining a special Malaysian.ai Show & Tell while he is in Kuala Lumpur—a rare chance for local builders to hear his journey and show what Malaysia is building.

**The news**

- Isaac announced that registration was live on 7 August: [open the Luma event](https://luma.com/zkxj8z7b).
- The plan combines Paul's founder journey, a curated showcase of 10–15 builders, and networking with the local community.
- The group explicitly confirmed that the event could be shared publicly, including on social channels.

**Amplification angle**
Share the Luma link with builders who have something strong to demonstrate, and frame the event as a window into both Supabase's story and Malaysia's active builder scene.

**Source reviewed**

- **WhatsApp · Resident Lounge** — launch announcement and public-sharing confirmation, 6–7 August 2026
- [Luma · Supabase's first move + Malaysian.ai Show & Tell](https://luma.com/zkxj8z7b)""",
        demo_time(9, 10, 19),
        ("resident_lounge",),
    ),
    demo_post(
        "progress_tracker",
        """## Progress · AICB lobby poster delivery

> **Status: In progress**

**Owner**
Maxine.

**Current status**
The AICB lobby campaign has moved from early concepts into final production for the building's LED screens.

**What changed**
Maxine shared three initial directions, incorporated feedback to emphasize Day 2, restored event logos, and took ownership of polishing the selected direction in both **16:9 and 9:16**.

**Completed work**
The placement goal, beginner audience, practical workflow/automation positioning, PNG preference, and need to make **FREE** more obvious are all established. Draft visuals received positive reactions.

**Blocker or dependency**
The export ends before final copy refinement, final asset approval, or confirmation that the files reached AICB.

**Next milestone**
Share the polished 16:9 and 9:16 PNG files for final copy review and placement approval.

**Supporting source**

- **WhatsApp · Resident Lounge** — Maxine's AICB lobby artwork thread, 8–9 August 2026""",
        demo_time(9, 10, 34),
        ("resident_lounge",),
    ),
    demo_post(
        "progress_tracker",
        """## Progress · Language-support coverage

> **Status: At risk**

**Current status**
The need is clear, but named coverage is not.

**What changed**
E asked the volunteer group to identify Mandarin speakers; Lizzie separately welcomed Malay- and Tamil-speaking volunteers. Resident Lounge outreach also framed Mandarin coaching as part of the beginner promise.

**Completed work**
Language access is now present in both volunteer recruitment and public-facing campaign thinking.

**Blocker or dependency**
No exported message confirms a Mandarin, Malay, or Tamil speaker assigned to registration, builder support, or another zone.

**Next milestone**
Confirm at least one named contact and location for each requested language during the volunteer briefing.

**Supporting sources**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — Mandarin, Malay, and Tamil recruitment
- **WhatsApp · Resident Lounge** — beginner flyer concept with Mandarin mentor support""",
        demo_time(9, 10, 48),
        ("mentors_volunteers", "resident_lounge"),
        for_you=True,
    ),
    demo_post(
        "suggested_actions",
        """## Suggested action · Confirm Mandarin, Malay, and Tamil coverage

> **Status: Awaiting confirmation**

**Proposed action**
Name the available Mandarin-, Malay-, and Tamil-speaking volunteers and place each person at registration, builder support, or an on-call escalation point.

**Why Hover is suggesting it**
The organizer explicitly invited all three language groups, and public outreach promises a beginner-friendly experience. The exports contain no assignment confirmation.

**Suggested due date**
Confirm during the Monday 9:00 PM briefing so the promise is operational before event day.

**Supporting WhatsApp evidence**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — language recruitment on 5 August
- **WhatsApp · Resident Lounge** — Mandarin-support outreach concept on 9 August""",
        demo_time(9, 11, 2),
        ("mentors_volunteers", "resident_lounge"),
        for_you=True,
        suggested_action_payload={
            "contract": "suggested_action",
            "schema_version": "1.0",
            "wording": "Confirm Mandarin, Malay, and Tamil volunteer coverage.",
            "proposed_assignee": None,
            "proposed_due_date": "2026-08-10",
        },
    ),
    demo_post(
        "topic_analysis",
        """## Topic analysis · Volunteer readiness and ownership gaps

**Question**
Is the volunteer operation ready to move from recruitment into delivery?

**Main finding**
Staffing momentum is healthy, but ownership information is lagging behind headcount.

**Supporting signals**

- The main group grew from a request for roughly ten more people to 17 reported volunteers, followed by another large intake.
- The 500 subgroup filled its separate three-person Day 1 ask with Andrew, Bede, and Gracie.
- Orange, purple/pink, green, and stage functions are described, but final placements were deferred and blue remains TBD.
- A Monday 9:00 PM briefing is confirmed specifically to explain roles in more detail.

**Uncertainty**
The exports do not include a final Day 2 roster, check-in plan, or a named blue-zone owner.

**Practical implication**
Do not recruit blindly. Use the briefing to publish a compact coverage matrix: person, time window, zone, language, and escalation lead.

**Supporting sources**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — staffing, floor plan, briefing
- **WhatsApp · 500 volunteers @ Learnathon** — Day 1 role fill""",
        demo_time(9, 11, 16),
        ("mentors_volunteers", "volunteers_500"),
        saved=True,
    ),
    demo_post(
        "topic_analysis",
        """## Topic analysis · Language access and message consistency

**Question**
Does the event's inclusive promise line up with operational coverage and public communication?

**Main finding**
The intent is consistent—all ages, true beginners, broad Malaysian participation—but the language promise is ahead of verified staffing.

**Supporting signals**

- Mentors & Volunteers explicitly seeks Mandarin speakers, then adds Malay and Tamil to the recruitment call.
- Resident Lounge frames the morning-market flyer around people with no coding experience and proposes reassuring non-English speakers that Mandarin mentors can coach them.
- Lobby creative discussion asks for “FREE” to be more obvious and for practical workflow/automation language that works beyond technical audiences.
- LearnAIMTO's public repository describes a beginner-friendly experience with guided learning and practical project inspiration.

**Uncertainty**
No export confirms who covers each language, and no final lobby asset or Instagram publication is shown.

**Practical implication**
Use one verified accessibility line everywhere: which languages are available, where attendees find help, and what “beginner-friendly” includes.

**Supporting sources**

- **WhatsApp · All Learn-a-thon Mentors & Volunteers** — language recruitment
- **WhatsApp · Resident Lounge** — beginner flyer and lobby positioning
- [GitHub · LearnAIMTO](https://github.com/ashvinpraveen/learnaimto) — public experience
- [Instagram · @aimto_26](https://www.instagram.com/aimto_26/) — monitoring destination only""",
        demo_time(10, 0, 15),
        ("mentors_volunteers", "resident_lounge", "github", "instagram"),
        for_you=True,
        saved=True,
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

    def reconcile_live_sources(
        self,
        *,
        realm: Realm,
        space: Space,
        owner: UserProfile,
        viewer: UserProfile,
    ) -> dict[str, SpaceAttachment]:
        members_by_id = {owner.id: (owner, SpaceMembership.Role.CONTRIBUTOR)}
        if viewer.id != owner.id:
            members_by_id[viewer.id] = (viewer, SpaceMembership.Role.SUBSCRIBER)
        for member, role in members_by_id.values():
            SpaceMembership.objects.update_or_create(
                realm=realm,
                space=space,
                user=member,
                defaults={"role": role, "added_by": owner},
            )

        accounts: dict[str, ConnectedAccount] = {}
        for source_spec in EVIDENCE_SOURCES.values():
            provider_key = source_spec["provider_key"]
            if provider_key in accounts:
                continue
            account, _created = ConnectedAccount.objects.update_or_create(
                realm=realm,
                provider_key=provider_key,
                external_account_id=uuid.UUID(hex=opaque_demo_id("account", provider_key)),
                defaults={
                    "provider_name": source_spec["provider_name"],
                    "display_name": f"AIMTO {source_spec['provider_name']}",
                    "connection_kind": ConnectedAccount.ConnectionKind.REMOTE_STUDIO,
                    "incoming_webhook_bot": None,
                    "created_by": owner,
                    "owner": owner,
                    "approval_state": ConnectedAccount.ApprovalState.APPROVED,
                    "health_status": ConnectedAccount.HealthStatus.HEALTHY,
                    "health_checked_at": demo_time(10, 0, 0),
                },
            )
            accounts[provider_key] = account
            for member, _role in members_by_id.values():
                ConnectedAccountGrant.objects.update_or_create(
                    realm=realm,
                    account=account,
                    user=member,
                    defaults={
                        "created_by": owner,
                        "state": ConnectedAccountGrant.State.ACTIVE,
                        "all_selectors": True,
                    },
                )

        attachments: dict[str, SpaceAttachment] = {}
        for evidence_key, source_spec in EVIDENCE_SOURCES.items():
            account = accounts[source_spec["provider_key"]]
            external_ref = f"src_{opaque_demo_id('source', evidence_key)}"
            source_record, _created = Source.objects.update_or_create(
                account=account,
                external_ref=external_ref,
                defaults={
                    "realm": realm,
                    "adapter_key": "clawer_sync",
                    "provider_key": source_spec["provider_key"],
                    "source_type": source_spec["source_type"],
                    "display_name": source_spec["display_name"],
                    "provider_name": source_spec["provider_name"],
                    "external_url": source_spec["url"],
                    "supports_live_capture": False,
                },
            )
            SourceCapability.objects.get_or_create(
                source=source_record, capability="message_history"
            )
            attachment, _created = SpaceAttachment.objects.update_or_create(
                realm=realm,
                space=space,
                source=source_record,
                defaults={
                    "state": SpaceAttachment.State.ACTIVE,
                    "history_window": SpaceAttachment.HistoryWindow.LAST_30_DAYS,
                    "history_timezone": "UTC",
                    "history_start_at": demo_time(1, 0, 0),
                    "custom_start_date": None,
                    "publication_cursor": "aimto-demo-complete",
                    "last_publication_sync_at": demo_time(10, 0, 0),
                    "last_publication_sync_error": "",
                    "publication_sync_failures": 0,
                    "publication_sync_state": SpaceAttachment.PublicationSyncState.IDLE,
                    "publication_sync_lease_token": None,
                    "publication_sync_lease_expires_at": None,
                    "next_publication_sync_at": None,
                    "attached_by": owner,
                    "detached_at": None,
                    "detached_by": None,
                },
            )
            attachments[evidence_key] = attachment
        return attachments

    def reconcile_modules(
        self,
        *,
        realm: Realm,
        space: Space,
        owner: UserProfile,
        attachments: dict[str, SpaceAttachment],
    ) -> dict[HoverModuleKey, ModuleVersion]:
        ensure_prebuilt_module_catalog(realm)
        versions: dict[HoverModuleKey, ModuleVersion] = {}
        for module_key in MODULE_NAMES:
            versions[module_key] = ModuleVersion.objects.get(
                definition__realm=realm,
                definition__stable_key=module_key,
                version=MODULE_VERSION,
            )
        all_attachment_ids = [attachments[key].id for key in EVIDENCE_SOURCES]
        single_bindings = {
            "marketing_digest": [attachments["resident_lounge"].id],
            "topic_analysis": [attachments["mentors_volunteers"].id],
        }
        for module_key in MODULE_NAMES:
            do_install_module(
                acting_user=owner,
                space=space,
                version_id=versions[module_key].id,
                attachment_ids=single_bindings.get(module_key, all_attachment_ids),
                trigger_kind="manual",
                activation_timezone="UTC",
            )
        return versions

    @transaction.atomic(savepoint=False)
    def reconcile_demo_message(
        self,
        post: DemoPost,
        *,
        post_number: int,
        stream: Stream,
        sender: UserProfile,
        owner: UserProfile,
        attachments: dict[str, SpaceAttachment],
        module_version: ModuleVersion,
    ) -> Message:
        candidates = Message.objects.filter(
            realm_id=stream.realm_id,
            recipient=stream.recipient,
            sender=sender,
            subject=MODULE_NAMES[post.module_key],
        ).order_by("id")
        message = candidates.filter(content=post.content).first()

        if message is None:
            send_request = internal_prep_stream_message(
                sender,
                stream,
                MODULE_NAMES[post.module_key],
                post.content,
                forged=True,
                forged_timestamp=post.sent_at.timestamp(),
                acting_user=owner,
            )
            assert send_request is not None
            message_id = do_send_messages([send_request])[0].message_id
            message = access_message(owner, message_id, is_modifying_message=False)
        elif message.date_sent != post.sent_at:
            Message.objects.filter(id=message.id).update(date_sent=post.sent_at)
            message.date_sent = post.sent_at

        evidence_sources = [attachments[key].source for key in post.evidence_keys]
        source_summary = (
            f"Across {len(evidence_sources)} sources"
            if len(evidence_sources) > 1
            else f"From {evidence_sources[0].display_name}"
        )
        publication_id = f"aimto-demo-publication-{post_number:02}"
        idempotency_key = f"aimto-demo-v1-{post_number:02}"
        business_identity = f"aimto-demo:{post.module_key}:{post_number:02}"
        covered_start_at = post.sent_at - datetime.timedelta(days=1)
        occurred_at = post.sent_at - datetime.timedelta(minutes=5)
        generated_at = post.sent_at - datetime.timedelta(minutes=1)
        evidence_refs = [
            f"evidence_{opaque_demo_id('evidence', f'{post_number}:{position}:{evidence_key}')}"
            for position, evidence_key in enumerate(post.evidence_keys)
        ]
        publication = ClawerPublication(
            publication_id=publication_id,
            idempotency_key=idempotency_key,
            business_identity=business_identity,
            contract=MODULE_OUTPUT_TYPES[post.module_key],
            schema_version="1.0",
            producer_key=post.module_key,
            producer_name=MODULE_NAMES[post.module_key],
            producing_version=module_version.version,
            run_reference="aimto-demo-run-2026-08-10",
            source_ref=attachments[post.evidence_keys[0]].source.external_ref,
            covered_period=CoveredPeriod(start=covered_start_at, end=post.sent_at),
            payload=demo_payload(post),
            evidence_refs=evidence_refs,
            importance="high" if post.for_you else "normal",
            occurred_at=occurred_at,
            generated_at=generated_at,
            published_at=post.sent_at,
            lineage_key=business_identity,
            parent_publication_id=None,
            material_change=False,
        )
        publication_envelope_hash = hashlib.sha256(
            orjson.dumps(publication.model_dump(mode="json"), option=orjson.OPT_SORT_KEYS)
        ).hexdigest()
        publication_payload = publication.payload.model_dump(mode="json")
        generated_item_defaults: dict[str, Any] = {
            "realm": stream.realm,
            "attachment": attachments[post.evidence_keys[0]],
            "publication_id": publication.publication_id,
            "idempotency_key": publication.idempotency_key,
            "publication_envelope_hash": publication_envelope_hash,
            "business_identity": publication.business_identity,
            "output_type": publication.contract,
            "module_key": publication.producer_key,
            "module_name": publication.producer_name,
            "module_version": publication.producing_version,
            "source_summary": source_summary,
            "payload": publication_payload,
            "importance": publication.importance,
            "run_reference": publication.run_reference,
            "covered_start_at": publication.covered_period.start,
            "covered_end_at": publication.covered_period.end,
            "occurred_at": publication.occurred_at,
            "generated_at": publication.generated_at,
            "published_at": publication.published_at,
            "lineage_key": publication.lineage_key,
            "parent_publication_id": publication.parent_publication_id,
            "material_change": publication.material_change,
        }
        # H14 keeps the immutable publication payload separate from the
        # human-reviewed projection. Populate it when that additive model
        # field is present so this H13 fixture remains valid on either side of
        # the independent Reply/Review integration commit.
        if hasattr(GeneratedItem, "reviewed_payload"):
            generated_item_defaults["reviewed_payload"] = publication_payload
        generated_item, _created = GeneratedItem.objects.update_or_create(
            message=message,
            defaults=generated_item_defaults,
        )
        proposal = (
            SuggestedActionPayload.model_validate(post.suggested_action_payload)
            if post.suggested_action_payload is not None
            else None
        )
        if proposal is not None and (_created or not generated_item.payload):
            generated_item.payload = proposal.model_dump(mode="json")
            generated_item.reviewed_payload = proposal.model_dump(mode="json")
            generated_item.save(update_fields=["payload", "reviewed_payload"])
        if proposal is not None and generated_item.attachment_id is not None:
            assignee = proposal.proposed_assignee
            SuggestedAction.objects.get_or_create(
                realm=stream.realm,
                space=generated_item.attachment.space,
                generated_item=generated_item,
                defaults={
                    "wording": proposal.wording,
                    "proposed_assignee_ref": assignee.ref if assignee is not None else "",
                    "proposed_assignee_display_name": (
                        assignee.display_name if assignee is not None else ""
                    ),
                    "due_date": proposal.proposed_due_date,
                },
            )
        generated_item.evidence_links.all().delete()
        EvidenceLink.objects.bulk_create(
            [
                EvidenceLink(
                    generated_item=generated_item,
                    realm=stream.realm,
                    source=source,
                    evidence_ref=evidence_refs[position],
                    position=position,
                    provider_key=source.provider_key,
                    provider_name=source.provider_name,
                    display_name=source.display_name,
                    url=source.external_url,
                )
                for position, source in enumerate(evidence_sources)
            ]
        )

        return message

    def populate_home_views(
        self,
        *,
        viewer: UserProfile,
        posts_and_messages: list[tuple[DemoPost, Message]],
    ) -> None:
        message_ids = [message.id for _post, message in posts_and_messages]
        for_you_message_ids = [message.id for post, message in posts_and_messages if post.for_you]
        saved_message_ids = [message.id for post, message in posts_and_messages if post.saved]

        do_update_message_flags(viewer, "add", "read", message_ids)
        do_update_message_flags(viewer, "remove", "read", for_you_message_ids)
        do_update_message_flags(viewer, "add", "starred", saved_message_ids)

        # Suggested Actions are proposals, not active Todos. Remove reminders
        # created by older versions of this fixture so rerunning the command
        # preserves that human-confirmation boundary.
        legacy_reminders = ScheduledMessage.objects.filter(
            sender=viewer,
            delivery_type=ScheduledMessage.REMIND,
            delivered=False,
            reminder_note__in=LEGACY_DEMO_TODO_NOTES,
        ).order_by("id")
        for reminder in legacy_reminders:
            do_delete_reminder(viewer, reminder)

    def populate_search_vectors(self, messages: list[Message]) -> None:
        # Streamlined development servers do not run the asynchronous FTS
        # worker. Populate this fixture's vectors synchronously so attached
        # source filters work immediately after running the command.
        message_ids = [message.id for message in messages]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE zerver_message
                SET search_tsvector =
                    to_tsvector('zulip.english_us_search', subject || rendered_content)
                WHERE id = ANY(%s)
                """,
                [message_ids],
            )
            if settings.USING_PGROONGA:
                cursor.execute(
                    """
                    UPDATE zerver_message
                    SET search_pgroonga = escape_html(subject) || ' ' || rendered_content
                    WHERE id = ANY(%s)
                    """,
                    [message_ids],
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

        if not realm.hover_enabled:
            realm.hover_enabled = True
            realm.save(update_fields=["hover_enabled"])

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

        space, _created = Space.objects.update_or_create(
            realm=realm,
            name="AIMTO Events",
            defaults={
                "description": stream.description,
                "state": Space.State.LAUNCHED,
                "category": folder,
                "created_by": owner,
                "stream": stream,
            },
        )
        for administrator in {owner, viewer}:
            SpaceAdministrator.objects.get_or_create(
                realm=realm,
                space=space,
                user=administrator,
                defaults={"added_by": owner},
            )

        attachments = self.reconcile_live_sources(
            realm=realm,
            space=space,
            owner=owner,
            viewer=viewer,
        )
        module_versions = self.reconcile_modules(
            realm=realm,
            space=space,
            owner=owner,
            attachments=attachments,
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

        posts_and_messages = [
            (
                post,
                self.reconcile_demo_message(
                    post,
                    post_number=post_number,
                    stream=stream,
                    sender=hover_user,
                    owner=owner,
                    attachments=attachments,
                    module_version=module_versions[post.module_key],
                ),
            )
            for post_number, post in enumerate(DEMO_POSTS, start=1)
        ]

        current_message_ids = [message.id for _post, message in posts_and_messages]
        stale_messages = list(
            Message.objects.filter(realm_id=realm.id, recipient=stream.recipient).exclude(
                id__in=current_message_ids
            )
        )
        if stale_messages:
            do_delete_messages(stream.realm, stale_messages, acting_user=owner)

        self.populate_search_vectors([message for _post, message in posts_and_messages])
        self.populate_home_views(viewer=viewer, posts_and_messages=posts_and_messages)

        self.stdout.write(
            self.style.SUCCESS(
                f"AIMTO Events is ready with {len(DEMO_POSTS)} native Hover posts, "
                f"{len(attachments)} live Sources, "
                f"{len(MODULE_NAMES)} enabled Modules, "
                f"{sum(post.for_you for post in DEMO_POSTS)} For You items, "
                f"{sum(post.saved for post in DEMO_POSTS)} Saved items, and "
                "3 Suggested Actions awaiting confirmation "
                f"in {realm.string_id}."
            )
        )
