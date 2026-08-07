# Cofounder Design System

## Status and scope

This document describes the Cofounder visual system implemented in the Zulip
web application. It is the design contract for application chrome, navigation,
message surfaces, controls, and the composer.

The system is intentionally quiet and editorial. Warm neutral surfaces carry
conversation content, while blue identifies primary action and intelligence.
Cyan and green are reserved for system activity and successful progress.
Expressive brand moments should remain concentrated in dedicated marketing
surfaces rather than spread through the operational interface.

## Sources of truth

- `web/styles/cofounder/design-system.css` defines primitive and semantic
  colors, spacing, shape, depth, motion, layout, reusable surfaces, and the
  bridge to Zulip's semantic tokens.
- `web/styles/cofounder/typography.css` defines font families, the responsive
  type scale, and production typography mappings.
- `web/styles/cofounder/app.css` composes the design system across Zulip's
  navigation, sidebars, message feed, composer, overlays, and controls.
- `web/src/bundles/app.ts` loads the Cofounder styles after Zulip's base styles.
- `web/src/bundles/common.ts` loads Source Sans 3 and Source Code Pro from the
  existing Zulip dependencies.

When this document and production CSS disagree, production tokens and tested
component behavior take precedence. Update this document in the same change.

## Principles

1. **Quiet by default.** Start with canvas, paper, and raised neutral surfaces.
   Introduce color only when it communicates identity, state, or action.
2. **Hierarchy is explicit.** Use type size, weight, spacing, and contrast before
   adding labels, borders, or decoration.
3. **Product evidence over ornament.** Interface surfaces should clarify actual
   workflows. Decorative effects must not compete with conversation content.
4. **Human control is visible.** Hover, active, focus, selected, disabled, and
   reduced-motion states are required behavior.
5. **Mono means data.** Reserve monospace typography for code, measurements,
   timestamps, counters, identifiers, and other system metadata.
6. **Italics are semantic.** Do not apply italic styling to layout containers or
   general interface copy. Use italics only for authored emphasis or an existing
   Zulip state whose meaning depends on it.

## Typography

### Font families

**Source Sans 3 VF** is the production proportional typeface for all interface
copy, controls, navigation, messages, and headings. It is an open-source
variable font already loaded by Zulip's shared frontend bundle.

The compatibility token `--font-saans` currently resolves to
`"Source Sans 3 VF", sans-serif`. The token name remains temporarily to avoid an
unrelated migration across component styles; it does not mean that the licensed
Saans family is in use.

**Saans Mono**, when installed locally, and the bundled **Departure Mono**
fallback serve code and system metadata through `--font-saans-mono`. Monospace
text should be functional rather than decorative.

Use these defaults:

- Body and interface copy: Source Sans 3, weight 400.
- Headings, sender names, selected navigation, and concise labels: weight 500.
- Avoid weights above 600 in routine application chrome.
- Use upright text by default. Never set `font-style: italic` on `body`, page
  regions, message rows, sidebars, or form controls.
- Use tabular numerals for counters and timestamps.
- Keep long-form reading content near `--ds-measure` (`70ch`).

### Type scale

| Role       | Class/token                  | Desktop size | Line height |
| ---------- | ---------------------------- | -----------: | ----------: |
| Display XL | `.display-xl`                |         72px |        1.05 |
| Display LG | `.display-lg`                |         56px |         1.1 |
| Display MD | `.display-md`                |         40px |        1.15 |
| Headline   | `.headline`                  |         28px |         1.2 |
| Card title | `.card-title`                |         22px |        1.25 |
| Subhead    | `--type-subhead-size`        |         20px |         1.4 |
| Body large | `--type-body-lg-size`        |         18px |         1.5 |
| Body       | `--type-body-size`           |         16px |         1.5 |
| Body small | `--type-body-sm-size`        |         14px |         1.5 |
| Caption    | `--type-caption-size`        |         12px |         1.4 |
| Button     | `--type-button-size`         |         15px |         1.2 |
| Mono       | `.mono` / `--type-mono-size` |         13px |         1.5 |

Display sizes reduce at 900px and again at 600px. Body copy remains readable
instead of shrinking proportionally with display text.

## Color

Components consume semantic tokens. Primitive tokens describe literal values
and should not be referenced when a semantic token already expresses the
intended role.

| Intent          | Semantic token         | Current value          |
| --------------- | ---------------------- | ---------------------- |
| Page canvas     | `--ds-surface-canvas`  | Neutral 50, `#f5f5f2`  |
| Paper content   | `--ds-surface-paper`   | Neutral 25, `#fbfbf8`  |
| Raised control  | `--ds-surface-raised`  | White, `#ffffff`       |
| Inverse surface | `--ds-surface-inverse` | Navy 950, `#071826`    |
| Primary text    | `--ds-text-primary`    | Neutral 800, `#3d3b39` |
| Secondary text  | `--ds-text-secondary`  | Neutral 500, `#777572` |
| Subtle border   | `--ds-border-subtle`   | Neutral 200, `#d8d7d2` |
| Primary action  | `--ds-action-primary`  | Neutral 950, `#252422` |
| Accent action   | `--ds-action-accent`   | Blue 500, `#2297df`    |
| Keyboard focus  | `--ds-focus`           | `#0b75bd`              |
| Text selection  | `--ds-selection`       | `#bce8ff`              |

Use blue for primary interaction, links, focus, unread state, and selection.
Use cyan and green only for meaningful activity or success. Do not create large
decorative blue surfaces in reading regions.

## Spacing, shape, and depth

Spacing uses a four-pixel base through `--ds-space-1` to `--ds-space-30`.
Choose the nearest token rather than introducing one-off values.

- Small inline shape: `--ds-radius-sm` (`6px`).
- Controls and inputs: `--ds-radius-control` (`8px`).
- Cards and message groups: `--ds-radius-card` (`14px`).
- Composer and large product windows: `--ds-radius-window` (`20px`).
- Pills and counters: `--ds-radius-pill`.

Shadows always combine a vertical offset with a soft blur:

- `--ds-shadow-control` for compact floating controls.
- `--ds-shadow-card` for paper conversation surfaces.
- `--ds-shadow-float` for the composer, dialogs, and popovers.

Do not stack multiple paper cards inside one another. Nested content should use
spacing, dividers, or a raised control surface instead.

## Application composition

### Navigation and sidebars

The top navigation is a lightly translucent paper surface with a subtle border
and restrained blur. Sidebars sit directly on the warm canvas and use borders to
separate regions.

Section labels are compact uppercase captions. Selected navigation uses a blue
inset marker rather than a filled accent background. Unread counters use the
mono stack and tabular numerals.

### Message feed

Each conversation group is a paper card on the canvas. Message headers use a
consistent neutral surface; channel identity remains visible through icons and
labels instead of colored header bands.

Message text is the primary evidence and receives the strongest readability.
Metadata is secondary, compact, and monospace where it represents time or
system state. Selected messages use a visible blue outline without recoloring
their content.

### Composer

The composer is the strongest product window in the interface. It uses the
large window radius, the floating shadow, and a lightly translucent paper
surface. The send action uses the strongest local contrast. Embedded formatting
controls stay quiet until hover or focus.

### Floating surfaces

Popovers, menus, dialogs, autocomplete results, and the emoji picker share the
card radius, subtle border, raised paper surface, and floating shadow. They are
page-specific compositions, not nested generic cards.

## Components and interaction

- Primary actions use a dark or accent-filled solid button.
- Secondary actions use a neutral paper or subtle surface.
- Status pills use `.ds-pill` and are non-interactive unless explicitly given
  button semantics and complete interaction states.
- Reusable paper cards use `.ds-surface`; do not nest them.
- Every interactive control must provide visible hover, active, focus-visible,
  and disabled states.
- Primary touch targets must be at least 40px high. Existing dense secondary
  controls may remain smaller only when their surrounding target is accessible.
- Focus rings must not rely on color alone or be hidden by overflow clipping.

## Motion

Use `--ds-ease-out` with the fast, base, or slow duration token. Motion should
explain response and hierarchy:

- Fast (`160ms`) for immediate control feedback.
- Base (`240ms`) for shadows, surface changes, and small transitions.
- Slow (`700ms`) only for major branded or explanatory sequences.

The interface respects `prefers-reduced-motion` by removing transitions and
animations while preserving all state information.

## Responsive behavior

The primary breakpoints are 900px and 600px.

- At 900px, conversation cards reduce horizontal margin and display typography
  steps down.
- At 600px, cards and the composer use tighter radii and spacing while retaining
  readable body text and reachable controls.
- Horizontal page overflow is never permitted.
- Intentional horizontal scrolling is limited to bounded controls such as tab
  rails and must not affect the document viewport.

## Accessibility

- Maintain visible keyboard focus on every interactive element.
- Preserve sufficient text and control contrast on all warm neutral surfaces.
- Do not communicate state with color alone.
- Keep authored message content selectable and readable at browser zoom.
- Disabled controls must be visually distinct and non-interactive.
- Respect reduced motion and user font-size preferences.
- Treat italic, uppercase, and monospace styles as semantic signals rather than
  decoration.

## Implementation rules

1. Add literal values as primitive tokens, then map them to semantic intent.
2. Components should consume semantic tokens rather than primitive colors.
3. Prefer the existing type classes and tokens over local font declarations.
4. Do not add a new font download when Source Sans 3 or the mono stack covers the
   use case.
5. Do not override inline channel colors unless identity remains visible through
   another accessible cue.
6. Keep the Cofounder styles loaded after Zulip's base component styles.
7. Test both desktop and mobile widths after changing shared surfaces or type.
8. When the Vagrant Webpack watcher misses a host-side stylesheet edit, touch the
   changed file inside the VM before evaluating the browser result.

## Review checklist

Before merging a design change, confirm:

- The change uses semantic tokens and the established type scale.
- Source Sans 3 remains upright for general UI and message content.
- Monospace is limited to data, code, identifiers, or system metadata.
- Hover, active, focus-visible, selected, and disabled states are present.
- Touch targets and contrast remain accessible.
- There is no horizontal page overflow at 900px or 600px.
- Reduced-motion behavior preserves meaning.
- `stylelint` and `git diff --check` pass.
- The production frontend bundle compiles.
- The result has been visually inspected in the running Zulip application.
