# 0021: Independently authorized Summary containers

## Status

Accepted

## Context

Hover presents a Summary beneath a parent Space, but a Summary can have a
smaller membership than that Space. A browser-only member list or a topic
label cannot enforce that boundary. Topic-level authorization would need to be
added consistently to message fetch, search, narrows, unread state, events,
links, replies, and future inherited Zulip surfaces.

Summary editions also need durable generation-time provenance. Editing a
Summary's current inputs must not change what an older edition claims to have
used, and revoked access must not be bypassable through a direct message URL.

## Decision

- **Summary** is the user-facing form of a scheduled Module Installation.
  Internal models and APIs may retain `ModuleInstallation` where it remains
  the durable automation owner.
- Each Summary owns a separate private native stream. Hover projects that
  stream as a child of the parent Space in navigation; the relationship is a
  presentation projection, not the authorization boundary.
- The Summary member set is a subset of active parent-Space members. Native
  stream subscriptions enforce access across message fetch, search, narrows,
  unread state, events, links, and replies. Removing a parent-Space
  subscription also removes every child Summary subscription; rejoining does
  not restore independently selected Summary membership.
- A Summary edition stores the exact input topic identities and citation
  message identities accepted at generation time. The generator rejects a
  citation outside those declared inputs.
- Evidence is authorized again at read time. Inaccessible citations contribute
  only to one aggregate `forbidden_count`; their identifiers, topics,
  providers, URLs, and ordering are never projected.
- Under the strict withdrawal policy, losing access to any required
  generation-time input withdraws the complete edition, including historical
  editions. Changing the Summary's current inputs never unlocks an older
  edition.
- Summary creation is one server transaction: validate the parent Space and
  member subset, create the private native stream and subscriptions, persist
  input bindings and daily schedule, and project the empty Summary. No
  placeholder message is created.

## Consequences

Hover can show Summaries within one Space hierarchy without relying on a new
topic-authorization fork in inherited Zulip code. A Summary consumes a native
stream identity and requires virtual-parent navigation, but direct message
URLs and new inherited message surfaces fail closed by default. Source topics
remain readable by every parent-Space member.
