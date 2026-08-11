# ADR 0019: Keep pilot provenance allowlists at the integration boundary

## Status

Accepted

## Context

Controlled Hover pilots use normal `Source` and `Integration Route` records for
native webhook provenance. GitHub repository/event filters and Apify
actor/event filters are enforced by the corresponding incoming integration,
before a native message reaches Hover. `IntegrationRouteAssociation` records
the server-owned bot, launched Space channel, and Source attachment, but has no
field that can enforce provider-specific webhook delivery policy.

Copying those filters into an unenforced database field would create a false
security boundary. Embedding them in frontend branches would expose deployment
configuration and make the reusable product pilot-specific.

## Decision

- The versioned private pilot config must declare explicit allowed actors,
  repositories where applicable, and event types for every native provenance
  route. Empty allowlists, unreviewed routes, duplicate entries, missing native
  Sources, and bot/account mismatches are invalid.
- The rollout command validates those controls and reports sanitized counts. It
  persists only the existing normal `Source` and `IntegrationRouteAssociation`
  records; it does not claim to enforce provider delivery policy locally.
- Before launch, an operator must verify the same allowlists in the GitHub or
  Apify integration configuration and mark the external configuration reviewed
  in the private config. Opaque Source references, actor identifiers, and
  credentials remain private and are never copied into rollout documentation.
- Route replay is idempotent. A different bot or attachment remains an explicit
  configuration conflict rather than an implicit update.

## Consequences

The actual enforcement point stays honest and reviewable. Hover retains safe,
provider-neutral provenance records, while the operational report proves that
the external allowlist was supplied and reviewed without disclosing its
contents. Supporting a future locally enforced provider policy requires a
separate domain decision and migration.
