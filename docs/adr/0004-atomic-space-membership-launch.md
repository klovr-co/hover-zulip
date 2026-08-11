# 0004: Atomic Space membership launch

## Status

Accepted

## Context

Attached Sources can identify internal teammates through verified account
mappings, but an observed participant is not authorization. Setup must remain
private while administrators review those matches, assign explicit roles, and
add unobserved internal teammates. Launch then crosses from Hover setup state
into native Zulip messaging state, where a partial commit could leak a channel
or leave an incorrect subscriber cohort.

## Decision

- A `SpaceMembershipSuggestion` stores only an already-resolved same-realm user,
  proposed role, verified mapping class, and opaque observation basis. Unmatched,
  external, inactive, guest, and bot participants are ignored.
- Suggestions have durable `pending`, `confirmed`, and `removed` decisions. A
  pending suggestion grants no Setup visibility, Source access, native
  subscription, or target event. A Space Administrator confirms the role and
  creates the unique `SpaceMembership` atomically.
- `SpaceMembership` is the confirmed access record. Contributor and Subscriber
  are membership roles; `SpaceAdministrator` is orthogonal responsibility. A
  non-creator administrator must already be a confirmed member, and every
  administrator must be a confirmed active member at launch.
- Setup reads and events target assigned Space Administrators only. Launched
  reads use confirmed membership. Connected Account grants do not imply Space
  membership.
- Every Setup mutation locks the Space first. Launch holds that lock while it
  validates active attachments, explicit history windows, approved accounts,
  resolved suggestions, memberships, roles, and administrators.
- Launch creates one private native channel, anonymous permission groups, and
  the exact confirmed subscriber cohort in the same database transaction, then
  stores the channel and launched state. A case-insensitive channel collision
  is an error. Replaying a completed launch returns the existing projection.
- Launch uses native subscription primitives but sends no welcome, mention, or
  launch message. Normal native convergence events and one authorized Hover
  Space event are emitted only after commit.

## Consequences

An identity match cannot silently broaden authorization, and removing or
changing pending setup data cannot disclose the Space to its target. Launch
failures roll back the Stream, Recipient, Subscription, anonymous UserGroup,
audit log, and Space state together. Contributor posting and Space
administration are represented by explicit native permission groups rather
than being inferred from subscription alone.
