# Cofounder-light v3 visual contract

Primary reference: `cofounder-light-design-reference-stitched-v6.png`

This contract translates the approved reference into repeatable constraints. A redesign is not
approved merely because it is light, rounded, or complete. It must preserve the source story and
use the visual grammar below.

## Foundation

| Property        | Contract                                                                                          |
| --------------- | ------------------------------------------------------------------------------------------------- |
| Canvas          | Warm off-white, approximately `#f7f6f2`; never pure white behind every surface                    |
| Paper           | White or subtly warm white, approximately `#fffefa`                                               |
| Primary text    | Near-black charcoal, approximately `#20221f`                                                      |
| Secondary text  | Neutral gray, approximately `#696b66`                                                             |
| Accent          | Cobalt blue, approximately `#0878e8`, reserved for focus, links, selection, and active indicators |
| Primary action  | Near-black fill with white text; blue is not the default primary button fill                      |
| Semantic colors | Muted green, amber, and red used only where meaning requires them                                 |
| Type            | Compact sans-serif product typography; 12–14px body, 10–12px metadata, 14–18px section titles     |
| Spacing         | `4 / 8 / 12 / 16 / 24px`; prefer compact groupings over presentation-scale whitespace             |
| Control height  | Usually 28–34px; dense menu rows may be 28–32px                                                   |
| Radius          | 6–8px controls, 10–14px panels; pills only for statuses or compact segmented controls             |
| Border          | 1px quiet neutral border; borders carry more structure than shadows                               |
| Shadow          | Subtle and limited to dialogs, menus, popovers, and other elevated/transient surfaces             |

## Composition rules

- Preserve the source component's native scale and context. A primitive remains a primitive; a
  screen remains an application screen.
- Do not wrap every component in a showcase card. Panels exist only when the component itself is a
  panel or needs a realistic parent context.
- Favor dense rows, aligned labels, quiet dividers, and short vertical rhythms.
- Keep strong hierarchy local. Story titles, filenames, component paths, and batch metadata never
  appear inside the UI.
- Use blue as a narrow signal. Large blue areas require a source-semantic reason.
- Empty states remain compact and purposeful; they do not become poster-like compositions.

## Archetype rules

### Controls

- Primary button: dark fill, white label, compact height.
- Secondary button: paper fill, neutral border, dark label.
- Tertiary action: text or quiet ghost treatment.
- Disabled state reduces contrast without becoming a blue-tinted primary action.
- Focus uses a thin cobalt ring or border, not a broad glow.

### Forms

- Labels sit close to their controls and are visually stronger than helper copy.
- Inputs use quiet borders, compact padding, and clearly distinct focus/error states.
- Related controls form dense vertical groups; avoid large card padding.
- Actions align at the bottom edge of the form or dialog when present.

### Menus and popovers

- Use compact 28–32px rows, aligned icon/label/shortcut columns, and quiet separators.
- Shortcut keys are small bordered keycaps, never substituted or omitted.
- The menu panel is sized to content and uses a restrained elevated shadow.

### Dialogs

- Use a compact header/body/footer hierarchy and preserve every action.
- The title is 16–18px, not a display heading.
- Content padding is usually 16–24px; field gaps are 12–16px.
- The primary footer action is dark unless the source semantics require destructive color.

### Lists and tables

- Preserve information density, column alignment, row actions, statuses, and pagination.
- Use quiet rules and compact rows rather than independent cards per record.
- Selected rows may use a faint cobalt tint; status chips remain semantic and small.

### Navigation

- Selected items use a light cobalt wash, thin indicator, or strong label—not a large filled tile.
- Navigation remains subordinate to content and uses consistent row height.

### Feedback

- Semantic color appears in the icon, border, status chip, or narrow tint—not as a decorative wash.
- Preserve dismissal, undo, retry, and other actions.
- Toasts and banners remain compact enough to coexist with product content.

### Screens

- Preserve shell, navigation, content columns, composer/toolbars, and spatial relationships.
- Do not turn the screen into a generic dashboard or a card floating on a blank canvas.
- Apply tokens and hierarchy locally while retaining the recognizable source application structure.

## Automatic rejection criteria

A result fails validation if any condition is true:

1. Visible catalogue metadata, filenames, paths, or `.png` suffixes appear in the UI.
2. Source text, controls, icons, shortcuts, actions, or states are missing or changed.
3. Content crosses an assigned crop boundary or is clipped.
4. The result uses oversized typography or materially lower information density than the source or
   reference.
5. A standard primary action uses blue instead of the contracted dark treatment.
6. Broad gradients, neumorphic shadows, excessive pills, or generic dashboard styling appear.
7. A full screen loses its application context or a primitive is inflated into a showcase card.
8. Empty whitespace dominates because the component was framed incorrectly.
9. The result is blurry, illegible, malformed, or visibly reconstructed from unreadable source text.
10. The result resembles neighboring batch items more than its own source story.

## Approval record

Every final asset must record two independent statuses:

- `semanticStatus`: exact source purpose/content/state preservation.
- `fidelityStatus`: compliance with this visual contract and the primary reference.

Only assets with both statuses set to `approved` count toward visual-fidelity coverage.
