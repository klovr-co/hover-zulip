# 0005: Capture native integration Source provenance atomically

## Status

Accepted

## Context

Zulip's Slack-compatible and native GitHub integrations already create normal
Messages with mature topic, rendering, search, reply, reaction, and notification
behavior. Hover needs those live messages to identify their configured Source
without replacing the native webhook paths or implying that older messages were
backfilled.

## Decision

- A native Connected Account names one active incoming webhook bot. Remote
  Studio accounts cannot bind a local bot.
- An Integration Route binds one active Space Attachment to that dedicated bot
  and the exact server-derived channel of a launched Space. Configuration
  requires an active Connected Account grant and a confirmed Space Administrator
  membership; organization administrator status alone is insufficient.
- Message sending matches the actual sender bot and recipient channel after
  Message IDs exist, then persists Source Provenance before realtime payloads are
  built. Account revocation, route detachment, attachment deactivation, or bot
  deactivation stops capture.
- Source Provenance snapshots only safe provider/type/label/HTTPS-link metadata.
  Historical snapshots survive later Source edits and route detachment.
- Authorized history, search, initial fetches, and realtime events all receive
  the same optional `hover_source_provenance` projection. Raw webhook events do
  not become Generated Items.

## Consequences

Native integration messages keep all existing Zulip behavior and acquire a
provider-neutral Hover label atomically. A bot can serve only one active Source,
which prevents ambiguous provenance. Messages before association or after
detachment remain unlabeled, while already captured history remains auditable.
