# Hover

Hover is an organizational intelligence feed that turns activity from external
conversations and systems into source-backed posts, updates, and follow-up work.

## Language

**Space**:
A flat organizational feed with members, human posts, and AI-generated updates.
Spaces may have a built-in or custom category.
_Avoid_: Channel, stream, workspace

**Connected Account**:
An organization-approved connection through which a teammate may be granted
access to specific external Sources. It names the connection without exposing
credentials, provider identifiers, or deployment topology.
_Avoid_: Login, credential, bot session

**Source**:
A provider-neutral external feed identity discovered through a Connected
Account. Provider-specific selectors, such as a WhatsApp Group, are adapter
details; Hover stores only an opaque Source reference and safe identifying
metadata.
_Avoid_: Chat ID, JID, phone number

**Space Attachment**:
The durable association between a Space and a Source. It records the actor and
an immutable, explicitly bounded history start in UTC for later ingestion. A
detached attachment can retain its bounded history for authorized, read-only
browsing without continuing to represent an active connection.
_Avoid_: Import, sync run, all history

**Source Record**:
A transient, read-only projection of a record fetched from an attached Source
within its approved history boundary. Hover exposes only safe display fields
and never stores the provider record or turns browsing into a Zulip message.
_Avoid_: Imported message, raw provider event, synced chat

**Integration Route**:
An explicitly configured live association between one dedicated native incoming
webhook bot, the exact channel of a launched Space, and one Space Attachment.
It labels only messages received while the route is active; it never backfills
earlier messages.
_Avoid_: Webhook credential, historical import, provider-specific route

**Source Provenance**:
An immutable, safe snapshot linking a native integration Message to the Source
whose active Integration Route captured it. It includes configured display
metadata and an optional HTTPS link, never credentials or opaque adapter IDs.
_Avoid_: Generated Item, raw webhook payload

**Module Definition**:
A realm-scoped stable identity for reusable Hover automation. Published Module
Versions carry its execution and presentation contracts; changing those
contracts never mutates the definition or an existing version.
_Avoid_: Prompt, bot, mutable template

**Module Installation**:
A Space-owned, pinned use of one immutable published Module Version, with
explicit attached-Source bindings, a supported structured trigger, and a
bounded processing start. An upgrade creates a successor installation.
_Avoid_: Latest Module, inferred Source, cron string

**Space Membership Suggestion**:
An internal, pending relationship inferred from an attached Source observation
after a verified email or phone mapping resolves to an active teammate in the
same organization. It grants no Space visibility or subscription until a Space
Administrator confirms it.
_Avoid_: External participant, invite, automatic member

**Space Membership**:
The single confirmed access relationship between an internal teammate and a
Space, with a Contributor or Subscriber role. During Setup, visibility remains
limited to Space Administrators; at launch, confirmed memberships become the
exact native subscription cohort.
_Avoid_: Connected Account grant, Source participant, channel guest

**Disputed Detail**:
An immutable, field-scoped record that credible Evidence Links conflict about
one existing field in a generated item. It remains visible whether ordinary
uncertainty or materially consequential ambiguity is later resolved.
_Avoid_: Whole-post warning, unsupported content

**Review Request**:
An interrupting, native assistant message created only for a material Disputed
Detail. Its targets direct attention but do not grant or restrict the ability of
confirmed Space members to submit a Review.
_Avoid_: Assignment, approval gate, Review

**Review Request Target**:
An active confirmed Space member notified by a Review Request, selected from
verified Source participant bindings or a deterministic Space Administrator
fallback.
_Avoid_: Reviewer permission, exclusive assignee

**For You**:
A live personal-relevance projection over the latest meaningful state of
generated items, Reviews, and Todos in a teammate's confirmed Contributor and
Subscriber Spaces. It ranks direct assignment, ownership, mentions, Review
requests, personal activity, importance, and membership relationship without
creating another feed record or acknowledgement state.
_Avoid_: Personal inbox, copied update, acknowledgement queue

**Team Pulse**:
A live shared-importance projection over the latest meaningful state of the
same Hover records in a teammate's confirmed Contributor and Subscriber
Spaces. Its rank has no personal activity or read-state inputs, so teammates
with identical Space memberships receive the same result.
_Avoid_: Organization-wide feed, personalized pulse, copied update

**Personal Edition**:
An immutable Morning Daily Brief or End-of-Day Roundup published for one
verified teammate and rendered only through the concise generated updates that
remain authorized in their confirmed Contributor and Subscriber Spaces. Its
suggested prose is guidance, never a Todo unless separately confirmed through
the Suggested Action workflow.
_Avoid_: Personal feed, Source digest, automatic task list

**Morning Daily Brief**:
A warm, prose-first Personal Edition that preserves urgency, unresolved
carryover, guidance, and a permission-safe all-clear treatment.
_Avoid_: Notification queue, priority dashboard

**End-of-Day Roundup**:
A reflective Personal Edition organized around meaningful movement, completed
work, carryover, safely waiting dependencies, and tomorrow's preview.
_Avoid_: Activity log, performance report

**AIMTO Events**:
The first Hover Space, used to prove the product through a real mixed feed of
human activity and source-backed AI updates.
_Avoid_: AIMTO app, AIMTO dashboard

**Pilot Configuration**:
A strict, versioned, private operator input that reconciles one reviewed Hover
pilot through normal records and reports its rollout gates. Provider-side
allowlists are validated and reported here but remain enforced by the incoming
integration that owns them.
_Avoid_: frontend fixture, deployment secret store, provider policy record

**Shadow Mode**:
A controlled pilot state in which Hover can be compared with an incumbent
workflow while Hover-owned Reviews and Todos remain local and have no external
writeback path.
_Avoid_: dual write, Monday synchronization, production expansion

**Suggested Action**:
A Hover-owned, versioned proposal projected from one immutable Suggested Action
publication. Its current reviewed wording and due date can be approved, marked
Not an action, or restored by a confirmed Space member; an opaque upstream
person reference is never treated as a Hover teammate.
_Avoid_: Todo before approval, inferred assignee, editable source proposal

**Action Transition**:
An append-only, request-identified record of one legal Suggested Action state
change. It preserves actor, time, optional dismissal reason, and the approved
snapshot without rewriting the native message, publication, or evidence.
_Avoid_: Status toggle, deletion, client-only state

**Todo**:
The durable accountable-work aggregate created exactly once when a Suggested
Action is approved. Confirmed Space members assign, reassign, complete, and
reopen it through request-identified Todo Events that preserve actor, time, and
before/after state. Space and Home consume the same versioned projection.
_Avoid_: Suggested Action, reminder, copied Home task

**Todo Event**:
An append-only assignment or lifecycle fact for one Todo. A later reassignment
or reopen event corrects earlier work without deleting its audit history.
_Avoid_: Mutable status row, client-only correction, deleted history

**Hover Search**:
A permission-filtered result surface spanning native human posts, generated
updates, and transient Source Records in every launched Space where the
teammate has a confirmed membership. Native knowledge is ranked before clearly
labelled Source evidence, and authorization is checked again after remote
Source search.
_Avoid_: Ask Hover, copied Source index, public search

**Saved**:
A teammate's private live collection of native human and generated messages,
implemented with Zulip starred-message state. Source Records are read-only and
cannot be saved in the pilot.
_Avoid_: Bookmark snapshot, Saved Source, shared collection
