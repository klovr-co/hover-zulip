# Source detachment and Space membership revocation

## Status

Accepted

## Context

Hover projects the same Space through native messages, transient Source history,
search, Saved, awareness feeds, Todos, notifications, and personal editions.
Removing access in only one projection would leave stale or contradictory
authorization. Source detachment has a different purpose: it stops new work but
must preserve the evidence and audit trail already used by the Space.

## Decision

- A detached Space Attachment remains the stable identity for its bounded,
  read-only history. Detachment atomically stops publication polling, invalidates
  an outstanding publication lease, detaches live integration routes, and pauses
  every bound Module installation. Existing generated messages, evidence, and
  audit records remain available to current confirmed Space members and carry
  the attachment's `detached` state.
- Permanent evidence deletion is a distinct, confirmed Organization Admin
  operation. It requires prior detachment, removes evidence and integration
  provenance, disables retained Source browsing, and records an audit event. It
  does not delete native generated messages or their human-authored workflow
  history.
- A Space membership is the canonical authorization relationship. Removing a
  launched-Space member deletes that relationship and, in the same transaction,
  deactivates the corresponding native subscription and contribution-group
  membership. Every Hover read seam checks current membership, so the removal is
  immediately reflected in initial state and direct endpoints.
- Re-adding a launched-Space member reactivates the existing native subscription
  and reconciles the contribution group. Native subscription identity and all
  authored messages, Reviews, transitions, Todo events, and audit records remain
  unchanged.

## Consequences

Detached history stays useful without allowing new Source-derived processing.
Membership changes cannot leave a user with a private-channel back door, and
idempotent native subscription operations avoid duplicate subscriptions on
re-add. Destructive evidence removal is deliberately harder and narrower than
ordinary detachment.
