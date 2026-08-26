# ADR 0020: Make the Hover light system the global Zulip presentation layer

## Status

Accepted

## Context

Hover's light visual language was initially expressed in a channel/topic-only
stylesheet guarded by `hover-enabled` and `hover-topic-screen`. The rest of
the client already has a shared Cofounder design-system bridge that maps
`--ds-*` tokens to Zulip's production semantic CSS variables, but that bridge
used a different blue and lavender system. This split made native Zulip
surfaces and Hover views look like separate applications, and required Hover
views outside the topic screen to carry fallback color literals.

## Decision

- The Hover light palette, text hierarchy, radii, shadows, and system font
  stack are defined in `web/styles/cofounder/design-system.css`, which is
  loaded for the complete web application.
- Existing `--ds-blue-*` names remain compatibility aliases during migration,
  but resolve to the Hover green action scale. New code should use semantic
  `--ds-action-*`, `--ds-surface-*`, `--ds-text-*`, and `--ds-border-*`
  tokens rather than color-family names.
- The existing `--hover-topic-*` and `--hover-overlay-*` names are globally
  aliased to those shared tokens so current Hover surfaces do not depend on
  topic-screen activation.
- `cofounder/app.css` is global presentation CSS. Hover capabilities are
  built into the application for every realm; `hover-enabled` is a static
  layout hook, not a realm setting or feature gate.
- `topic-screen.css` remains narrowly scoped because it adapts a native Zulip
  channel/topic layout; it must not impose that layout on non-conversation
  screens.

## Consequences

All Zulip and Hover surfaces now share a single visual foundation and the
same built-in Hover capabilities. The migration retains native semantic color
hooks while removing per-realm access, routing, and interaction gates.
Screen-specific selectors can be simplified incrementally as they move from
compatibility aliases to shared semantic tokens.
