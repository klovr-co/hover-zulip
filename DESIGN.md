# Cofounder Design System

## Status and scope

This document describes the Cofounder visual system implemented in the Zulip
web application. It is the design contract for application chrome, navigation,
message surfaces, controls, and the composer.

The system is intentionally quiet and workspace-like. Pale lavender side rails
frame a near-white conversation surface, while saturated blue identifies the
brand, links, focus, and primary action. Dividers and control outlines provide
structure without shadows or nested cards.

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

1. **Quiet by default.** Start with lavender canvas, conversation paper, and
   outlined controls. Introduce stronger color only for identity or state.
2. **Hierarchy is explicit.** Use type size, weight, spacing, and contrast before
   adding labels, borders, or decoration.
3. **Product evidence over ornament.** Interface surfaces should clarify actual
   workflows. Decorative effects must not compete with conversation content.
4. **Human control is visible.** Hover, active, focus, selected, disabled, and
   reduced-motion states are required behavior.
5. **Mono means data.** Reserve monospace typography for authored code and
   identifiers; timestamps and counters use tabular proportional numerals.
6. **Italics are semantic.** Do not apply italic styling to layout containers or
   general interface copy. Use italics only for authored emphasis or an existing
   Zulip state whose meaning depends on it.

## Typography

### Font families

**Be Vietnam Pro** is the preferred typeface for interface copy, controls,
navigation, and messages. **Manrope** is preferred for brand and display text.
**Avenir Next** and **Source Sans 3 VF** (already loaded by Zulip's shared
frontend bundle) provide metrically similar system and cross-platform fallbacks.

The compatibility token `--font-saans` resolves to
`"Be Vietnam Pro", "Avenir Next", "Source Sans 3 VF", sans-serif`, while
`--font-headline` begins with Manrope. The `--font-saans` token name remains to
avoid an unrelated migration across component styles.

**Saans Mono**, when installed locally, and the bundled **Departure Mono**
fallback serve code and system metadata through `--font-saans-mono`. Monospace
text should be functional rather than decorative.

Use these defaults:

- Body and interface copy: Be Vietnam Pro, with Avenir Next or Source Sans 3 as
  fallbacks, weight 400.
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
| Page canvas     | `--ds-surface-canvas`  | Lavender 50, `#f2f3ff` |
| Paper content   | `--ds-surface-paper`   | Lavender 25, `#faf8ff` |
| Raised control  | `--ds-surface-raised`  | Lavender 25, `#faf8ff` |
| Inverse surface | `--ds-surface-inverse` | Navy 950, `#131b2e`    |
| Primary text    | `--ds-text-primary`    | Slate 800, `#434655`   |
| Secondary text  | `--ds-text-secondary`  | Slate 500, `#737686`   |
| Subtle border   | `--ds-border-subtle`   | Slate 200, `#c3c6d7`   |
| Primary action  | `--ds-action-primary`  | Blue 500, `#004ac6`    |
| Accent action   | `--ds-action-accent`   | Blue 500, `#004ac6`    |
| Keyboard focus  | `--ds-focus`           | `#0053db`              |
| Text selection  | `--ds-selection`       | `#dbe1ff`              |

Use blue for primary interaction, links, focus, unread state, and selection.
Use cyan and green only for meaningful activity or success. Do not create large
decorative blue surfaces in reading regions.

## Spacing, shape, and depth

Spacing uses a four-pixel base through `--ds-space-1` to `--ds-space-30`.
Choose the nearest token rather than introducing one-off values.

- Small inline shape: `--ds-radius-sm` (`4px`).
- Controls and inputs: `--ds-radius-control` (`5px`).
- Selected messages: `--ds-radius-card` (`9px`).
- Composer: `--ds-radius-window` (`9px`).
- Pills and counters: `--ds-radius-pill`.

Application surfaces are flat. Use borders and surface contrast in the main UI;
reserve a soft shadow for transient menus, dialogs, and popovers only.

At the 1422px reference viewport, the application uses a precise
`310px / 802px / 310px` grid with 27px conversation gutters and a 70px header.

## Application composition

### Navigation and sidebars

The top navigation is split by the same vertical dividers as the page. Sidebars
sit directly on the lavender canvas and use borders to separate regions.

Section labels use readable title case. Selected navigation uses a pale outlined
surface. Unread counters use tabular numerals.

### Message feed

The conversation feed stays open and flat. Topic headers use a compact lavender
outlined bar; channel identity remains visible through icons and labels.

Message text is the primary evidence and receives the strongest readability.
Metadata is secondary and uses tabular numerals. Selected messages use a pale
lavender fill and visible blue outline without recoloring their content.

### Composer

The composer is an outlined lavender window anchored 17px from the desktop
viewport bottom. The send action uses the strongest local contrast. Embedded
formatting controls stay quiet until hover or focus.

### Floating surfaces

Popovers, menus, dialogs, autocomplete results, and the emoji picker share the
card radius, subtle border, paper surface, and soft shadow. They are
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

The desktop reconstruction transitions back to Zulip's fluid layout below
1100px; typography continues to step down at 900px and 600px.

- Below 1100px, the rigid desktop columns, fixed user filter, and 70px header
  return to Zulip's responsive geometry.
- At 900px, display typography steps down.
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
4. Keep Source Sans 3 as the bundled fallback when the preferred Stitch faces
   are unavailable; do not make application startup depend on a third-party font
   host.
5. Do not override inline channel colors unless identity remains visible through
   another accessible cue.
6. Keep the Cofounder styles loaded after Zulip's base component styles.
7. Test both desktop and mobile widths after changing shared surfaces or type.
8. When the Vagrant Webpack watcher misses a host-side stylesheet edit, touch the
   changed file inside the VM before evaluating the browser result.

## Review checklist

Before merging a design change, confirm:

- The change uses semantic tokens and the established type scale.
- General UI and message content remain upright in the proportional UI stack.
- Monospace is limited to data, code, identifiers, or system metadata.
- Hover, active, focus-visible, selected, and disabled states are present.
- Touch targets and contrast remain accessible.
- There is no horizontal page overflow at 900px or 600px.
- Reduced-motion behavior preserves meaning.
- `stylelint` and `git diff --check` pass.
- The production frontend bundle compiles.
- The result has been visually inspected in the running Zulip application.
