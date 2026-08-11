# 0003: Provider-neutral Source attachments

## Status

Accepted

## Context

Hover needs to attach external conversations to Spaces without making its
domain model, navigation, or browser contract depend on WhatsApp identifiers.
Discovery is jointly constrained by a teammate's local grant and Studio's
organization-level ceiling. Choosing a Source also establishes the earliest
history that later ingestion may request.

Attachment must not consume a Studio publication page. Publication ingestion
and cursor ownership belong to the ingestion boundary, and discarding a first
page during setup could permanently lose data.

## Decision

- A `Source` belongs to a Connected Account and is uniquely identified there
  by an opaque adapter reference. Provider and source type are metadata, not
  identity exposed to the browser.
- A `SpaceAttachment` uniquely associates a Source with a Space and persists
  the chosen window, timezone, and exact UTC start. Replaying the same semantic
  window is idempotent; changing it is an explicit conflict.
- The WhatsApp pilot uses a typed `whatsapp_group` grant selector. Hover fully
  scans bounded Studio discovery, intersects it with the actor's explicit
  grant, and only then applies safe local pagination.
- Source discovery, preview, and attachment require an explicit Space
  Administrator assignment. Studio remains the outer authorization ceiling.
- Attachment is a local durable operation. It stores the future Studio
  `start_at` boundary but does not call the publication sync endpoint.
- Initial state and `hover_space` update events project only safe Source and
  attachment metadata; credentials, raw provider identifiers, phone numbers,
  and message content are excluded.

## Consequences

The UI and event contract can support future providers without adding parallel
Space models. Ingestion can begin from an exact persisted boundary and own the
first publication cursor. Restricted discovery may fail retryably when its
safe scan bound is exhausted rather than returning a partial, density-leaking
result.
