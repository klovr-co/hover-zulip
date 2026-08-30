# 0022: Hover-owned Summary execution

## Status

Accepted

## Context

A Summary combines native message authorization, remote generation, private
preview, interval scheduling, and atomic publication. Letting the generator
select messages would move Hover's permission boundary into a service that
does not own native access. Letting manual and scheduled runs build their own
payloads would also make provenance and replay behavior differ by trigger.

ADR 0021 specified a daily local-time schedule while establishing private
Summary containers and strict withdrawal. Summary scheduling is now based on
elapsed intervals, but those authorization decisions remain unchanged.

## Decision

- Hover owns one execution function for manual and scheduled runs. It freezes
  the authorized input identities and native messages before dispatch.
- The remote pipeline receives only a versioned bounded snapshot with opaque
  input and citation tokens. It cannot query Hover's database or expand the
  evidence boundary.
- Hover persists the exact text sent, validates every returned citation token,
  and is the final publication authority. An unknown or duplicate token fails
  the execution without retaining generated prose.
- Manual success remains private until Publish. Scheduled success and
  scheduled no-change results publish through the same idempotent transaction.
- Summary schedules are contiguous elapsed UTC intervals. Creation anchors the
  first window at the installation creation time; a settings edit creates a
  new anchor at save time. Timezone remains presentation and date-input
  context, not schedule arithmetic.
- Request, result, occurrence, and publication hashes and uniqueness
  constraints make identical replays idempotent and conflicting replays fail
  closed.

## Supersession

This ADR supersedes only ADR 0021's daily scheduling clause. ADR 0021's private
native containers, independent member sets, generation-time provenance, and
strict withdrawal policy remain in force.

## Consequences

Hover can prove which authorized native content bounded every generation even
after messages or Summary settings change. The pipeline remains provider- and
database-neutral, while retries and catch-up reuse stable execution identities.
