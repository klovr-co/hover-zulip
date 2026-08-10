# 0005: Transient Source record browsing

## Status

Accepted

## Context

Launched Space members need to inspect the original records behind an attached
Source without copying private provider data into Hover or converting it into
native Zulip messages. Provider cursors and identifiers are sensitive, and a
detached Source may need to preserve already-approved history while no longer
acting as an active connection.

## Decision

- Hover fetches Source records on demand through the Clawer/Studio adapter and
  does not persist record bodies, media, sender identifiers, or provider
  cursors.
- Browsing requires a launched Space, a confirmed active membership, and an
  active or retained attachment. Guests, bots, pending attachments, and
  cross-realm relationships receive the same not-found response.
- Every fetch is authorized both before and after the upstream request so a
  concurrent membership or attachment change cannot disclose the response.
- The adapter validates a strict versioned contract and enforces the immutable
  attachment Source and history boundary. Hover returns only safe display
  fields, opaque record IDs, and metadata; it strips provider identifiers.
- Hover wraps each upstream cursor in a short-lived signed token bound to the
  requesting user, Space, attachment, history boundary, and normalized search
  query. Cursors therefore cannot be replayed across users or contexts.
- Detachment is an explicit attachment state with actor and timestamp. It stops
  active attachment behavior while allowing authorized browsing of retained
  bounded history.
- The Source view is a dedicated read-only middle-column surface. Browsing does
  not create messages, events, reactions, or other application writes.

## Consequences

Hover can present paginated, chronological Source history without becoming a
second store of provider records. Revocation takes effect across initial state,
events, in-flight requests, and cursor reuse. Browsing depends on upstream
availability, and retained history remains readable only while both the Space
membership and detached attachment continue to authorize it.
