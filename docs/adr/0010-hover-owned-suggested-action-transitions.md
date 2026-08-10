# ADR 0010: Keep Suggested Action decisions and Todos in Hover

## Status

Accepted.

## Context

Clawer publishes a versioned Suggested Action proposal with exact evidence and
an opaque proposed-person reference. It cannot know whether Hover members accept
the proposal or which internal teammate should become accountable. Native
messages and publication evidence must remain stable while human decisions
converge across history, search, and realtime clients.

## Decision

Each valid Suggested Action publication atomically materializes one pending
`SuggestedAction` beside its immutable `GeneratedItem` and native `Message`.
Hover promotes current reviewed wording and due date for workflow queries but
keeps the original payload, message, envelope hash, and Evidence Links unchanged.
Opaque `person_*` references remain source suggestions and never resolve to a
Zulip user without an explicit verified contract.

Only active, non-guest, non-bot confirmed Contributors and Subscribers in the
exact launched Space can decide. A decision requires a client UUID and expected
version under a row lock. Legal transitions are pending to approved, pending to
Not an action, and Not an action back to pending. Transition and Todo Event rows
are append-only. Approval creates exactly one active Todo in the same transaction;
the Todo is the aggregate that later assignment and completion workflows extend.

Initial message serialization and targeted realtime events use the same complete
versioned projection. Clients ignore older versions and update the existing
native message rather than inserting a second feed record.

## Consequences

Publication replay and concurrent approval cannot duplicate accountable work.
Dismissal is reversible without deleting audit or evidence history. Review edits
advance the action version and synchronize promoted fields, while responsibility
remains explicitly unassigned until Hover receives a valid internal selection.
Legacy malformed demo rows remain presentation-only instead of being inferred
from Markdown.
