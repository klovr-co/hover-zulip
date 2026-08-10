# Hover Wayfinding Context

## Working destination

Produce an implementation-ready MVP specification and decision map for Hover
as a single-organization KSK pilot. Hover should replace Monday as the primary
knowledge and review experience while Clawer remains the authoritative
ingestion and AI-processing backend. The product model should be able to
generalize beyond KSK without requiring the first build to support multiple
organizations.

## Product direction

Hover is an **organizational intelligence feed**: a collaborative company
memory that presents source-backed knowledge extracted from external
conversations and systems. It is not initially intended to replace WhatsApp,
email, or Slack as the place where those conversations happen.

The intended loop is:

```text
External conversation or system
  -> Clawer ingestion and extraction
  -> Hover knowledge item
  -> human awareness, verification, discussion, and action
```

### Authority boundary

- **Clawer** is authoritative for source ingestion, immutable source evidence,
  processing history, and initial AI-generated interpretations.
- **Hover** is authoritative for human corrections, AI Suggested Action review,
  active Todo state, assignment, reassignment, completion, and their audit
  histories.
- **Monday.com** is not required for Hover's runtime or human workflows. During
  migration it may remain an optional export or compatibility bridge, but it
  must not become a second writable authority for Hover-owned state.

## Three equally important product outcomes

The outcomes below are equal pillars of the intended product. Their order is a
delivery sequence, not a ranking of long-term importance.

1. **Better awareness of what matters — prove first.**
   Help people notice important signals, decisions, actions, and developments
   without manually checking every source system or conversation.
2. **Faster review and correction of Clawer's output.**
   Let people verify provenance, correct extracted facts, review AI Suggested
   Actions, and improve the reliability of organizational knowledge.
3. **Clearer ownership and completion of action items and Todos.**
   Let people turn knowledge into accountable action, identify responsibility,
   track progress, and close the loop visibly.

## MVP sequencing guardrail

The first user experience may emphasize reading and awareness, but it must not
model knowledge as an immutable, presentation-only feed. Knowledge items need
stable identity and room for provenance, verification state, discussion,
ownership, and resolution so the second and third outcomes can be added without
replacing the foundational data model.

## Awareness rhythm

The first habit-forming Hover experience will be a **Morning Daily Brief**.
It is Hover's presentation of Clawer's existing personalized **BOD PIC digest**,
not a collection of generic knowledge-item cards. Its promise is: open Hover at
the start of the workday and receive a clear, supportive plan for today without
checking every underlying conversation or system.

The existing BOD contract is the baseline:

- address the teammate directly;
- lead with groups needing attention, ordered by urgency;
- preserve unresolved work and supplied age/carryover context;
- give concrete actions the teammate can execute today;
- acknowledge groups that are all clear; and
- remain a concise authored briefing rather than exposing raw chat excerpts.

This preserves the BOD's **selection and prioritization logic**, not its
WhatsApp presentation. The plain-text greeting followed by warning/checkmark
sections and a flat bullet list is explicitly rejected for Hover. The Hover
version needs a native editorial hierarchy that feels like a composed morning
edition rather than a WhatsApp message placed inside a web page.

The existing BOD's managerial "attack plan" voice is also rejected. Hover's
Daily Brief should sound like an **encouraging personal assistant**: warm,
reassuring, observant, and specific about what would help today. It should make
the workload feel understandable and manageable, acknowledge what is already
going well, and suggest an order without barking commands or manufacturing
urgency.

Prefer language such as "A good place to start", "Once that's moving", "You
can leave this with...", and "Everything else is in good shape." Avoid routine
use of "attack plan", "needs you", "requires attention", militarized language,
or terse imperative-only instructions. This likely requires a Hover-specific
generation prompt over the BOD source state rather than displaying the existing
WhatsApp digest text verbatim.

A user-controlled **carousel** is a candidate presentation for this editorial
brief. Progressive disclosure may reduce mental load by showing the overview,
each focus area, deferred dependencies, and on-track work one step at a time.
This is recorded as a prototype TODO rather than a settled production decision.
The prototype must include progress, Back/Next navigation, accessibility and
reduced-motion behavior, and a "View all" alternative so information is never
trapped behind carousel navigation.

The carousel follows a **personal daily narrative**, not a project-based
sequence: greeting and overview, one focus at a time, dependencies the teammate
can leave with others, and a close showing what is already moving well. Project
organization belongs in each project's own digest and source views.

Each focus slide is prose-first: a warm, specific headline; a short narrative
explaining the current situation; one clearly labelled suggested next step; and
a link to open the relevant Space update. It does not show severity badges, raw
evidence, or dashboard-style metadata. The suggested next step is guidance in
the briefing, not an active Todo unless it has separately passed Hover's Todo
confirmation workflow.

In the mockup, this belongs at **Home -> Daily Brief**. It should read as one
intentional, personalized digest, with richer navigation available around it,
rather than as a dashboard of atomic evidence cards.

The project-level **3VEN Conversation Digest** (previously discussed as 3VEN
Daily Digest) is a different artifact: it summarizes what happened within that
Space or its source conversations. A teammate's BOD Daily Brief may draw
priorities from several such Space-level digests, but the two must not be
conflated.

An **End-of-Day Roundup** is also required. Clawer already produces retained
Group EOD and PIC digest outputs, so Hover should present that existing value as
the close-of-day counterpart to the Morning Daily Brief. It is a personal
closing narrative across the teammate's relevant Spaces: what meaningfully
moved, what the teammate completed, what remains open and carries forward,
what is safely waiting on someone else, and a reassuring preview of tomorrow.
It does not repeat every update or replace each Space's Conversation Digest.

Between those editions, separate **For You** and **Team Pulse** feed surfaces
provide live awareness during the workday. "Continuously updated" means
event-driven: when Clawer finishes processing enough new evidence to create a
meaningful update, or changes the state of an existing one, the result can
appear in the appropriate feed. It does not mean copying every raw message into
the feed or regenerating the whole feed every few seconds.

Publication timing is urgency-aware:

- urgent blockers, decisions, and newly assigned actions publish as soon as
  the producing AI Module creates a validated update;
- routine developments wait through a 15-minute accumulation window so related
  evidence becomes one concise update; and
- a later post appears only when the situation materially changes.

Sentiment detection is not implicit platform behavior. Negative-sentiment
updates exist only when a Sentiment Detection AI Module is enabled for the
Space. Without that Module, Hover neither classifies sentiment nor publishes a
sentiment-derived update. When enabled, its validated outputs follow the same
publication rules and may identify a material negative development as urgent.

Both feeds present concise, source-backed Hover updates rather than individual
raw messages. For example, several WhatsApp messages about a delayed approval
become one update explaining the blocker, current responsibility, and next
development. The update links to its supporting messages for verification; raw
conversation content remains in the relevant Space source view.

When later evidence materially changes the same development, the Space retains
each chronological Hover post, while For You and Team Pulse show the latest
meaningful state by default. The feed item indicates that earlier updates exist
and offers **View history** rather than presenting stale and current states as
separate competing items. This is a projection of the linked development
history, not a copied or rewritten record.

**For You** contains updates connected to the current teammate's work,
assigned Todos, or other personally relevant conversations from Spaces where
they have been explicitly added as a Contributor or Subscriber. **Team Pulse**
provides the wider picture across that same set of Space memberships, including
important developments in which they are not personally involved. Neither feed
draws from every Space in the organization merely because it exists, and there
is no separate follow or subscribe toggle. The two feeds may reference the
same underlying update; they are different audience and ranking lenses rather
than duplicate records.

For a Space where the teammate is a **Contributor**, For You includes relevant
day-to-day developments. For a Space where the teammate is a **Subscriber**,
For You normally includes only important developments such as decisions,
blockers, milestones, and major changes. A Subscriber can still open the Space
to inspect its complete update history. Contributor/Subscriber changes feed
attention, not content access or collaboration permissions.

Hover-generated updates are visible in their Space as soon as they are posted
but are quiet by default. Hover sends an immediate notification only when the
teammate is assigned, directly mentioned, or explicitly asked to review. Other
updates reach teammates through the Space history, For You, Team Pulse, Daily
Brief, or End-of-Day Roundup according to relevance and importance rather than
notifying every Space member.

Ordinary Hover updates use normal read/unread state and do not require a
teammate to acknowledge, approve, or dismiss them. They are awareness content,
not an inbox that must be cleared. Only an explicit Review request, an AI
Suggested Action awaiting a human decision, or an active Todo creates a required
response or workflow state.

The intended daily rhythm is:

```text
Morning BOD Daily Brief -> For You / Team Pulse during the day -> End-of-Day Roundup
```

The Morning Daily Brief and End-of-Day Roundup are authored digest editions.
The feeds, source and project views, review queues, and ownership workflows are
separate ways to inspect and act on the changing operational state that informs
those digests. Selecting a digest passage first opens the relevant concise
Hover update inside its Space, where the teammate can see current status,
discussion, Review, and Todo context. **View sources** from that update is the
second step to the underlying WhatsApp, Instagram, GitHub, or other evidence.
The digest itself does not expose raw evidence cards or inline review machinery.

## First audience

The first personalized Daily Brief is for the KSK staff member currently
described as an "operational PIC": a person responsible for keeping assigned
work, projects, or source conversations moving.

The preferred provisional language separates identity from responsibility:

- **Teammate:** The person using Hover and receiving a personalized brief.
- **Owner:** A teammate's accountability relationship to a knowledge item or
  piece of work.

With this language, Hover can say: "Each teammate receives a Daily Brief based
on the work they own and the Spaces where they contribute or subscribe." This
avoids making "PIC" a permanent product role and generalizes beyond KSK.

## Feed personalization

The two live feed surfaces serve different awareness needs:

1. **For You:** Personalized knowledge selected from the teammate's Contributor
   and Subscriber Spaces, assigned work, direct mentions, and other individual
   relevance signals.
2. **Team Pulse:** Important developments across the same Contributor and
   Subscriber Spaces that the teammate should understand beyond their own
   responsibilities.

For You is individually ranked using signals such as assignment, ownership,
mentions, and activity. Team Pulse uses shared importance instead: two
teammates with the same Space memberships should receive the same important
developments in Team Pulse, while their For You feeds may differ. Teammates
with different Space memberships naturally receive different Team Pulse
results because neither may see updates from a Space where they are not a
member.

**Topics You Follow is removed from the product model.** Hover does not create
a separate personal topic-subscription system. Topic Analysis remains an
optional AI Module that produces source-backed outputs inside its configured
scope; it does not alter feed eligibility or grant access.

The first product has no standalone **People & Teams** navigation item. A
Space's member view shows its Contributors, Subscribers, and Space Admins;
organization Settings contains the teammate directory and permission groups.
Hover may reuse Zulip user groups later if named internal Teams become useful,
without introducing a separate Team domain model for AIMTO.

Contributor and Subscriber are the only Space-membership relationships used
for feed eligibility. **Subscriber** itself means the teammate follows the
Space for awareness; it is not a second opt-in switch. Space Admin is an
orthogonal permission held by a confirmed Space member and does not widen the
feeds to unrelated organization Spaces.

"Across KSK" was explicitly rejected as the shared-awareness label. Team Pulse
works for KSK while remaining suitable for Hover organizations generally.

## Space, Category, and Source model

**Space** is the underlying umbrella term for a context such as 3VEN. Hover
rarely needs to expose that generic word in everyday navigation because each
organization can create its own user-facing **Categories**.

Categories replace a fixed Type enum. Examples might include Clients, Projects,
Programs, Campaigns, Departments, or any organization-specific grouping. Thus
3VEN can be a Space in the Clients category without forcing every Hover
organization into the same taxonomy.

Each Space belongs to exactly **one primary Category** for predictable
navigation. Tags and explicit relationships may express secondary or
cross-cutting classifications without duplicating the Space under several
sidebar categories.

Every Space remains **flat**. Spaces do not contain child Spaces and do not
inherit Sources, teammates, permissions, or generated outputs from one another.
Related Spaces may be linked explicitly without creating a navigation or
ownership hierarchy.

A Space is a named work context that selects relevant material from the shared
data lake and combines it with teammate activity and Hover-generated outputs.
The source systems themselves are not the Space.

The product architecture separates raw evidence, Space context, AI Modules,
and presentation surfaces:

```text
Organization raw data lake
WhatsApp | Gmail/Email | GitHub | other integrations
                         |
                         | selected Sources link records
                         v
Space context (for example, 3VEN)
All | Whiteboard
WhatsApp | Email | GitHub | other selected source views
                         |
                         | enabled AI Module instances
                         v
AI Module layer
Todo | Progress Tracker | Conversation Digest | Signal Monitor
Daily Brief | Marketing Digest | Topic Analysis | custom Modules
                         |
                         | Space-scoped or cross-Space presentation
                         v
Hover surfaces
Space module tabs and All filters
Home: For You | Team Pulse | Daily Brief | Todos
```

The Space's WhatsApp, Email, GitHub, and future integration views expose the
underlying data-lake records selected by its configured Sources: complete
WhatsApp conversation history, email threads, GitHub issues/pull requests/events,
attachments, timestamps, identities, and source metadata as applicable. These
views are intentionally the searchable source "brain dump," not feeds of
pre-summarized Hover updates. Whiteboard is Space-native collaborative content
alongside those source views. Raw Source views are read-only: Hover does not
send composer messages back to WhatsApp, Instagram, GitHub, or other external
systems in the first product. Teammates create human-authored Space posts in
All/Whiteboard and add Replies or Reviews beneath Hover updates.

Todo, Decision Capture, Progress Tracker, Conversation Digest, Daily Brief,
Weekly Roundup, Signal Monitor, Marketing Digest, Topic Analysis, and future
custom capabilities are all **AI Modules**. A Module
instance may be scoped to one Space or may aggregate and personalize across
accessible Spaces for Home. For example, the Todo Module produces Space-level
Suggested Actions and active Todo views while Home Todos aggregates those same
records; the Daily Brief Module composes a personal cross-Space edition.
Generated records are not duplicated between Space and Home presentations, and
every output can link back to the relevant raw source records or Whiteboard
context.

**AI Slides is removed from the product model.** It originated as an unexplored
mockup idea for generated presentations, but no user need or processing
contract was established for it.

### All view and configurable AI Modules

**All** is a unified, filterable Space view. By default it shows human-authored
Space posts and updates generated by every AI Module enabled for that Space.
It does not show the raw WhatsApp, Instagram, GitHub, Email, or other Source
records by default.

A teammate can selectively include or isolate any available Source or Module
through the filters. This changes only the current view: the raw Source records
remain available as evidence, and the human or AI-generated posts continue to
reference them without being duplicated.

### Search

Hover search spans every Space where the teammate is a confirmed Contributor
or Subscriber. It returns human-authored posts, AI-generated updates, and raw
WhatsApp, Instagram, GitHub, Email, or other Source records. Default ranking
favours concise human and AI updates; raw records are clearly labelled as
**Sources** and remain available for exact evidence retrieval. Results never
include a Space or Source the teammate cannot access.

Native Zulip Messages can use Zulip search. External raw records that remain
authoritative in Clawer or another data-lake service participate through a
permission-filtered search adapter or index; global search does not require
copying authority for those records into Hover.

The first AIMTO pilot returns search results rather than generating a direct
answer. **Ask Hover** is deferred until permission filtering, ranking, and
source provenance have proved trustworthy. A future Ask Hover action may
synthesize a concise cited answer from the same permission-filtered search
interface while keeping the underlying results available for verification.

### Saved

**Saved** is the teammate's private collection of bookmarked human-authored
posts and AI-generated updates. The AIMTO pilot reuses Zulip's existing
per-user starred-message state rather than introducing a separate Hover record.
A saved entry references the live post, so Reviews and status changes remain
current rather than freezing a private snapshot. Saving raw external Source
records is deferred because Clawer-backed evidence is not uniformly represented
as a native Zulip Message.

Todo, Decision Capture, Progress Tracker, Conversation Digest, Daily Brief,
Weekly Roundup, Signal Monitor, Marketing Digest, and Topic Analysis are
examples of configurable **AI Modules**, not a hard-coded complete list. A
Space Admin can enable only the Space-scoped Modules
appropriate to the Space. Each Module declares its allowed scope, the source
data or other capabilities it requires, and the Space or Home surfaces it can
contribute. The UI may expose friendlier labels for individual Modules, while
**AI Module** is the underlying domain term.

The mockup's fixed **Customer Signals** concept is replaced by an optional
**Signal Monitor** Module. A Space Admin can configure its detection criteria
and give the installation a context-appropriate display name, such as Audience
Signals for AIMTO, Client Signals, or Risk Signals. It emits existing Feed
Update or Analysis outputs and therefore does not introduce another canonical
output contract.

Informational Module outputs such as Conversation Digests, Progress Tracker
updates, Topic Analysis, and the updates collected by Team Pulse publish
automatically when processing succeeds. They include source links and remain
correctable through the visible audit history; they do not wait in a mandatory
approval queue before teammates can benefit from them. Outputs that create
accountable work use a stricter policy: an AI Suggested Action may appear for
review, but it becomes an active Todo only after a teammate confirms it.

**AI Builder** is an additional organization-level role that can be assigned
to a teammate independently of their Space relationships and permissions. An
AI Builder may also be a Contributor, Subscriber, or Space Admin, but none of
those Space roles grants AI Builder automatically. Organization Admins receive
AI Builder automatically and may assign or revoke it for other confirmed
teammates. Any AI Builder may create, edit, and publish any AI Module directly
to the organization's Module Library;
there are no per-Module owner, maintainer, or fork permissions and no second
Organization Admin approval. Each edit creates a new draft and publishing
creates a new immutable version rather than modifying a version already used.
The Module history records every editor and publisher so teammates can assess
its provenance and generated outputs can identify the exact published version
used. Publishing makes a version available; it is distinct from enabling that
version to process data or contribute outputs in a particular scope. AI Builder
does not itself grant access to any Space's Sources; previews and test runs may
use only data the builder can already access through Space membership.

A Space Admin enables or disables Space-scoped Modules for their Space because
that decision grants the Module processing access to the Space's configured
Sources. Contributors and Subscribers may use, review, and correct the enabled
Module's outputs but do not enable additional Space processing themselves.
The reusable Module definition declares the Integration types and Source
capabilities it requires, such as one or more WhatsApp Sources and optional
Email Sources; it never hard-codes a particular account, WhatsApp Group,
mailbox rule, or repository. When enabling the Module, the Space Admin binds
those requirements to specific Sources already configured in that Space. The
Module may process only those selected Sources.

By default, a newly enabled Module processes only material arriving after its
activation time. During enablement, the Space Admin may explicitly request an
initial backfill such as the last 7 days, the last 30 days, or a custom period
within the history already available through the selected Sources. Hover never
processes the complete available Source history for a new Module installation
without explicit confirmation.

Module execution supports three configurable trigger modes: new Source
material, a schedule, and a manual run. An event-triggered installation uses a
debounce or accumulation window rather than running once for every raw event.
A scheduled installation records its cadence and timezone when it is enabled.
A Module may support more than one trigger mode, and the mode is not inferred
from its product label: Topic Analysis, for example, may run on a schedule as
well as manually or after new material.

A Module may consume the structured outputs of other enabled Modules as well
as raw Sources. Dependencies are explicit in the published definition and
execution graph, and Hover rejects direct or indirect dependency cycles. This
allows a Daily Brief to compose Conversation Digests, Progress Tracker updates,
and confirmed Todos without independently reprocessing every raw conversation.
Each consumed record retains its original Module version and source provenance
through the downstream output.

Module dependencies bind to a compatible, versioned output contract rather
than a hard-coded built-in Module name. For example, Daily Brief may request
Digest outputs, Progress updates, and confirmed Todos. A Space may satisfy the
Digest input using Hover's default Conversation Digest or a custom published
Module that implements the same contract. Enablement validates compatibility
before processing begins.

The initial canonical Module message/output contracts are:

- **Feed Update:** A concise awareness item with a title, summary, importance,
  and supporting Sources.
- **Digest:** A narrative edition with structured sections, a covered period,
  and supporting Sources.
- **Suggested Action:** A proposed action with an optional assignee and due
  date plus supporting Sources. It requires human confirmation before becoming
  an active Todo.
- **Progress Update:** The evolving operational state of work, including
  status, what changed, blockers, milestones, and supporting Sources.
- **Decision:** An agreed decision, participants or deciders, decision time,
  rationale when available, supporting Sources, and lifecycle state of active,
  superseded, or reversed.
- **Analysis:** A topic or question, structured findings, and supporting
  evidence, with room for Module-specific fields.

An enabled **Decision Capture** Module produces Decision outputs. Each appears
as an AI-generated update in All and in a dedicated Decisions filter. A later
superseding or reversing decision creates a new chronological post and updates
the structured lifecycle link; it does not rewrite the earlier decision.

A Space tab is a channel-like chronological message stream, not a visible
representation of a Module run or output-contract taxonomy. Teammates simply see
updates posted into the stream; Hover does not group them under a run, label the
internal contract, or show retry/validation machinery in the normal interface.
A Module may post one or several messages to a stream from one bounded evidence
window. The same results may instead be produced by separate Modules, and more
than one Module may publish into the same stream. Module-to-stream routing is a
configuration choice rather than a rule that one Module must equal one sidebar
tab. Each message still carries its own identity, producing Module and version,
output contract, provenance, and contract-specific state such as Suggested
Action approval for audit and processing. For You, Team Pulse, Home Todos, and
other surfaces reference those same messages or their confirmed state rather
than creating copies.

All AI-generated updates appear conversationally from one consistent assistant
identity: **Hover**. Individual Modules do not appear as separate bot personas.
The producing Module and immutable version remain available with Sources and
other provenance under the update's details for trust, auditing, and debugging.

When new Source evidence materially changes a previously reported situation,
Hover publishes a new follow-up message in the same Space stream rather than
overwriting the earlier post. The original and follow-up preserve the timeline
of what the team knew at each point, while provenance links the related
developments. This is distinct from a teammate Review: a Review remains attached
to the original post as its visible confirmation or revision history and does
not masquerade as a newly observed operational development.

When responding beneath an AI-generated update, a teammate chooses a reply type:
**Reply** or **Review**. Reply is ordinary discussion. Review declares that the
teammate is evaluating Hover's derived knowledge and may confirm, refine, or
challenge it. When the review specifies a change, choosing Review serves as the
teammate's confirmation rather than requiring a second approval prompt. Both
types remain visibly threaded with the update and become Space-native,
human-authored context eligible for future Module runs. Hover preserves each
response's type, author, and timestamp and distinguishes human responses,
imported Source records, and prior AI outputs in provenance so a Module can use
the conversation without treating its own earlier wording as new human evidence.

These contracts describe Hover's downstream behavior and presentation needs;
they are not limited to the shapes emitted by current Clawer pipelines. Existing
Clawer news, journals and Cappy Briefs, group Todos, Group EOD updates,
sentiment results, marketing outputs, and collection extractions can be
normalized into the appropriate contracts. Progress Update remains distinct
from Feed Update: a Progress Update models state and movement over time, though
Hover may present an important Progress Update within For You or Team Pulse.

Each teammate may enable or disable a personal cross-Space Module, such as
their Daily Brief, for themselves; it can read only the Spaces where that
teammate is already a Contributor or Subscriber. Home aggregation does not
grant additional source access.

An enabled Module installation is pinned to an immutable published version.
Publishing a newer version does not silently change existing processing or
outputs. Hover shows the available update and its change history; the Space
Admin explicitly upgrades a Space-scoped installation, while the teammate
explicitly upgrades their own personal Module. Each generated record and run
retains the exact Module version that produced it.

A published Module version that has been used cannot be deleted. An AI Builder
may deprecate the Module, removing it from new enablement while retaining its
definitions, installation history, runs, and generated-record provenance.
Existing pinned installations continue until their responsible Space Admin or
teammate replaces or disables them. An Organization Admin may emergency-disable
an unsafe Module across the organization; this stops future processing without
erasing historical versions or outputs.

### MVP sequencing

The visual AI Module Builder does not gate the first usable Hover release. MVP 1
proves the end-to-end reading and collaboration experience using a small set of
prebuilt Modules: Spaces and Sources, Home feeds and digests, Hover's
channel-like generated posts, Reply and Review, Suggested Actions, and Todos.
Space Admins can enable and configure the available prebuilt Modules.

Custom visual Module authoring, versioning, and publication may follow as MVP 2
or be developed separately in parallel. Parallel work remains compatible because
the Builder publishes through Hover's owned versioned Module definition and
output contracts; it does not define a separate runtime or presentation model.

### Initial pilot Space

**AIMTO Events** is the first and only initial Space for the controlled KSK
pilot. It is manually created through the normal Setup and Launch flow, placed
in the organization's chosen custom Category, and configured with its relevant
Sources, teammates, Space Admins, and prebuilt Modules. Event operations provide
a useful test of changing logistics, deadlines, external communication,
decisions, progress, and action ownership.

AIMTO launches with Conversation Digest, Progress Tracker, Todo, Decision
Capture, Marketing Digest, and Topic Analysis enabled for the Space. Morning
Daily Brief and End-of-Day Roundup are enabled for the pilot teammates as
personal cross-Space Modules. Signal Monitor remains available but off by
default, and Weekly Roundup remains outside the pilot.

AIMTO Events initially uses three live Source paths: its relevant WhatsApp
Groups through Clawer, Instagram scraper output from Apify through Zulip's
Slack-compatible incoming webhook, and GitHub repository events through
Zulip's native GitHub integration. It has no Email Source. Apify and GitHub do
not require new custom connector adapters for this live-event path.

These webhook paths begin collecting new events when connected; they do not by
themselves provide historical Instagram or repository backfill. Durable capture
of ephemeral Instagram media and complete GitHub history remain optional richer
Source capabilities if AIMTO later needs them. Candidate Spaces for later
rollout are **3VEN**, **firm.ai**, **BWAI**, and **Aldrent**. They do not gate or
share the initial AIMTO launch.

### AI Module Builder direction

Hover needs a visual AI Module Builder inspired by Langflow, but should not
rebuild the graph canvas, connection handling, history, variable inspection,
and node-form machinery from scratch or embed an entire external AI platform.

The leading spike candidate is **FlowGram.AI**. It is an MIT-licensed,
React/TypeScript workflow-development toolkit rather than a ready-made
platform, and includes free/fixed-layout canvases, node forms, variable scope,
history, validation support, and AI-oriented materials. **React Flow** is the
fallback: it is more mature and has stronger documented keyboard and screen
reader support, but supplies canvas primitives rather than the higher-level
builder machinery, so Hover would implement more itself. **Rete.js** remains a
framework-neutral alternative but has a wider plugin interface and higher
composition overhead. Langflow and Node-RED are full runtimes/platforms and are
not recommended as the embedded Hover editor.

This Zulip fork currently uses TypeScript, Handlebars, and Webpack without an
active React application layer. Both FlowGram and React Flow therefore require
an isolated React builder bundle mounted as an island inside the existing Hover
shell, rather than converting the whole frontend to React.

The external canvas library must remain an adapter, not Hover's persistence or
execution contract. Hover owns a versioned `ModuleDefinition` containing
semantic nodes, typed ports, edges, configuration, scope, required sources,
publication targets, and scheduling. Library-specific node geometry and editor
state map to and from that definition through a canvas adapter. Published
Modules never persist FlowGram-, React Flow-, or Rete-specific graph objects as
their authoritative definition.

Execution remains server-side. A Module compiler validates and publishes a
definition; a Module runner resolves permitted Space Sources and invokes
Clawer/Temporal processing through an owned remote seam. The first builder node
catalog should be deliberately constrained to source selection, filtering,
prompt/analysis, structured output, human-review policy, scheduling, and
publication. Arbitrary Python/JavaScript execution and a Langflow-sized
component marketplace are outside the first version.

### AI Module execution direction

FlowGram or React Flow supplies the visual editor; it does not durably execute
published Modules. For the present architecture, **Temporal remains the runtime
owner for AI Module executions**. Clawer already operates a substantial
Temporal implementation for journals, WhatsApp reconciliation, sentiment,
briefs, EOD/BOD digests, marketing ingestion, exports, backups, and other
scheduled or long-running work. Introducing a second durable engine for Hover
Modules would split execution history, recovery, scheduling, and operational
ownership without yet removing the existing Temporal obligations.

The Module compiler should freeze a published `ModuleDefinition` version into
a validated execution plan. Clawer can execute that plan through one generic,
deterministic `HoverModuleWorkflow` rather than generating a new Temporal
Workflow class for every user-authored Module. Source reads, AI calls, database
writes, and publication remain retry-safe Activities. A Module that requires
human review may wait durably and resume from a recorded Temporal Signal or
Update; recurring Module runs use Temporal Schedules. Each execution pins its
Module version, source policy, publication policy, and stable business ID so a
retry cannot silently adopt a newly edited definition.

Hover should expose its own small execution interface across the Hover-to-
Clawer seam—submit a pinned run, inspect it, deliver a human decision, and
cancel it—rather than leaking Temporal workflow types and identifiers into the
product domain. Temporal is an implementation behind that seam, but there is
no need to build and maintain both Temporal and DBOS adapters before a second
runtime is actually required.

**DBOS is a credible future replacement candidate, not an additional runtime
for the first version.** It offers lightweight durable workflows, queues,
schedules, and human-in-the-loop waits backed by Postgres and avoids operating
a separate orchestration server. It becomes worth a bounded comparison if
Hover later moves Module execution out of Clawer, standardizes the execution
tier on Postgres, and plans to retire the existing Temporal workflows. Clawer
currently uses SQLite for application state and already bundles and supervises
Temporal, so adopting DBOS now would also introduce Postgres into that runtime
or place Module execution on the other side of the established Clawer seam.
Do not run the same Module schedule or accepted execution in both engines.

Before selection, run a bounded FlowGram spike that proves: mounting in the
Webpack/Handlebars shell, Hover styling, keyboard interaction, serialization
through the Hover-owned schema, one source-to-digest graph, one
source-to-Suggested-Action graph, validation, preview, and bundle-size impact.
Fall back to React Flow if FlowGram cannot meet the integration, accessibility,
or schema-isolation requirements cleanly.

A newly created Space begins in **Setup** rather than immediately becoming
active. During Setup, only its creator and added Space Admins can see it. They
complete the Space name and Category, select accessible Sources, review
suggested teammates and Contributor/Subscriber relationships, add other Space
Admins, enable prebuilt Modules, and choose each initial history window. Source
selection may support private previews and suggestions, but Hover does not
publish generated posts, grant confirmed members active Space access, or notify
them before launch. **Launch Space** activates the confirmed membership and
configured processing together.

There is no standalone globally browsable **Sources** navigation page. Ordinary
teammates inspect attached raw records through the current Space's Source
filters. Space Admins attach or remove Sources in that Space's Setup or
Settings. Organization Admins manage Integrations, Connected Accounts, and
account assignments in organization Settings; this administrative inventory
does not expose every account's raw records as a global browser.

Source selection is configured within each Space:

- A teammate manually creates 3VEN and places it in an existing or newly
  created Category.
- They choose which kinds of data-lake Sources the Space should include.
- A **WhatsApp Source** selects the relevant WhatsApp Groups.
- An **Email Source** defines matching rules such as recipient addresses and
  recipient email domains or subdomains.
- Future source types can define their own explicit matching rules.
- Hover does not auto-create Spaces or silently infer their Sources in the first
  version.

When adding a Source, the Space Admin previews the matching data and explicitly
chooses its historical window: start from today, use a standard lookback such
as the last 30 days, or select a custom start date. After that initial backfill,
the Source continuously includes new matching data. Hover never imports all
available history into a Space without an explicit choice.

Detaching a Source stops new ingestion and prevents future Module processing
from that Source. Existing posts, evidence links, and audit history remain
visible to authorized Space members under a **Detached** label. Permanent
evidence deletion is a separate destructive Organization Admin action, not an
effect of ordinary Source detachment.

Source access follows a three-level hierarchy:

```text
Integration -> Connected Account -> Source selection
WhatsApp    -> Account 1         -> WhatsApp Group A
Email       -> Account 1         -> email address, recipient, domain, or subdomain rule
GitHub      -> integration bot   -> repository and event route
Apify       -> webhook bot       -> Instagram scraper output route
```

**Connected Account** is the authenticated or ingested account beneath a
Connector; this avoids confusing it with a Hover teammate or client account.
Organization admins can manage all Connected Accounts. A Space Admin may add
or broaden Sources only through Connected Accounts assigned to that teammate.
Thus permission for a broad Email Source depends first on access to the relevant
Email Connected Account, not merely on the person's Space Admin role.

A Connected Account assignment grants access to the whole account by default,
but it may carry optional selector restrictions. Organization policy can limit
a teammate to particular WhatsApp Groups, email addresses or mailboxes, or
email domains/subdomains within the assigned account. A Source must satisfy
both the Connected Account assignment and any restrictions on that assignment.

Only **organization admins** may assign, restrict, or revoke Connected Account
access. Connected Account users and Space Admins cannot delegate this access to
other teammates.

Teammates may connect their own WhatsApp or email accounts. A newly connected
account is private to that teammate by default and cannot supply Sources to a
shared Space until an organization admin approves it. Approval makes the
account eligible for explicit assignment; it does not automatically expose its
data or attach it to any Space.

WhatsApp, email, and GitHub are important first use cases, not the boundary of
Hover's source catalog. Because Hover is being built on Zulip, it should by
nature expose a much broader connector ecosystem:

- Zulip-native integrations become first-class Hover Connectors.
- Services that emit Slack-compatible incoming webhooks can enter through a
  generic Slack-compatible Connector.
- Generic incoming webhooks and the Zulip REST API provide an extension path
  for services without a packaged integration.
- Hover-specific adapters may add richer history, resource discovery, identity
  matching, provenance, and filtering than a webhook-only Connector can offer.

The catalog therefore must be capability-driven rather than defined by a fixed
enum of WhatsApp, Email, and GitHub. Connector definitions should declare what
they support, such as Connected Accounts, resource discovery, historical
backfill, event filters, attachments, replies/threads, and source identity.
Sources can then render the selectors appropriate to each Connector rather than
assuming every source has WhatsApp groups, email rules, or GitHub repositories.

Existing Clawer-generated BOD, EOD, group-digest, todo, and collection outputs
are also inputs to Hover's generated experiences.

Current Clawer has a signal-driven, debounced `GroupJournalWorkflow` for tracked
WhatsApp groups. It regenerates one group/day journal containing narrative,
source-anchored news, and group Todos, and exposes group-news and group-Todo
APIs. This can seed some WhatsApp-derived Hover experiences. It is not yet a
generic continuous-update pipeline across WhatsApp, Gmail, GitHub, and the
broader connector catalog. The implementation plan must therefore treat a
cross-source normalized derivation/publication pipeline as new work rather than
assume every raw data-lake source already emits Hover updates.

WhatsApp is a required, working, first-class Connector for Hover's initial
product; it is not merely an example or optional future integration. The first
release must support the complete WhatsApp path from Connected Account and
group selection through evidence, Sources, feeds, and digests, using the current
Clawer pipeline where appropriate.

Matrix may be incorporated later. Once the Matrix path has proven sufficient,
Hover expects to deprecate the direct WhatsApp Connector through an explicit
migration period rather than remove it abruptly. Core Space-to-Source,
conversation, and evidence identities must therefore remain independent of
WhatsApp-, Matrix-, or other connector-specific IDs and schemas. Connector
adapters normalize source identities and events at the data-lake boundary so
existing Spaces, history, citations, and generated outputs can survive that
transition.

A source event may match or be deliberately linked to more than one Space.
Those links reference the same data-lake evidence rather than duplicating it.

Space teammate onboarding is **suggested, not fully manual**:

- Hover uses existing phone-number mappings and, where available, email
  mappings to identify known teammates participating in a Space's tracked
  conversations.
- The onboarding page presents those matched teammates as smart suggestions for
  Space access.
- For each known teammate suggestion, Hover may also recommend Contributor or
  Subscriber based on participation in the selected source conversations. The
  Space creator reviews and confirms that relationship along with access;
  Hover never assigns it silently.
- Teammates who do not appear in the tracked source conversations can still be
  found and added explicitly.
- Presence in a tracked conversation alone must not turn an external
  participant into a Hover teammate or grant access. A suggestion needs to
  resolve to a known teammate identity.
- The creator reviews and explicitly confirms the suggested teammate list
  before anyone receives access. New matches discovered later remain pending
  suggestions until reviewed; Hover never grants access silently.

The first AIMTO pilot is internal to authenticated KSK organization teammates.
External clients, sponsors, attendees, or other participants may appear as
Source identities but cannot become Contributors, Subscribers, or Space Admins.
A future guest-account model is separate product work; a client-oriented Space
does not itself imply client login access.

Removing a teammate from a Space immediately revokes that Space's posts, raw
Sources, search results, Saved references, and notifications for that teammate.
Their earlier posts, Reviews, approvals, and other audit events remain in the
Space with their original authorship.

Space creation is controlled by an explicit organization-level permission:

- A person must first be a confirmed Hover teammate.
- The teammate must have **Can create Spaces** permission within the
  organization.
- Organization admins receive **Can create Spaces** automatically and may grant
  or revoke it for other confirmed teammates.
- Detection in a Source or suggestion for Space access never grants this
  organization-level capability.
- The teammate who creates a Space becomes its first **Space Admin**.

Each Space may have multiple Space Admins. An existing Space Admin can promote
another confirmed teammate in that Space to Space Admin, and organization
admins retain an override for managing Space Admin assignments. **Owner** is
reserved for a teammate's accountability relationship to work or knowledge; it
is not an access-control role.

For the first version, Space Admin is one combined role. Space Admins can
configure the Space's Sources, review and manage teammate access, and add or
remove other Space Admins. These capabilities are not split into separate
source-management and membership-management roles.

Within each Space, use **Contributor** and **Subscriber** as the provisional
teammate relationship labels:

- A Contributor is actively working in the Space.
- A Subscriber follows the Space for awareness without being part of its
  everyday work.

Subscriber is not a read-only permission. Subscribers may still review and
approve AI Suggested Actions, correct generated items, complete Todos, comment,
and otherwise participate when needed. This approval specifically turns a
Suggested Action into an active Todo; it does not refer to approving summaries
or operational matters such as budgets and deliverables.
Contributor/Subscriber primarily informs relevance, feed ranking, and
notification behavior. **Space Admin** remains a separate permission role
rather than a third level on the same scale.

## Collaborative review

Any confirmed teammate with access to a Space may review and correct a
Hover-generated summary, decision, action item, owner, date, signal, or other
derived knowledge item. Review does not require approval from a Space Admin or
from the teammate named in the item.

Every correction leaves a visible audit record containing the previous value,
the new value, the teammate who made the change, and the time of the change. A
teammate may also include an explanatory note. The supporting WhatsApp message,
email, GitHub event, or other original source evidence remains immutable and
available for comparison; correcting Hover's interpretation never rewrites the
source evidence. If a Review requests a change but does not identify it
unambiguously, Hover asks the teammate to clarify rather than silently changing
the derived record. An ordinary Reply may inform future Module output but does
not by itself revise the current record.

When credible Sources disagree, Hover publishes the useful supported parts of
the update and marks the disputed detail **Needs review** rather than stating it
as fact or withholding the entire update. The detail links to each conflicting
Source. Needs review becomes an explicit Review request only when the ambiguity
materially affects a decision or action; ordinary uncertainty remains visible
without automatically interrupting teammates.

A material Review request notifies the teammate or teammates directly involved
in the disputed detail. If Hover cannot identify a relevant teammate, it routes
the notification to a Space Admin. Notification routing creates initial
responsibility but does not restrict participation: any Contributor or
Subscriber in the Space may submit the Review.

## Action items and Todos

When Hover interprets a source conversation as containing a possible action
item, it creates an **AI Suggested Action**, not an immediately accountable
Todo. A teammate reviews the suggestion against its linked source evidence and
approves it before it becomes an active Todo. Approval should include review of
its wording, assigned teammate, and due date where those details exist.

Any confirmed teammate with access to the Space, whether Contributor or
Subscriber, may approve an AI Suggested Action. The assigned teammate is then
notified and may correct or reassign it. Hover records the approval, assignment,
corrections, and reassignments in the Todo's visible history.

Contributors and Subscribers may also mark an AI Suggested Action **Not an
action**. This is a reversible dismissal, not deletion: Hover preserves the
suggestion, actor, timestamp, source evidence, and an optional reason such as
AI misunderstood, already completed, or duplicate. Any teammate with Space
access may restore the suggestion through another recorded state change.

Any confirmed teammate with access to the Space may also mark an active Todo
complete. If someone other than the assigned teammate completes it, Hover
notifies the assignee. The completion actor and timestamp remain visible in the
Todo history, and an incorrect completion can be corrected through another
recorded state change rather than erasing history.

Use **action item** or **Todo** in product and planning language. Avoid the vague
term **follow-up** for this concept.

Use **WhatsApp Group** for the external source conversation and **Team** for an
internal collection of teammates. Avoid the unqualified term "Group" where the
meaning would be ambiguous.

## Provisional language

These terms are working language, not yet a settled domain glossary:

- **Knowledge item:** A source-backed unit presented in Hover, potentially
  classified as a signal, decision, action item, highlight, brief, or system
  update.
- **Source:** The external conversation or system from which evidence entered
  Clawer.
- **Provenance:** The evidence and processing history supporting a knowledge
  item.

## Open decisions

- Validate whether the carousel improves comprehension and mental load over a
  scrollable editorial edition.
