# ADR 0002: Identify generated updates with structured message metadata

## Status

Accepted.

## Context

The first Hover demo identified generated updates from a development bot email
and derived their Module and source presentation by parsing message topics and
rendered content. Those values are presentation details, not a durable or
authorized product contract.

Hover must preserve native Zulip message delivery, search, unread state,
replies, and reactions while making generated-update provenance explicit.

## Decision

A generated update remains a native Zulip `Message` and is linked one-to-one to
an organization-scoped `GeneratedItem`. Ordered `EvidenceLink` records hold its
source references. The server adds an optional `hover_generated_item` object to
an already-authorized message payload for both historical fetches and real-time
message events.

The web client applies generated-update presentation only when that object is
present. Sender identity, Space name, topic, message content, and source URLs
are not generated-update discriminators.

## Consequences

- Native Zulip interaction and retrieval behavior remains authoritative.
- Initial fetches, search results, and real-time events share one metadata
  projection.
- Ordinary messages cannot acquire generated styling by matching demo content.
- Future Hover workflows can extend `GeneratedItem` and `EvidenceLink` without
  replacing the native message transport.
