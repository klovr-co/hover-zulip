# Permission-filtered Hover Search and native Saved

## Status

Accepted

## Context

Teammates need one search across concise Space knowledge and authoritative raw
Source evidence. Native messages and external records have different storage,
search, and authorization boundaries. Saving a copied result would also become
stale as Reviews and workflow status change.

## Decision

- Hover Search starts from launched Spaces where the active, non-guest,
  non-bot teammate has a confirmed Contributor or Subscriber membership.
- Human and generated native messages use Zulip's full-text narrow machinery,
  constrained to the exact current Space stream IDs. Native integration
  evidence does not enter the knowledge tier.
- Attached raw records are queried on demand through the existing versioned
  Source-record browsing adapter, including its immutable history boundary and
  strict response contract. Hover does not persist or index record bodies.
- Knowledge is returned and presented before the secondary **Sources** tier.
  Source results are explicitly read-only and contain no message or save
  action.
- Authorization is evaluated before native and remote search and again after
  all remote requests. A membership revoked while search is in flight removes
  both the Space's native and Source results from the response.
- **Saved** continues to use private native starred-message state. Search save
  controls update that same state, and Saved opens the live native message
  rather than a copied snapshot.

## Consequences

Hover provides unified discovery without acquiring authority over external
records or introducing a second bookmark model. Source availability can be
partial while native results remain useful. Cross-Source ranking is deliberately
limited in the pilot: concise native knowledge is the primary tier and exact
evidence is a clearly separated secondary tier.
