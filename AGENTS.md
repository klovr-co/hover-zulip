## Agent skills

## Product direction

Hover is the product and the only supported user experience. This repository
is transitioning its inherited Zulip implementation into Hover; treat Zulip as
the legacy technical foundation, not as a presentation mode that must remain
available.

- Build new UI and UX as unconditional Hover behavior. Do not introduce or
  preserve `hover-enabled` feature gates merely to keep an ordinary Zulip UI.
- Prefer one canonical Hover implementation over parallel Hover and Zulip
  variants.
- Preserve inherited Zulip DOM, behavior, and infrastructure only where Hover
  still depends on them during the migration. Do not remove those foundations
  without tracing their consumers.

### Issue tracker

Issues and PRDs live in GitHub Issues. Use the `gh` CLI. See
`docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, and `wontfix` labels. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain glossary in `CONTEXT.md` with architectural
decisions under `docs/adr/`. See `docs/agents/domain.md`.
