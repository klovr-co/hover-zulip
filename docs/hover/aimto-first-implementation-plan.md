# Hover: AIMTO-First Implementation Plan

## Outcome

Deliver the first controlled Hover pilot as one **AIMTO Events** Space. The
pilot uses real WhatsApp Groups ingested by Clawer, Instagram scraper output
delivered by Apify through Zulip's Slack-compatible incoming webhook, and
GitHub events delivered through Zulip's native integration. It proves the
complete loop:

```text
Clawer evidence
  -> source-backed Hover post
  -> teammate Reply or Review
  -> Suggested Action approval
  -> accountable Todo
  -> For You / Team Pulse / Daily Brief / End-of-Day Roundup
```

The first pilot does not require Email, the visual AI Module Builder, Matrix,
multiple Spaces, Monday retirement, or historical Apify/GitHub backfill. The
existing Zulip webhook paths are sufficient for live Apify and GitHub events
from connection onward.

## Confirmed codebase facts

### Hover/Zulip

- The branch is clean and currently matches `origin/main`; no Hover domain
  models or application routes exist yet.
- The server is Django with PostgreSQL. The browser application uses
  TypeScript, Handlebars, and Webpack rather than React.
- Zulip already provides high-leverage primitives that Hover should retain:
  - `Realm`: organization and organization-level administration.
  - `UserProfile`: teammate identity, authentication, and existing organization
    roles.
  - `Stream`: the private channel backing a Space's message audience.
  - `Subscription` and `UserMessage`: membership visibility, message read state,
    mention flags, and notification preferences.
  - `Message`: chronological posts, Markdown, search, editing history, and the
    real-time event system.
  - `ChannelFolder`: the organization-defined primary Category for a Space.
  - `UserGroup`: organization capabilities and per-Space administration.
- Zulip topics are useful transport metadata for Space tabs, but they do not
  model replies beneath one generated post. Hover needs an explicit root-post
  relationship for Reply and Review.
- Zulip already has a Slack-compatible incoming webhook that can receive Apify
  output written for Slack's incoming-webhook format.
- Zulip already has a native GitHub integration for repository events.

### Clawer

- Clawer owns WhatsApp ingestion in SQLite and runs WuzAPI reconciliation,
  tracked-group journals, BOD/EOD work, and other durable flows.
- Current useful interfaces include tracked/discoverable WhatsApp Groups,
  group members, group journals, journal news/Todos, semantic search, and
  source-message anchor resolution.
- Group journals already retain source WhatsApp message IDs and can provide
  citation-friendly `clawer://...` references.
- Clawer does not currently expose a paginated raw WhatsApp Group message view
  or a normalized, cursor-based Hover publication stream.
- Existing output shapes are heterogeneous. In particular, group Todo prompt
  and parser shapes must be normalized and validated before Hover treats them
  as a stable contract.
- Current BOD/EOD processing still reads or writes Monday-owned operational
  shapes. Monday can remain a compatibility source during the pilot, but the
  final Hover runtime cannot depend on Monday as a second writable authority.
- Every Hover-to-Clawer call must route through **clawer-studio**. Hover must
  never connect directly to a user's Clawer VM, and new Clawer integrations
  must also respect Studio's ingress/egress role.

## Architecture decision

### Keep native message transport; add a Hover domain module

Create a dedicated Django application named `hover` rather than scattering
Hover tables through core Zulip models. It owns Hover's domain records, action
functions, queries, routes, event schemas, and tests. The web application lives
under `web/src/hover/` with Handlebars templates under `web/templates/hover/`.

Use one private Zulip `Stream` as the transport audience for each launched
Space. Hover's action module creates and administers the corresponding Stream;
generic channel-join paths remain unavailable for Hover Spaces.

An AI-generated update is a native Zulip `Message` sent by the single **Hover**
bot identity plus a one-to-one structured Hover record. The native Message
supplies ordering, real-time delivery, search, and read/unread state. The Hover
record supplies output contract, provenance, current reviewed state, lineage,
Module version, and workflow state.

The original generated Message is not rewritten when a teammate submits a
Review. Hover renders the current reviewed state and visible revision history
from its structured records while preserving the original AI wording.

### Clawer sync is a deep module

Put one server-side seam between Hover and Clawer:

```text
Hover actions and queries
        |
        v
ClawerSync interface
        |
        v
StudioClawerAdapter -> clawer-studio -> Clawer VM
```

The interface should expose three operations:

1. `discover_sources(account, query)` returns WhatsApp Groups the connected
   account may select, without exposing VM credentials.
2. `sync(selection, cursor)` returns a bounded idempotent batch of raw record
   metadata, normalized publications, member observations, and the next cursor.
3. `resolve_evidence(refs)` returns the authorized immutable source material
   required for View Sources and audit comparison.

This small interface hides Studio routing, Clawer authentication, SQLite and
artifact files, pagination, current Temporal/runtime details, and temporary
Monday compatibility. Tests use an in-memory adapter against the same
interface. It is specifically the seam for Clawer-backed Sources, not a generic
connector framework.

Apify and GitHub enter AIMTO through existing Zulip integrations rather than
through `ClawerSync`: Apify sends scraper results to the Slack-compatible
incoming webhook, and GitHub sends repository events to the native GitHub
integration. A small Hover provenance bridge associates each integration bot
and destination route with its `Source` and `SpaceSource`, allowing the native
`Message` to act as live source evidence. No new provider adapter is required
for this live path.

## Proposed data model

All tables are organization-scoped and use database constraints for uniqueness
and lifecycle invariants.

| Hover record                   | Purpose                                                                                                                                                | Reused Zulip record                                                  |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `OrganizationSettings`         | Hover feature flag plus `Can create Spaces` and `AI Builder` capability groups                                                                         | `Realm`, `UserGroup`                                                 |
| `Space`                        | Setup/Launched lifecycle, launch time, creator, presentation settings                                                                                  | one-to-one `Stream`; Category uses `Stream.folder` / `ChannelFolder` |
| `SpaceMembership`              | Contributor or Subscriber relationship                                                                                                                 | one-to-one active `Subscription`                                     |
| Space admins                   | Multiple admins without treating admin as a third membership relationship                                                                              | `Stream.can_administer_channel_group`                                |
| `ExternalIdentity`             | Verified phone/email/provider identity used for smart teammate matching                                                                                | `UserProfile`                                                        |
| `ConnectedAccount`             | Provider connection reference and health; either a Studio-issued Clawer account or an existing Zulip integration bot/endpoint, with no provider secret | `Realm`, creator `UserProfile`                                       |
| `ConnectedAccountGrant`        | Organization-admin assignment and optional selector restrictions                                                                                       | grantee `UserProfile`                                                |
| `Source`                       | Stable provider source reference and typed selector, such as a WhatsApp Group                                                                          | `ConnectedAccount`                                                   |
| `SpaceSource`                  | Explicit Source attachment, history window, and active/detached lifecycle                                                                              | `Space`, `Source`                                                    |
| `ModuleVersion`                | Immutable version and one of the supported output contracts for prebuilt Modules                                                                       | none                                                                 |
| `ModuleInstallation`           | Enabled version, trigger policy, Source bindings, and publication tab                                                                                  | `Space` or personal `UserProfile`                                    |
| `ModuleRun`                    | Idempotency key, accepted configuration snapshot, status, and external run reference                                                                   | none                                                                 |
| `GeneratedItem`                | Original AI payload, current reviewed payload, importance, lineage key, uncertainty state, and producing version                                       | one-to-one nullable `Message`                                        |
| `EvidenceLink`                 | Ordered source reference, generation-time display snapshot/hash, and evidence role                                                                     | `GeneratedItem`, `Source`                                            |
| `Response`                     | Reply or Review beneath one generated root post                                                                                                        | one-to-one reply `Message`                                           |
| `Revision`                     | Before/after patch, actor, reason, time, and source Review                                                                                             | `GeneratedItem`, `UserProfile`                                       |
| `ReviewRequest`                | Needs-review state and targeted teammates                                                                                                              | `GeneratedItem`, `UserProfile`                                       |
| `SuggestedAction`              | Proposed action and pending/approved/not-an-action state                                                                                               | `GeneratedItem`                                                      |
| `Todo` and `TodoEvent`         | Current accountable work plus append-only assignment/completion history                                                                                | `SuggestedAction`, `UserProfile`                                     |
| `Decision` and `DecisionEvent` | Current active/superseded/reversed decision state plus append-only lifecycle history                                                                   | `GeneratedItem`, optional superseding `Decision`                     |
| `PersonalEdition`              | Morning Daily Brief or End-of-Day Roundup for one teammate                                                                                             | `UserProfile`, optional `GeneratedItem` links                        |
| `SyncCursor`                   | Last accepted cursor per Connected Account/Source adapter                                                                                              | `ConnectedAccount` or `Source`                                       |

Keep the six normalized output contracts versioned:

1. Feed Update
2. Digest
3. Suggested Action
4. Progress Update
5. Decision
6. Analysis

Store contract-specific payloads in validated versioned JSON, but promote
frequently queried fields—importance, assignee, due date, current status,
lineage key, and publication time—to indexed columns. Suggested Action and Todo
state must not live only in JSON.

## Clawer and Studio work required

### Normalized publication contract

Add a durable Clawer publication/outbox record written in the same successful
business step that persists a derived artifact. A publication contains:

- stable publication ID and idempotency key;
- output-contract name and schema version;
- producing Module/prompt version and run reference;
- source references and covered time window;
- validated payload;
- ordered evidence references;
- importance and optional lineage key;
- occurred, generated, and published timestamps.

The sync interface is cursor-based and safe to replay. Hover inserts by
idempotency key, so a lost response or repeated poll cannot duplicate a post.
Valid publications are independently consumable; an invalid output is withheld
and retried inside Clawer without exposing failure machinery to teammates.

### WhatsApp evidence contract

Add a paginated source-record reader for selected WhatsApp Groups. It must
support stable cursors, bounded history windows, attachments/media metadata,
sender identity references, replies where available, and exact evidence
resolution by opaque reference. Do not make Hover parse Clawer's journal files
or query its SQLite schema.

Retain the existing group discovery and member observations, but expose them
through Studio with stable provider/source identifiers. Phone numbers are used
server-side for verified identity matching and are not emitted unnecessarily to
ordinary browser clients.

### Temporary BOD/EOD compatibility

For the AIMTO pilot, Clawer may normalize the existing BOD/EOD artifacts into
Hover's Digest contract while Monday continues in parallel. Before Monday is
retired, persist the canonical group-status input and generated digest artifact
inside Clawer independently of the Monday board. Hover Reviews and Todos remain
authoritative only in Hover and must not be synchronized bidirectionally with
Monday.

### Studio changes

Studio authenticates Hover's server, resolves the intended Clawer instance,
forwards the source discovery/sync/evidence calls, applies rate limits, and
scrubs logs. WhatsApp `ConnectedAccount` records store only Studio-issued
references and health metadata. Apify and GitHub use existing Zulip integration
bot/webhook configuration. WuzAPI, Clawer VM, Apify, and GitHub credentials
never enter browser payloads or Hover logs.

## Delivery phases

### Phase 0 — Contract and integration spike

Deliverables:

- Add the `hover` Django app behind an organization feature flag.
- Prove one new Hover event can participate in Zulip's initial-state plus
  real-time event system.
- Define shared JSON schemas and golden fixtures for all six output contracts,
  evidence references, sync batches, and cursor replay.
- Implement an in-memory `ClawerSync` adapter and a Studio adapter skeleton.
- Replay one real, sanitized AIMTO group-journal specimen through the contract.

Exit criteria:

- The same contract fixtures validate in Hover and Clawer tests.
- Replaying the same sync batch twice creates one record.
- No raw message content, phone number, credential, or VM address appears in
  application logs.

### Phase 1 — AIMTO Space Setup and launch

Deliverables:

- Organization capabilities: Organization Admin, Can create Spaces, and the
  orthogonal AI Builder role.
- Custom Categories using ChannelFolder.
- Setup lifecycle visible only to creator and added Space Admins.
- WhatsApp Connected Account assignment and Source discovery through Studio.
- AIMTO WhatsApp Group selection with today/30-day/custom history choice.
- AIMTO Apify Slack-compatible webhook and native GitHub integration are
  configured as live Sources and associated with the Space. Pilot setup may use
  Zulip's existing integration configuration instead of rebuilding it in the
  Hover Setup wizard.
- Teammate suggestions from observed phone mappings; creator confirms each
  teammate and Contributor/Subscriber relationship.
- Multiple Space Admins and atomic Launch Space.
- AIMTO launch Modules: Conversation Digest, Progress Tracker, Todo, Decision
  Capture, Marketing Digest, and Topic Analysis for the Space, plus personal
  Morning Daily Brief and End-of-Day Roundup for the pilot cohort. Signal
  Monitor is available but off by default; Weekly Roundup remains deferred.

Exit criteria:

- No suggested teammate receives access before confirmation and launch.
- A Space Admin cannot select a Connected Account or group outside their grant.
- Launch creates active Stream subscriptions exactly once and does not notify
  members merely because the Space launched.
- Removing a member immediately removes Space, Source, search, Saved, and
  notification access without deleting their authored or audited history.

### Phase 2 — AIMTO live Sources and WhatsApp history

Deliverables:

- AIMTO WhatsApp source tab with paginated chronological records and media
  metadata.
- New Apify Instagram scraper messages and native GitHub event messages enter
  AIMTO through their existing Zulip webhook paths.
- A provenance bridge maps each integration bot and route to the corresponding
  `Source`, so source filters and AI Modules can distinguish WhatsApp,
  Instagram, and GitHub evidence.
- Search/filter within attached Sources.
- Raw WhatsApp, Instagram, and GitHub views are read-only; human posts are
  created in All/Whiteboard and Replies or Reviews attach to Hover updates.
- Exact source-message View Sources experience through evidence resolution.
- Clear unavailable/retrying states when Studio or Clawer is offline.
- Incremental sync worker with per-Source cursor and idempotent retry.
- Source detachment stops future ingestion and Module processing while
  retaining existing history under a Detached label; permanent evidence
  deletion is a separate Organization Admin action.

Exit criteria:

- A teammate cannot retrieve evidence for a Space they cannot access.
- Historical-window boundaries are enforced.
- Interrupted sync resumes without a gap or duplicate.
- Hover does not become authoritative for the raw WhatsApp record.
- No Source-view composer can send an outbound message to an external system.
- A new Apify or GitHub event is visible in AIMTO with its Source type and
  external source link; no historical backfill is implied.

### Phase 3 — Generated Space posts

Deliverables:

- One Hover bot identity for every AI-generated post.
- AIMTO `All` shows human-authored posts and AI-generated updates by default;
  raw WhatsApp, Instagram, and GitHub records appear only when their Source
  filters are selected.
- Conversation Digest, Feed Update, Progress Tracker, Decision, and Suggested
  Action publications normalized from Clawer.
- Optional Decision Capture Module output appears in All and a Decisions filter,
  with active, superseded, and reversed lifecycle history.
- One or several Modules may publish chronological Messages into the same
  configurable Space tab without visible run grouping.
- Generated item details show Sources, producing Module/version, and audit
  metadata only on demand.
- Urgent blocker, decision, and newly assigned action outputs publish as soon
  as they validate; routine outputs use a 15-minute accumulation window.
- Sentiment-derived updates are produced only when a Sentiment Detection Module
  is enabled; Hover performs no implicit sentiment classification.
- Material developments create new posts; related posts carry a lineage key.
- Invalid publication payloads never create placeholder posts.

Exit criteria:

- A real AIMTO development from an attached Source appears once as a concise
  Hover post with resolvable source evidence.
- A later resolution creates a new post and preserves the earlier one.
- Quiet posts do not send immediate notifications.

### Phase 4 — Reply, Review, Suggested Action, and Todo

Deliverables:

- Reply/Review selector in the post response composer.
- Reply creates human-authored context without changing current derived state.
- Review creates an audited revision; ambiguous review text asks for
  clarification and makes no silent mutation.
- Needs review marks disputed fields, links conflicting evidence, and targets
  involved teammates with Space Admin fallback.
- Suggested Action approve, Not an action, restore, assign/reassign, and active
  Todo completion flows.
- Notification occurs only for direct assignment, mention, or explicit Review
  request; ordinary updates remain read/unread content.

Exit criteria:

- Contributor and Subscriber can both Review, approve, reject, and complete.
- Every state transition records actor and timestamp and is reversible through
  another event rather than deletion.
- The original generated Message and immutable source evidence remain intact.

### Phase 5 — Home awareness surfaces

Deliverables:

- For You deterministic ranking based on assignment, mention, Review request,
  Contributor/Subscriber relationship, and personal activity.
- Team Pulse deterministic importance projection across the same explicit
  Space memberships.
- Latest-state projection with View history for linked developments.
- Unified search across the teammate's explicit Space memberships, ranking
  human and AI updates ahead of clearly labelled raw Source results while
  combining Zulip Message search with permission-filtered Clawer results.
- Private Saved collection for human and AI posts using Zulip's existing
  per-user starred-message state; raw external evidence is not saveable in the
  first pilot.
- Morning BOD Daily Brief in the encouraging personal-assistant voice.
- Prose-first focus slides with a warm headline, short situational narrative,
  one suggested next step, and a link to the relevant Space update; no severity
  badge, raw evidence, or dashboard metadata.
- Personal End-of-Day Roundup covering meaningful movement, completed work,
  carryover, delegated dependencies, and a short preview of tomorrow without
  duplicating each Space's Conversation Digest.
- Aggregated confirmed Todos.
- User-controlled Daily Brief carousel prototype plus View all; keep the
  scrollable editorial version for pilot comparison.

Exit criteria:

- Two teammates with the same Space memberships see the same Team Pulse, while
  For You differs through personal relevance.
- Ordinary feed content never becomes an acknowledgement queue.
- Brief passages link to deeper context without exposing a wall of evidence
  cards.
- A passage opens its relevant Hover Space update first; View Sources from that
  update resolves the underlying evidence as a second step.
- Carousel is keyboard/touch/screen-reader operable and never auto-advances.

### Phase 6 — AIMTO controlled pilot

Start with AIMTO only and a small real teammate cohort.

1. **Shadow:** compare Hover publications and briefs with the current
   Clawer/Monday experience without changing operational behavior.
2. **Collaborative:** enable Review, Suggested Action, and Todo use in Hover;
   Monday remains an unchanged fallback, not a second editor of Hover state.
3. **Evaluate:** accuracy, source trust, review rate, missed important events,
   notification noise, Daily Brief usefulness, and repeat voluntary use.
4. **Expand:** add 3VEN, firm.ai, BWAI, or Aldrent only after AIMTO meets the
   acceptance gates.

Pilot acceptance gates:

- No unauthorized Space or source access.
- No duplicate generated posts under replay/retry.
- Every factual claim and Suggested Action can reach its evidence.
- Reviews and Todo history remain complete across edits and retries.
- Users can identify the day's first useful action faster than in the existing
  workflow.
- The cohort chooses to return to Hover without being prompted.

### Phase 7 — Historical enrichment and Builder

After the AIMTO pilot:

- **Apify/Instagram enrichment:** add historical retrieval or durable media
  capture if live webhook messages and linked media are insufficient. Resolve
  retention, privacy, copyright, and account-policy requirements before storing
  ephemeral content.
- **GitHub enrichment:** add an authenticated historical repository reader only
  if AIMTO needs a full repository brain-dump view beyond native live events.
- **Visual Module Builder:** develop separately or as MVP 2 against the same
  versioned ModuleDefinition and output contracts. It does not block AIMTO.

## Verification strategy

- **Action-module tests:** permission, lifecycle, audit, and state transitions
  are tested through Hover action interfaces, not direct table mutation.
- **Contract tests:** the same fixtures run in Hover and Clawer for every schema
  version and malformed-output case.
- **Adapter tests:** in-memory and Studio adapters run the same behavioral suite.
- **Event tests:** every state-changing action verifies both the database result
  and the Zulip initial-state/real-time event application path.
- **Frontend tests:** Space Setup, source view, post renderer, Reply/Review,
  Todo controls, feed projections, and brief accessibility.
- **Replay tests:** repeated, reordered, and interrupted sync batches; an AIMTO
  sanitized history fixture; later-resolution lineage; partial publication
  success.
- **Security tests:** membership changes, Connected Account grants, evidence
  authorization, source-window enforcement, search-result filtering, and
  secret/log scrubbing.
- **Operational telemetry:** sync lag, publication validation failure, duplicate
  rejection, evidence-resolution failure, Review rate, Suggested Action
  approval/dismissal, and feed/brief return usage. Never attach raw content or
  phone numbers to telemetry.

## Estimated turnaround

The estimate includes live Apify/Instagram and GitHub delivery through existing
Zulip integrations. It excludes the visual Builder, historical Apify/GitHub
backfill and enrichment, Matrix, and Monday retirement.

| Milestone                                          | One experienced full-stack engineer | Two engineers with Hover/Clawer split |
| -------------------------------------------------- | ----------------------------------: | ------------------------------------: |
| Phase 0 contract spike                             |                           1–2 weeks |                                1 week |
| First usable AIMTO read-only slice through Phase 3 |                     5–7 weeks total |                       3–5 weeks total |
| Collaborative AIMTO pilot through Phase 6          |                   12–17 weeks total |                      8–11 weeks total |

These are planning ranges, not commitments. Re-estimate after Phase 0 because
the Studio work, raw WhatsApp pagination, current BOD/EOD Monday dependency,
and Zulip custom-event integration are the highest-variance items.

## Explicit non-goals for the first AIMTO launch

- Multiple organizations.
- External guest accounts; AIMTO membership is limited to authenticated KSK
  organization teammates.
- Automatic Space creation or automatic teammate access.
- A standalone People & Teams discovery page; membership lives in each Space
  and the organization directory remains in Settings.
- A global browsable Sources directory; raw records are viewed within their
  Space, while Connected Accounts are administered in organization Settings.
- Email Sources.
- Historical Apify/Instagram or GitHub backfill.
- Generated Ask Hover answers; the first pilot provides searchable results and
  source provenance only.
- A fixed Customer Signals surface; organizations may instead enable and name a
  Signal Monitor Module per Space.
- Weekly Roundup; it remains an optional cross-Space AI Module after the daily
  awareness loop is proven.
- Visual Module Builder.
- Matrix migration or WhatsApp deprecation.
- Bidirectional Monday synchronization.
- Replacing Clawer's ingestion store or durable execution engine.
- Exposing Module runs, retries, validation failures, or separate bot personas
  in the ordinary teammate interface.

## Remaining non-blocking decisions

- Which exact AIMTO WhatsApp Groups and history windows are selected during
  Setup.
- Which Apify scraper output route and GitHub repositories/events are connected
  to AIMTO.
- The verified Hover user-to-phone mappings for the pilot cohort.
- The initial AIMTO Space Category label.
- Module-specific importance and material-change thresholds for Feed Updates.
- Whether the carousel or scrollable Daily Brief performs better in pilot use.
- The runtime choice being evaluated separately does not change the
  Hover-to-Clawer sync interface in this plan.
