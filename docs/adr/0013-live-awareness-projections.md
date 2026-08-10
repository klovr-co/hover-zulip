# ADR 0013: Project live awareness from canonical Hover records

## Status

Accepted

## Context

For You must focus each teammate on relevant work while Team Pulse must show a
stable shared picture. Both surfaces need to respond immediately to Reviews,
lineage, and Todo changes. Persisting feed copies would create a second writable
state, while reusing unread as a queue would turn ordinary awareness into work
that needs acknowledgement.

## Decision

For You and Team Pulse are query-time projections over canonical generated
items, Review requests, Todos, and native messages. Only records in the
requesting teammate's launched, confirmed Contributor and Subscriber Spaces are
eligible. A lineage contributes only its latest meaningful item; View history
links back to the canonical native chronology.

For You uses a documented lexicographic score: assignment, ownership, direct
mention, explicit Review request, personal Review or Reply activity,
importance, and Contributor membership. Routine items from Subscriber Spaces
are excluded unless an important or direct personal relationship makes them
relevant.

The integer rank encodes that ordering with descending powers of two:
assignment `2^20`, ownership `2^19`, direct mention `2^18`, Review request
`2^17`, personal activity `2^16`, important state `2^15`, and Contributor
membership `2^14`. The small native importance value is the final ranked
signal. Thus no combination of lower-priority signals can overtake a
higher-priority signal.

Team Pulse uses only shared item state: importance, open material Reviews,
active Todos, and material changes. It never uses the requesting teammate's
read state, mentions, activity, assignment, or identity in scoring. Therefore
two active teammates with identical confirmed Space memberships and roles get
the same ordered record IDs and ranks.

Its corresponding weights are urgent `2^20`, high importance `2^19`, open
Review `2^18`, active Todo `2^17`, and material change `2^16`, followed by the
small native importance value.

Both projections carry native message IDs and read state for presentation. They
do not mutate read state or add acknowledgement state. Their Home clients
refresh after native message, Space membership, Review, and Todo events and
fetch the same current-state serializers used by ordinary message views.

## Consequences

- Authorization changes take effect on the next query without deleting history.
- Review, Todo, and lineage state cannot drift between Space and Home surfaces.
- Ranking changes can evolve without data migration, but policy changes require
  explicit test updates because ordering is part of the product contract.
- Team Pulse cannot contain a personalized tie-breaker; stable item identity and
  meaningful time are the final deterministic tie-breaks.
