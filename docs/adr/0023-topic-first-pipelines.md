# 0023: Topic-first Pipeline identity and execution

## Status

Accepted

## Context

The first Hover Pipeline implementation attached each Pipeline one-to-one to an
inbound Connector. That made a transport configuration simultaneously the
input identity, permission boundary, lifecycle owner, and health signal. Hover
Topics can also contain human messages, can aggregate multiple Data Sources,
and can legitimately feed multiple Pipelines, so those concerns cannot share a
Connector identity.

## Decision

- A Pipeline input is the composite identity of one launched Space stream ID
  and one trimmed Topic name compared case-insensitively. A Pipeline output uses
  the same identity shape and may equal the input.
- Topic-wide rename and move operations update matching Pipeline input
  identities atomically. Topic deletion, archival, or access loss preserves the
  Pipeline but pauses it as `topic_unavailable` until an authorized user repairs
  the selection.
- Each run freezes a closed message-ID interval and advances the Pipeline cursor
  only after that run is durably recorded. Pipeline-authored messages have an
  explicit provenance record and are excluded from all later input windows.
- A caller-supplied run key identifies retries. Publication is recorded on the
  run and guarded by uniqueness, so replay returns the existing result instead
  of sending a duplicate message.
- Data Source delivery health is subordinate metadata for the input Topic.
  Pipeline availability derives from Topic access, and run health derives from
  execution and publication outcomes.
- Connector changes, disablement, or deletion only affect future content
  arriving in the Topic. They never rebind, pause, hide, or delete a Pipeline.

## Migration

Persistence expands with nullable Topic fields, deterministically backfills
valid Connector destinations and topics, marks invalid legacy rows as drafts
with unavailable input, cuts all reads and writes over, and then removes the
Pipeline-to-Connector relation. Counts are asserted during backfill.

## Consequences

Ordinary Topics and source-backed Topics share one product flow, several
Pipelines may read the same Topic, and same-Topic output is safe. Data Sources
remain independently managed syncers rather than an alternate Pipeline model.
