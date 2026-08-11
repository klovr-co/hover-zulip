# ADR 0017: Reconcile Studio participant selectors from Hover authorization

Hover is authoritative for personal-edition eligibility. Studio stores only a
materialized account-scoped selector set and replaces it atomically from an
authenticated Hover request. The desired set contains opaque `person_` refs
whose verified binding reaches an approved account through an active Source
attachment in a launched Space where the bound active, non-guest, non-bot user
is a Contributor or Subscriber.

Hover records one durable reconciliation row per Connected Account in the same
transaction as relevant authorization mutations. A periodic command recomputes
the complete set, retries typed transient failures with bounded backoff, and
sends neither raw provider identity nor Space content. Empty sets are meaningful
and revoke all stale participant selectors. Studio always disables
`allSelectors` during replacement.

The worker snapshots the desired set and its account generation while claiming
an expiring lease, then releases the database transaction before the fixed
remote operation. Concurrent authorization mutations increment the generation.
An in-flight result becomes current only when its generation is still current;
otherwise the outbox remains pending for another complete replacement. A crash
after remote success safely retries the idempotent replacement when its lease
expires.

ADR and migration number `0018` are reserved for future H22 telemetry.
