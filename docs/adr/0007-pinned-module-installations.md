# 0005: Pinned Module installations

## Status

Accepted

## Context

Hover Spaces need reusable AI automation without letting a catalog edit move
existing output to a different prompt, runtime, Source set, or native topic.
Source access and historical availability are already represented by Space
Attachments, while launch is the atomic boundary between private Setup and a
member-visible Space.

## Decision

- A realm-scoped Module Definition has append-only published Module Versions.
  Each version records its output contract, runtime and prompt identities,
  controlled native destination topic, navigation metadata, supported trigger
  rows, Source capability requirements, and a canonical content hash.
- A Module Installation pins one version. Its bindings reference active Space
  Attachments and declared requirement rows; they never reference raw Sources
  or private provider identifiers. Manual, bounded new-Source debounce, and
  scheduled cadence/local-time/IANA-timezone settings use structured rows.
- Installation mutation requires both active Space membership and Space
  Administrator responsibility. Identical installation replay is idempotent;
  a different current configuration conflicts. Upgrades disable the old
  installation and create a provenance-linked successor.
- Setup stores configured installations. Space launch revalidates bindings and
  capabilities under the Space lock, then activates all configured
  installations at the shared launch timestamp. Processing begins there unless
  an administrator explicitly confirmed an earlier bounded start within every
  binding's availability.
- Detaching an in-use Source hides the attachment and pauses launched
  installations without deleting their bindings or output. Resuming requires
  an explicit compatible rebind. Disabled and paused installations remain
  visible in administrator setup but only enabled installations drive member
  navigation.
- The full sanitized installation projection travels in initial state and
  `hover_space` update events. The client derives native Module topic links
  exclusively from enabled server-owned installations.

## Consequences

Publishing cannot silently change a running Space, provenance remains pinned
across upgrades, and a Source grant cannot bind an unattached Source. Runtime
execution remains a separate Studio operation; Hover stores no provider keys
such as JIDs and does not infer producer identity from display names.
