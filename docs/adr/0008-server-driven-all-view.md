# Server-driven All view over native messages

## Status

Accepted

## Context

A launched Hover Space contains human posts, imported Source records, and
structured Module publications. The approved All view should feel like one calm
editorial feed without creating a second message store or deriving Module
identity from AIMTO topic names. Linked publications also need a latest-state
projection while the chronological Space record remains intact.

## Decision

The native Zulip `Message` remains the only feed record. Authorized message
responses project contract presentation, producing Module/version, exact Source
IDs, audit timestamps, and same-Space lineage from `GeneratedItem` and
`EvidenceLink`. The browser uses those fields to:

- show human messages plus the latest meaningful state from every enabled
  Module in All;
- exclude raw imported Source records from All by default;
- filter the current native feed by server-record Module and Source identities;
- reveal earlier linked posts through View history; and
- keep producer, evidence, audit, and timing detail behind explicit controls.

Installed Module names, icons, destinations, availability, and publication
counts remain part of the Space projection. Source and Module filters therefore
do not depend on built-in names, topic inference, or copied feed objects.

Lineage lookup is constrained to the current organization and the same Space as
an already-authorized message. It exposes native message links, not payloads
from another Space.

## Consequences

Space topic views continue to show chronological posts, including earlier
states. All is a reversible presentation projection: opening history navigates
back to the original message. Raw Source browsing remains the separate,
read-only Source view. Future feed ranking can use the same server metadata
without changing message identity.
