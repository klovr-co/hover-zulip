# ADR 0012: Project durable Todos from append-only events

## Status

Accepted.

## Context

Suggested Action approval creates accountable work, but assignment and
completion continue after approval. The same work must appear in its Space and
in Home without copied state, survive retries and reordered realtime delivery,
and preserve incorrect assignments or completions as auditable history.

## Decision

The approval-created `Todo` remains the canonical aggregate. Confirmed active
Space members append request-identified `TodoEvent` rows to assign, reassign,
complete, or reopen it under a row lock and expected version. Events record the
actor, time, before/after state, before/after assignee, and any native
notification message. Event rows cannot be updated or deleted.

The server returns one complete versioned Todo projection from both the
Suggested Action and the authorized Home list endpoint. Targeted `hover_todo`
events carry the same projection. Clients retain one Todo object per ID and
ignore an older version, so retries and reordered delivery cannot rewind either
surface.

Assignments notify the selected teammate with a native ID mention. Completion
by another confirmed member notifies the assignee. Reassignment and reopening
are new events rather than edits to earlier facts.

## Consequences

Home is a projection of authorized Space work rather than a second task store.
Every material change is attributable and corrections remain visible. The
projection includes stable links to its Space, approval, Generated Item, native
message, and evidence while the original publication remains immutable.
