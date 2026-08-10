# ADR 0009: Keep Hover Replies and Reviews native

## Context

Teammates need to discuss and correct a generated Hover update without losing
Zulip topics, authorship, search, read state, or realtime delivery. A correction
must preserve both the original publication payload and its exact evidence.

## Decision

A Hover response is a native human-authored channel `Message` in the generated
root's channel and topic, plus a one-to-one typed `Response` record. The standard
message-send request accepts a generated-item ID and either `reply` or `review`.
Only a confirmed, active Space member may use that extension.

`GeneratedItem.payload` remains the immutable publication-time interpretation.
`GeneratedItem.reviewed_payload` is the current reviewed projection. The first
review flow accepts one existing top-level field and a JSON value. This makes a
patch deterministic: selecting Review is its approval, so there is no second
confirmation step. Missing, invalid, nested, or unknown fields create a visible
Review marked as needing clarification and do not mutate the projection.

Every applied patch creates one append-only `Revision` with its old and new
values, actor, timestamp, native Review message, and the Review text as its
reason. Response message metadata contains the updated root projection, so the
same message event that delivers the response also converges the root in live
clients. Initial message fetches use the same serializer.

## Consequences

- Replies and Reviews inherit native permissions and collaboration behavior.
- Subscribers may use the validated Hover response extension even when the
  Space's channel normally reserves ordinary posting for Contributors.
- Evidence and original generated wording are never rewritten by a Review.
- Nested or multi-field editing can be added later behind a versioned patch
  contract without changing the audit model.
