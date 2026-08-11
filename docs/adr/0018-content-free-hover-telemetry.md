# Content-free Hover telemetry

## Status

Accepted

## Context

Hover needs enough operational and product telemetry to run a controlled pilot
and diagnose replay, integration, evidence, workflow, notification, and edition
failures. The same code paths process private Source records, credentials,
provider identifiers, evidence payloads, message content, and internal service
addresses. Ordinary structured logging is too permissive for this boundary.

## Decision

- All Hover telemetry passes through `hover.telemetry`. Events and outcomes are
  fixed enums. Each event has an explicit outcome allowlist and dimension
  allowlist, so even a fixed but semantically unrelated outcome is rejected.
- Dimension values are limited to non-negative integers, booleans, and fixed
  bucket enums. Arbitrary strings, exception text, mappings, lists, payloads,
  references, URLs, credentials, phone numbers, and network addresses are
  rejected before logging.
- Counts, durations, and sync lag are bucketed at the boundary. Stable local
  database identifiers may be logged only where explicitly allowlisted for
  operational correlation.
- Product decisions are represented by fixed outcomes, never by user-authored
  wording or reasons. Failure telemetry records retryability and a fixed failure
  class, never upstream response bodies or exception messages.
- Telemetry is emitted after successful workflow commits where practical.
  Attempt failures are emitted after their durable failure state is recorded.

## Consequences

Pilot operators can distinguish lag, contract and duplicate rejection,
recoverable evidence failures, Reviews, Suggested Action decisions, Todo
completion, notification volume, and edition degradation without receiving
private Source data. Adding a new dimension or categorical value requires a
reviewed code change rather than an ad-hoc logging call.
