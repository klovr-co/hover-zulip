# Cofounder Design System

## Direction

Hover is migrating to a standalone Cofounder component library. The library
owns its markup, `cf-*` class API, visual tokens, interaction states, and the
TypeScript required to change component state after render. Zulip components
remain migration inputs, not the target architecture.

The approved visual authority is
`design-references/cofounder-light-design-reference-stitched-v6.png`, translated
into repeatable constraints by
`design-references/cofounder-light-v3-spec.md`. The ZIP extraction is supporting
evidence only; its marketing and dark Canvas systems are not production token
sources.

This is an **Operate** interface: compact, legible, and optimized for repeated
workspace tasks. Warm neutral surfaces carry content. Charcoal identifies the
strongest local action. Cobalt identifies focus, links, selection, and active
state. Semantic green, amber, and red appear only where meaning requires them.

## Source of truth

- `web/styles/cofounder/components/foundations.css` owns literal primitives,
  semantic roles, spacing, shape, depth, type roles, and motion.
- `web/styles/cofounder/components/*.css` owns component appearance and every
  visual interaction state.
- `web/templates/cofounder/components/*.hbs` owns reusable component markup.
- `web/src/cofounder/components/*.ts` owns stateful component behavior and
  exported component types.
- Product templates consume the Cofounder partials and retain product-specific
  classes only as behavior hooks or composition selectors.

The former typography bridge is retired. `app.css` now consumes only native
`--cf-*` roles, but remains a temporary product-composition layer to decompose
as each feature surface receives an owned Cofounder contract. The reduced
`design-system.css` file is only a host adapter from remaining Zulip layout and
semantic variables to Cofounder roles; it must not declare Cofounder primitives
or receive new component rules. Delete adapter assignments as their host
consumers migrate.

`cofounder_foundations.test.cjs` verifies that every un-fallbacked `--cf-*`
reference resolves inside the owned stylesheet graph and that no Cofounder
stylesheet can reintroduce `--ds-*` tokens.

The generated template catalog and its Storybook-only calibration stylesheet
are retired. Curated top-level Cofounder stories use the same `.cf-theme` and
component CSS as production; live-app checks are the second supported visual
verification surface.

## Naming and ownership

- Component classes use the `cf-` prefix: `.cf-button`, `.cf-field`,
  `.cf-surface`, `.cf-status`.
- Elements and variants use BEM-style names: `.cf-button__label`,
  `.cf-button--primary`.
- Tokens use the `--cf-*` prefix. Literal color values are permitted only in
  `foundations.css`.
- Product hooks such as `.save-button` may coexist with a component class while
  JavaScript is migrated. Product hooks must not define the component's visual
  appearance.
- Do not add legacy `.action-button`, `.btn-*`, `.ds-*`, or Zulip intent classes
  to new Cofounder component markup.

## Foundation contract

| Role                | Token                 | Value     |
| ------------------- | --------------------- | --------- |
| Canvas              | `--cf-surface-canvas` | `#f7f6f2` |
| Paper               | `--cf-surface-paper`  | `#fffefa` |
| Primary text/action | `--cf-color-ink`      | `#20221f` |
| Secondary text      | `--cf-color-ink-soft` | `#696b66` |
| Border              | `--cf-color-line`     | `#d9d8d2` |
| Focus/accent        | `--cf-color-accent`   | `#0878e8` |
| Success             | `--cf-color-success`  | `#278642` |
| Warning             | `--cf-color-warning`  | `#9a6500` |
| Danger              | `--cf-color-danger`   | `#c63b35` |

Spacing follows `4 / 8 / 12 / 16 / 24px`. Standard controls are 32px tall on
desktop and 40px on narrow touch layouts. Controls use a 7px radius, panels use
12px, and overlays use 14px. Pills are reserved for concise statuses.

Source Sans 3 is the deterministic production UI face. Interface body copy is
14px, labels are 13px, metadata is 12px, and routine surface titles are 18px.
Display typography is not part of the application component library.

## Component contracts

### Button

Use the `cofounder/components/button` partial.

- `primary`: charcoal committed action; one strongest action per local region.
- `secondary`: paper surface with a quiet border.
- `ghost`: low-emphasis text action.
- `danger`: destructive committed action.
- `success`: compact completed state, not a general call to action.
- `compact=true`: dense secondary controls only.
- Icon-only buttons require an accessible label.

All variants implement hover, active, focus-visible, and disabled states. Async
buttons retain their label width while a loading indicator is visible.

### Text field

Use the `cofounder/components/text_field` partial. Labels remain visible and
close to their control. Hint and error copy receive stable IDs and are connected
through `aria-describedby`. Errors set `aria-invalid`; required fields retain
native required semantics.

### Surface

Use `cofounder/components/surface` as a partial block only when the component is
actually a panel or elevated region. Do not wrap every primitive in a surface,
and never nest generic surfaces. Raised and overlay depth are explicit variants.

### Status

Use `cofounder/components/status` for concise, non-interactive state. Statuses
may be neutral, accent, success, warning, or danger. Semantic color stays in the
compact status rather than washing an unrelated parent surface.

### Dialog

`dialog_widget` is the production Cofounder dialog shell. Its backdrop,
container, heading, body, footer, buttons, spinner, and tab region use the
`cf-dialog__*` contract while Micromodal continues to own focus trapping,
Escape handling, lifecycle callbacks, and removal from the DOM.

Callers choose `modal_submit_button_variant` explicitly when the committed
action is destructive. `cofounder/components/dialog.ts` owns loading state:
actions expose `aria-busy`, retain their label width, and disable both footer
buttons until the request settles. On narrow touch layouts, dialogs anchor to
the bottom edge without losing the same semantic structure.

### Menu

Use `cofounder/components/menu` with `cofounder/components/menu_item` for new
menus. The container owns the semantic `menu` list, scrolling, width limits,
surface, and mobile touch targets. Items own `menuitem` roles, focus, selected,
disabled, danger, icon, label, and shortcut states. Runtime traversal must use
`cofounder/components/menu.ts` so disabled actions and custom radio items share
one keyboard contract.

Migrating production popovers may temporarily retain behavior-specific legacy
classes beside `cf-menu*` hooks. Generic visual rules must target `cf-menu*`;
the legacy classes are not part of the Cofounder component API and should be
removed after their JavaScript selectors have moved.

### Banner

Use the shared `components/banner` entry point, which renders the standalone
`cofounder/components/banner` contract. Its intent controls the semantic live
region and quiet left-edge accent: warning and danger are alerts; neutral,
brand, info, and success are status updates. Actions use Cofounder button
variants directly, and dismiss controls use `cf-banner__close` with an inline
SVG icon.

Popup and navbar placement are layout variants of the same component. Runtime
updates must target `cf-banner__label`, `cf-banner__close`, and
`cf-banner--{intent}`; caller-specific classes may identify behavior but must
not carry component styling.

### Notice

Composer, modal, and feed-level notices use the
`cofounder/components/notice` contract. It owns semantic intent, flexible
content/action layout, and the accessible dismiss control while
feature-specific classes remain behavior-only.

### Toast

Transient, elevated feedback uses `cofounder/components/toast`. Toasts own
semantic intent, title/content/action structure, dismiss controls, motion, and
their fixed host/stack layout. Persistent or page-anchored feedback remains a
banner or notice instead.

### Tabs

Use `cofounder/components/tabs` for related views within one surface. The
component owns the `tablist` and `tab` semantics, compact segmented surface,
selected and disabled states, focus treatment, fill/wrap layout modifiers, and
mobile touch targets. Stateful callers use `components.toggle`, which owns
roving focus, arrow-key movement, and selection callbacks through `cf-tabs*`
hooks.

### Navigation item

Rail and compact list navigation use `cofounder/components/nav_item`. The
component owns icon, label, badge, masked-unread, selected, disabled, focus,
and trailing-action states. Feature selectors may remain as explicit behavior
adapter classes during migration, but must not provide component visuals.

Channel rows use `cofounder/components/channel_nav_item`, which owns the
channel link, privacy glyph, unread signals, selected/muted states, and the
semantic search, compose, and overflow controls. Topic lists and Hover-specific
module/source sections remain nested feature content below the owned header.

Nested topic rows use `cofounder/components/topic_nav_item`. The route link,
resolved marker, unread signals, selected/muted states, visibility-policy
button, and overflow button are separate semantic targets under one visual
contract. Feature behavior may retain `topic-box`, `change_visibility_policy`,
and `topic-sidebar-menu-icon`; `cf-topic-nav*` owns every visual state.

Topic-list navigation actions use `cofounder/components/topic_nav_action`.
Show-all and new-topic rows share the topic rhythm but remain native links with
their existing delegated behavior hooks; they do not impersonate selectable
topic rows or carry topic policy state.

Direct-message rows use `cofounder/components/dm_nav_item`. The component owns
presence and group markers, recipient/status content, unread signals, selected
state, and route semantics while `dm-box` remains a delegated behavior hook.
Overflow into the complete conversation list uses the native button contract
in `cofounder/components/dm_nav_action`; arrow-key list navigation activates
both links and buttons.

Direct-message section framing uses `cofounder/components/dm_section_header`
for the sticky collapse state, typed feed/compose actions, unread total, and
the modal filter slot. Existing IDs and rotation classes carry application
state; `cf-dm-section-header*` owns the layout and every visual state.

## Icon ownership

Cofounder primitives render icons through `cofounder/components/icon` as
inline, current-color SVG. The initial set covers close, plus, check,
chevron-down, search, overflow, and warning semantics. Add named SVG geometry
to this renderer when a migrated component needs another symbol; do not reach
back into the Zulip icon font from `cf-*` markup. The legacy font remains only
for product surfaces that have not migrated yet. Unicode glyphs and emoji are
not substitutes.

All shared square icon actions render through
`cofounder/components/icon_button`. The compatibility `icon-button-*` classes
remain as runtime intent hooks while `cf-icon-button*` owns sizing, focus,
disabled/loading states, color intent, and typed SVG rendering.

Conversation recipient headers render through
`cofounder/components/conversation_header`. The component owns the channel or
direct-message identity, topic hierarchy, sticky surface, typed action icons,
responsive control disclosure, and focus treatment. Existing message-header,
recipient-control, and route classes remain behavior hooks until their callers
move to the `cf-conversation-header*` API.

Message presentations use the `cf-message-item*` contract. The standalone
`cofounder/components/message` partial is an isolated preview, while production
rows expose the same contract through `single_message`, `message_body`, and
`message_avatar`. Cofounder owns avatar geometry, native sender interaction,
sender/time hierarchy, content measure, unread and pending modifiers, typed bot
and state icons, hover/focus action disclosure, reaction states, and narrow
touch targets.

Controllers for condensing, copying, quoting, widgets, tooltips, user cards,
message reports, local echo, touch selection, editing, and viewport traversal
target `cf-message-item__*` elements. `cf-message-group` owns recipient-group
composition; `cf-message-item`, `cf-message-item__frame`, and
`cf-message-item__body` own row identity and grid anatomy. Production message
markup, styles, controllers, and tests must not depend on the superseded
`recipient_row`, `message_row`, `selectable_row`, `messagebox`, or
`messagebox-content` classes.

`Cofounder/Messages/Production row` renders the real production partial tree
and is authoritative for unread, reaction, bot, local-echo, desktop, and narrow
touch states.

### Message actions and reactions

Production message rows use the `cf-message-actions*` and
`cf-message-reactions*` contracts. Actions and reactions are native buttons
with accessible names, focus-visible treatment, disabled semantics, and 40px
targets on narrow touch layouts. Typed Cofounder icons own edit, move, react,
overflow, star, retry, and dismiss presentation; these controls must not use the
Zulip icon font.

`MessageCleanReaction.selected` is the reaction state source of truth. Render
and runtime updates derive `cf-message-reaction--selected` and `aria-pressed`
from that boolean rather than transporting a CSS class through application
data. Product hooks such as `edit_content_button`, `move_message_button`,
`refresh-failed-message`, and `remove-failed-message` remain behavior-only.

`Cofounder/Messages/Actions and reactions` renders the production partials and
is the authoritative scene for own-message actions, starred state, selected and
archived reactions, failed-send controls, and narrow touch geometry.

### Source actions and evidence

Knowledge-source controls use `cofounder/components/source_actions`. Evidence,
linked-provider, and unavailable-provider states share the
`cf-source-actions*` contract; provider keys map to typed inline Cofounder SVGs
with a generic link fallback. Cofounder source markup must not render Font
Awesome or the Zulip icon font.

Evidence launchers expose `data-cf-evidence-url`; retry actions expose
`data-cf-evidence-retry-url`. `hover_evidence` owns request validation and
dialog lifecycle but does not depend on presentation classes. Loading, results,
empty, retryable, and permanent-error content use `cf-evidence*`, `cf-notice`,
and `cf-button` contracts. `Cofounder/Components/Source actions` and
`Cofounder/Patterns/Evidence` render the real production partials and are the
authoritative desktop and narrow-touch verification scenes.

Read-only source history uses `cf-source-view*` for page composition and
`cf-source-record*` for record anatomy. Search, pagination, retry, provider
identity, retained-history status, quoted context, transcripts, and media
metadata compose the shared field, button, status, and typed-icon contracts.
The `hover_source_view` module may retain its domain filename, but its rendered
markup and controller selectors use Cofounder hooks exclusively.
`Cofounder/Patterns/Source browser` renders the production page and record
partials for populated, loading, retry, empty, desktop, and narrow-touch states.

### Space navigation

Expanded launched Spaces use `cf-module-nav*` and `cf-source-ledger*` for
enabled Module destinations, generated counts, attached-source identity,
retained metadata, and internal or external navigation. Setup Spaces use the
parallel `cf-space-setup*` row and compose the same source-ledger contract once
the first attachment exists.

Controllers use `data-cf-space-id`, `data-cf-module-key`, and
`data-cf-source-key` hooks. Stable Module definition and Source provider keys
map to the typed Cofounder icon union in `hover_spaces.ts`; server-owned legacy
`navigation_icon` strings must not reach templates. `Cofounder/Components/
Channel navigation item/Space Navigation` renders the real launched and setup
templates and is authoritative for expanded composition, external sources,
focus states, zero overflow, and narrow-touch geometry.

### Space setup workbench

Private Space setup uses the `cf-space-workbench*` contract for Space identity,
attached Sources, pinned Modules, teammate access, launch readiness, Source
discovery, verified preview, and bounded history selection. Shared `cf-field`,
`cf-button`, `cf-status`, source-ledger, dialog, and typed-icon contracts own the
primitives; `data-cf-space-*`, `data-cf-module-*`, and `data-cf-member-*` hooks
own dynamic behavior.

The server's `navigation_icon` strings remain schema inputs only. Stable Module
definition and Source provider keys resolve through the typed mappings in
`hover_spaces.ts` before templates render. `Cofounder/Settings/Dialogs/Space
Setup` composes the real production dialog and setup/discovery templates for
populated, verified, desktop, and narrow-touch verification states.

### Awareness

For You and Team Pulse use the `cf-awareness*` contract for feed composition,
cards, unread state, reasons, current state, todo context, source actions, and
responsive action geometry. `hover_awareness_view` may retain its feature
module name, but rendered awareness markup and controller selectors use
`cf-awareness*`. `Cofounder/Patterns/Awareness` renders the real production
template for populated, retry, desktop, and narrow-touch states.

### Global search

Permission-filtered search uses the `cf-global-search*` contract for page
composition, labeled search controls, result metadata, save state, read-only
Source evidence, loading status, and empty results. The `hover_search_view`
module and `/json/hover/search` endpoint retain their domain names, while
rendered markup and controller selectors use Cofounder hooks exclusively.

Knowledge results rank before Source evidence. Save actions expose native
`aria-pressed` state and typed star icons; Source records remain visibly and
semantically read-only. `Cofounder/Patterns/Global search` renders the real
production template for populated, searching, empty, desktop, and narrow-touch
verification states.

### Editions

Morning and end-of-day briefs use the `cf-edition*` contract for the editorial
shell, edition tabs, status and loading states, full and focus reading modes,
passages, source actions, carousel controls, and all-clear treatment. The
feature may retain its `hover_editions_view` module and template filenames, but
rendered IDs, classes, and controller selectors use `cf-edition*` exclusively.

Edition actions compose the shared `cf-button` and typed inline-icon contracts;
source launchers use `data-cf-evidence-url`. Narrow layouts preserve 40px touch
targets and zero document-level overflow. `Cofounder/Patterns/Editions` renders
the production template for full, focus, loading, retry, empty, and narrow-touch
verification states.

### Composer

Composer surfaces use the `cf-composer*` contract. The standalone
`cofounder/components/composer` partial provides the visual component and its
default, typing, and disabled verification states. The production compose shell
uses the same contract around the existing `send_message_form`, recipient,
textarea, draft, upload, preview, and send hooks so behavior can migrate without
being reimplemented.

`cf-composer__textarea`, `cf-composer__toolbar`, `cf-composer__send-column`, and
the SVG-backed send/options/close, resize, recipient, and formatting controls
own appearance and responsive geometry. IDs such as `compose-textarea`,
`compose-send-button`, `send_later`, and `compose_close`, along with delegated
classes such as `formatting_button`, `emoji_map`, and `compose_upload_file`,
remain application behavior hooks. Production composer markup must not use the
Zulip icon font; new actions extend the typed Cofounder icon renderer instead.

The `Cofounder/Composer/ProductionToolbar` story renders the real production
template inside its required `#compose > #compose-container` host. Do not use
the generated template-catalog compose entry for layout verification because it
omits that host contract.

### Data table and filters

Dense operational lists use the `cf-data-table*` contract for table surfaces,
column headings, keyboard-accessible sort controls, rows, cells, unread state,
row actions, and empty content. Toolbars use `cf-filter-chip` for toggleable
filters and `cf-load-more` for incremental history loading; `aria-checked` is
the visual and semantic source of truth for chip selection.

Recent Conversations is the first production consumer. Its synchronized header
and body tables share the contract while `recent-view-*` classes remain layout,
focus-navigation, and controller hooks. Runtime topic-policy and folder changes
replace typed SVGs through `cofounder/components/icon.ts`; they do not mutate
icon-font classes. `Cofounder/Data table/Recent conversations` is the
authoritative desktop, narrow, empty, and loading verification scene.

Settings, channel-member, and user-group-member lists use the
`cf-data-table--settings` composition. Sort state remains on semantic
`<th data-sort>` elements for ListWidget compatibility, while typed chevrons
reflect `.active` and `.descend`. Shared `cf-filter-field` and
`cf-drag-handle` primitives preserve the existing `.search`, `.clear-filter`,
and `.move-handle` controller hooks. Settings dropdown callers must opt into
`cofounder=true`; otherwise the shared widget renders a legacy icon-font
trigger. `Cofounder/Components/Data table/Settings members` renders the real
production header/filter template with representative dynamic rows.

Hierarchical conversation indexes use the parallel `cf-conversation-list*`
contract. It owns the filter toolbar, framed sections, folder and channel
headers, topic/direct-message rows, unread and mention signals, typed policy
and overflow actions, collapsed notes, empty states, and responsive touch
geometry. Inbox is the first production consumer; `inbox-*` classes remain
controller and keyboard-navigation hooks, while `Cofounder/Conversation
list/Inbox` renders the real production partial tree for desktop, narrow, and
empty-state verification.

Settings overlays use the `cf-settings-shell*`, `cf-settings-nav*`,
`cf-settings-section*`, `cf-settings-field-row*`, `cf-settings-choice-group*`,
and `cf-settings-stepper*` contracts. The shell owns two-pane and narrow
drill-in composition, selected/locked navigation states, header actions,
field rhythm, segmented choices, and density controls. Existing
`data-section`, `.active`, `.settings-section`, and setting IDs remain behavior
hooks; controller changes synchronize `aria-current` and typed SVG state.
`Cofounder/Settings/Shell` is the authoritative production-template scene.

Connected Account administration composes that shell with the
`cf-connected-accounts*` section and `cf-connected-account*` card/grant
contracts. TypeScript maps approval and provider-health state to semantic
status tones and typed icons; delegated account and grant actions use
`cf-connected-account__*` hooks and shared button variants. Provider secrets
remain absent from rendered data. `Cofounder/Settings/Connected accounts`
renders the real settings overlay, admin section, and dynamic card partial for
approved, pending, revoked, empty, desktop, and narrow-touch states.

### Todo workflow

Suggested Actions and the Todos overlay use the `cf-suggested-action*`,
`cf-todos*`, and `cf-todo-card*` contracts for state, responsibility, due-date,
assignment, completion, evidence, and responsive action layout. Shared
`data-cf-todo-*` hooks let the same controllers update Todo state in message
rows and the overlay without depending on either surface's visual classes.

TypeScript maps projection state to explicit semantic labels and status tones;
templates compose `cf-status`, `cf-field__control`, `cf-button`, and typed icon
primitives rather than accepting presentation classes from application data.
The `hover_*` domain module and event names may remain while rendered markup and
controller selectors use Cofounder hooks exclusively. `Cofounder/Workflow/Todos`
and `Cofounder/Workflow/Suggested action` render the production partials for
active, pending, completed, rejected, empty, desktop, and narrow-touch states.

### Review workflow

Human review responses, clarification notices, review-request state, and
disputed details use the `cf-review-response*`, `cf-review-clarification`,
`cf-review-request*`, `cf-review-details`, and `cf-review-detail*` contracts.
Generated-update replies use the `cf-review-composer*` contract for response
mode, patch fields, guidance, and mobile composition; the behavior controller
reads `data-cf-response-mode`, `data-cf-reply-help`, and
`data-cf-review-patch` hooks without visual-selector dependencies.
Evidence launchers use `data-cf-evidence-url`; delegated review actions use
`data-cf-review-message-id` and `data-cf-review-field-path` without depending
on visual classes. TypeScript maps open, resolved, material, and uncertain
projection state to semantic status tones before rendering.

`Cofounder/Workflow/Review requests` renders the real production message row
for open, resolved, and narrow-touch states. Its integrated verification covers
message identity, generated-update chrome, conflicting evidence, review
actions, zero document overflow, and 40px minimum touch targets.
`Cofounder/Composer/Production Review` and `Production Review Narrow` render the
real production compose template with explicit review-patch state. They are the
authoritative scenes for response-mode accessibility, field population,
contained send controls, zero overflow, and mobile touch geometry.

### Generated updates

Generated message cards use the `cf-message-item--generated-update` modifier
and `cf-generated-update*` contract for module/output identity, source context,
lifecycle state, importance, detail/history actions, and responsive grid
placement. Controllers use `data-cf-generated-message-id`; presentation and
importance strings are converted to shared status tones rather than
interpolated into CSS modifier names.

The generated-update stylesheet specializes the owned message contract and is
the sole authority for card, frame, content, action-row, selected, desktop, and
narrow-touch states. Generic message frame composition now lives in
`message.css`; `app.css` must not reintroduce generated-update or message-frame
compatibility overrides. `Cofounder/Workflow/Generated updates` renders the real
details/history partial for technical metadata, current and superseded history,
desktop, and narrow-touch verification states.

## Migration sequence

1. Foundations, buttons, fields, surfaces, statuses, and loading behavior.
2. Menus, popovers, dialogs, banners, and toasts.
3. Navigation rows, lists, tables, tabs, and pagination.
4. Application shell, sidebars, messages, composer, search, and inbox.
5. Hover-specific Sources, Editions, evidence, connected-account, and workflow
   surfaces.
6. Cofounder icon ownership and removal of remaining legacy component assets.
7. Delete superseded bridge CSS, compatibility aliases, generated legacy
   stories, screenshots, and catalog tooling.

Migrate by component family rather than by arbitrary stylesheet section. A
surface is migrated only when its markup, visuals, dynamic states, accessibility
behavior, and tests all use the Cofounder API.

## Verification

Every component family must demonstrate:

- Real content plus hover, active, focus-visible, disabled, loading, error, and
  empty states where applicable.
- Keyboard operation and accessible naming.
- Desktop and narrow touch layouts with no document-level horizontal overflow.
- Body and placeholder contrast at or above 4.5:1.
- Reduced-motion behavior that preserves state information.
- Production-template rendering, not screenshot-only reconstruction.
- `stylelint`, template validation, unit tests, `git diff --check`, and the
  production frontend build.

The generated Storybook catalog and its redesign/calibration pipeline are
retired. The remaining Storybook configuration is a focused Cofounder
verification harness: it discovers curated Cofounder stories plus the banner
and conversation production fixtures, and it must not grow generic legacy
template coverage. Retire that harness only after equivalent component-state
coverage and representative live application flows are automated at desktop
and mobile widths.
