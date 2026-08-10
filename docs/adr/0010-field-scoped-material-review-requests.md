# ADR 0010: Route material ambiguity through native Review requests

## Status

Accepted

## Context

A publication can be useful while credible evidence conflicts about one field.
Treating the whole update as unreliable hides supported information. Treating
every uncertainty as an interruption creates notification fatigue. Upstream
participant references also cannot safely be matched to teammates by names or
raw provider identifiers.

## Decision

Hover accepts additive publication schema 1.1 dispute metadata for Feed Update,
Progress Update, and Decision while preserving schema 1.0 canonical hashes.
Each ambiguity becomes an immutable Disputed Detail with its exact ordered
Evidence Links. Ordinary uncertainty remains a field-scoped display state.

A material Disputed Detail atomically creates one assistant-authored native
message in the generated root's Space and topic. Native silent mentions notify
targets resolved through verified, Source-scoped participant bindings. When no
eligible involved teammate remains in the Space, the oldest eligible Space
Administrator is the deterministic fallback. Targeting controls attention only;
H14's active confirmed Contributor/Subscriber check remains the sole Review
authorization rule.

An explicit H14 Revision of the exact disputed top-level field appends resolution
links to both the Disputed Detail and Review Request. It never rewrites the
publication payload, generated message, evidence, request message, or targets.
Initial message fetches and realtime response events share the same structured
metadata. Exact conflicting evidence is resolved from a server-owned subset URL;
the browser never supplies evidence references.

## Consequences

- Publication replay stays immutable and one request message is the idempotency
  and notification boundary.
- Verified identity observations may persist only opaque Source participant
  bindings; raw email, phone, and provider identity data remain outside Hover.
- Material publication acceptance fails atomically if no eligible target exists.
- Later multi-field Reviews will require an explicit evolution of the one-field
  resolution relation.
