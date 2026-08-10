# ADR 0001: Mark generated updates in the first Hover demo by sender

## Status

Superseded by [ADR 0002](0002-structured-generated-item-message-metadata.md).

## Context

The first Hover vertical slice must render a source-backed AI update through
Zulip's native message view without introducing the complete Hover domain model.
The fixture creates one development-only bot with the stable delivery email
`hover-ai@hover.test`.

## Decision

For this development fixture only, the web client identifies messages from that
bot as Hover generated updates and adds presentation metadata to the existing
message container. The message remains a normal Zulip message, so replies,
reactions, editing, search, permissions, and real-time delivery remain native.

The email marker is not a production API contract. The next data-model slice
must replace it with server-supplied GeneratedItem metadata and EvidenceLink
records that distinguish update types and resolve every source reference.

## Consequences

- The prototype can validate the native feed transformation without a migration.
- Every message from the demo bot receives the generated-update treatment.
- Production ingestion, Reviews, Suggested Actions, and audit history remain
  blocked on the structured Hover model described above.
