# ADR 0015: Personal editorial editions

## Status

Accepted

## Context

Hover needs a Morning Daily Brief and an End-of-Day Roundup without creating a
second, weakly authorized feed or turning generated guidance into task state.
Clawer publishes strict personal digest envelopes through Studio, while the
concise operational updates they discuss already exist as native messages in
launched Spaces.

Personal identity and Space access can change independently. A client-provided
person reference, an edition rendered directly from Source evidence, or a
snapshot of membership at generation time would each permit an edition to
cross an authorization boundary.

## Decision

- Hover derives each upstream `teammate_ref` only from a verified
  `SourceParticipantBinding` attached to a currently launched Space where the
  requester has a confirmed Contributor or Subscriber `SpaceMembership`. The
  browser cannot provide or choose this reference.
- Studio exposes one bounded personal-edition sync operation. Its opaque cursor
  is stored separately per Connected Account, Hover user, teammate reference,
  and immutable start boundary. Hover accepts only strict digest v1 envelopes
  whose personal edition, teammate reference, and producer key agree.
- Personal editions are immutable durable records separate from
  `GeneratedItem`, `SuggestedAction`, and `Todo`. Ingestion never creates a
  native message, Suggested Action, or Todo.
- Every editorial passage must declare one or more operational publication
  identifiers. At read time, Hover resolves every identifier to a native
  generated update in an active attachment and a launched Space where the
  reader still has confirmed membership. A passage with any missing or
  unauthorized update is omitted.
- The passage's primary action opens the first concise native Space update.
  When exact evidence exists, a secondary View Sources action opens that
  generated update's existing permission-checked evidence surface; the
  personal edition never accepts or links directly to raw Source records.
- Morning sections preserve urgency, unresolved carryover, and guidance. The
  all-clear treatment is generic and appears only when every edition-level
  operational publication remains authorized. End-of-day sections preserve
  meaningful movement, completed work, carryover, safely delegated or waiting
  dependencies, and tomorrow preview.
- The default presentation is a fully scrollable editorial edition. A manual,
  keyboard-operable focus carousel is optional, never advances automatically,
  respects reduced-motion preferences, and always exposes a View all control.
- Upstream failure does not erase an authorized cached edition. The UI labels
  the cached state and offers a retry.

## Consequences

The edition is a personal, permission-filtered view over canonical Space
updates rather than a new operational system of record. Removing the last
qualifying membership or identity binding stops sync and hides the cached
edition; removing access to only one referenced Space removes the affected
passages. Confirmed Todo references remain transport lineage and have no
write-side effect in Hover.

The Clawer transport contract is implemented by Clawer commit
`7ffb3bceffe8070cea31552e30514a6bcbbcb628`. Studio must forward
`personal_edition_sync` at
`POST /api/hover/v1/connected-accounts/{external_id}/personal-editions/sync`
to Clawer's permission-scoped personal-edition page.
