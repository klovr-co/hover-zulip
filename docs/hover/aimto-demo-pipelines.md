# AIMTO demo pipelines

## Purpose

Replace the fixed development posts created by `populate_hover_demo` one
module at a time. Each pipeline owns one visible AIMTO module and writes a
source-backed output through Clawer's existing durable Hover publication
workflow. The static command remains the deterministic UI fixture.

## Source set

| Key                  | Source                                           | Use in the first pilot                                                        |
| -------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------- |
| `mentors_volunteers` | All Learn-a-thon Mentors & Volunteers (WhatsApp) | Event coordination, ownership, staffing and language coverage.                |
| `volunteers_500`     | 500 volunteers @ Learnathon (WhatsApp)           | Day-one staffing and subgroup decisions.                                      |
| `resident_lounge`    | Resident Lounge (WhatsApp)                       | Creative delivery, public positioning and campaign progress.                  |
| `GitHub`             | LearnAIMTO repository                            | Public product and delivery context.                                          |
| `instagram`          | `@aimto_26`                                      | Monitoring/publication destination only; never infer a post without evidence. |

## Pipeline catalogue and expected outputs

| Pipeline            | Trigger / window                                                                     | Contract           | Expected AIMTO output                                                                                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------ | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Conversation Digest | 15-minute debounce after relevant WhatsApp activity, per group                       | `digest`           | What changed, confirmed facts, unresolved points and why it matters. Example: volunteer recruitment grew but blue-zone ownership is still unresolved.                               |
| Progress Tracker    | 15-minute debounce after a milestone, ownership change, blocker or completion signal | `progress_update`  | Status, owner where known, completed work, blockers/dependencies and next milestone. Example: _AICB lobby poster delivery — in progress; final 16:9 and 9:16 PNG approval remains._ |
| Suggested Actions   | After a confirmed unresolved task is extracted from a group digest                   | `suggested_action` | A proposal only—wording, rationale/evidence, suggested assignee and due point. Example: _Confirm Mandarin, Malay and Tamil coverage at the Monday briefing._                        |
| Decisions           | After explicit agreement or instruction is detected, per group                       | `decision`         | Decision text, active/superseded/reversed lifecycle, rationale and exact evidence. Example: _Keep overall coordination in the main group._                                          |
| Marketing Digest    | Daily scheduled campaign window, plus material campaign events                       | `digest`           | Shareable development, supporting facts and amplification angle. Example: _University challenge leaderboard is live._                                                               |
| Topic Analysis      | Manual question or daily cross-group run                                             | `analysis`         | Question, main finding, supporting signals, uncertainty and practical implication. Example: _Volunteer readiness is strong, but ownership data lags behind headcount._              |

## Delivery order

1. **Progress Tracker**: highest demo coverage (four posts) and a clear, bounded output.
2. **Conversation Digest**: the source-context companion to progress.
3. **Suggested Actions**: reuse the existing group-journal proposal publisher; do not create Todos automatically.
4. **Decisions**: publish only explicit confirmed choices; never infer a decision from a tentative suggestion.
5. **Marketing Digest**: add GitHub context only when it is attached evidence; Instagram remains monitoring-only.
6. **Topic Analysis**: cross-source synthesis last, because it needs the strongest evidence and uncertainty discipline.

## Shared execution rules

- Every accepted run is a Temporal workflow with a stable source/window/module identity.
- A pipeline reloads exact evidence and validates its contract before publication.
- Invalid output is withheld; it never creates a placeholder Hover post.
- Routine progress may accumulate for 15 minutes. Urgent blockers and material decisions publish immediately.
- Suggested Actions remain proposals until a teammate approves them in Hover.
- The pipeline sends only through the Studio-mediated Hover publication path; it never makes the browser or Hover server reach a Clawer VM directly.

## First acceptance slice: Progress Tracker

Given the Mentors & Volunteers and Resident Lounge sources, a successful run
must create a `progress_update` with:

- a concise title such as `Language-support coverage` or `AICB lobby poster delivery`;
- status `in_progress` or `blocked` based only on supported evidence;
- a list of what changed and completed work;
- named blockers only when the source establishes them;
- an explicit next milestone; and
- evidence references to the exact WhatsApp messages used.

The pipeline must withhold output when its evidence cannot support a status or
next milestone. That is preferable to producing a convincing but invented
progress update.
