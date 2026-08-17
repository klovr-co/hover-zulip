# ADR 0020: Keep Space Documents Hover-owned while reusing BlockSuite editors

## Status

Accepted

## Context

Hover Spaces need native collaborative rich documents and spatial canvases
alongside Updates, Sources, and Discussion. AFFiNE demonstrates the intended
single-document Document View and Canvas View experience, but its full
application also brings workspace, identity, permissions, storage, and sharing
systems that overlap with Hover's existing authority.

Importing those application services would create two workspace and access
models inside one product. Reimplementing BlockSuite's editor and CRDT behavior
would instead discard the reusable layer designed for independent embedding.
BlockSuite evolves rapidly, so treating its internal AFFiNE integration code as
a stable application API would also increase upgrade risk.

## Decision

- `SpaceDocument` is a Hover-owned object under exactly one Space. It has one
  shared content model and can be attached to BlockSuite's Document View or
  Canvas View without conversion or duplication.
- Hover remains authoritative for Space membership, roles, document metadata
  and lifecycle, Document Files, Source evidence references, search
  projection, checkpoints, and audit history. There is no separate AFFiNE
  workspace, account, permission, or sharing backend.
- Launched-Space Subscribers can read Space Documents. Contributors and Space
  Administrators can create and edit them. Space Administrators can archive,
  restore, and create checkpoints. Setup remains visible only to Space
  Administrators, and there are no per-document sharing overrides.
- BlockSuite is consumed as a public, exactly pinned dependency for its preset
  editors, block schemas, and Yjs-compatible content model. AFFiNE application
  code may be studied as a reference but is not copied as an integration layer.
- A small Hover-authorized Yjs-compatible sync service will use short-lived
  capabilities and revalidate Space access. Persistent browser-only offline
  editing is outside the first release; live presence is ephemeral.
- Collaborative updates are retained with periodic snapshots. Named Document
  Checkpoints are the meaningful audit boundary. The first restore workflow
  creates a new Space Document from a checkpoint rather than rewriting the
  current document's collaborative history.
- Document Files use Hover storage. Custom evidence blocks persist stable Hover
  identifiers and resolve current authorized projections at read time. Hover
  Search indexes a safe text projection after applying Space permissions.
- Space Documents are archived and restored in the first release; permanent
  deletion is not exposed. Discussion remains the Space's native Discussion
  surface until inline document comments are designed separately.

## Consequences

Hover has one access-control and audit boundary, and a Space membership change
can revoke both editor and sync access without coordinating with AFFiNE
services. Users get AFFiNE's core document/canvas behavior while documents
remain native Hover knowledge connected to Sources, Updates, and Discussion.

The team owns the sync service, durable update and snapshot storage, file
adapters, search projection, and custom evidence blocks. Exact dependency
pinning and explicit upgrade work are required because BlockSuite's public APIs
are still evolving. Features implemented only in the AFFiNE application—such
as its workspace library, account system, sharing backend, and application
history UI—are not inherited automatically.
