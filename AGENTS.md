## Agent skills

## Collaboration

Use subagents whenever independent, bounded parts of a task can proceed in
parallel. Delegate research, codebase exploration, test planning, and isolated
implementation or review work to accelerate delivery; keep tightly coupled or
trivial work local when delegation would add more coordination than value.

## CI and testing

Use the repository-owned development environment for CI-style checks. Run
frontend lint, Node tests, backend lint, backend tests, and browser tests with
`./tools/dev exec -- <command>` so each worktree uses its isolated Hover data.
Do not provision another Vagrant guest or Docker stack for a worktree.

During development, run lint against the files changed by the current task for
fast feedback, and use the same task-scoped lint for final verification. Do not
default to a full-repository lint when the repository's unrelated baseline is
already known; run it only when the user or the task explicitly requires it. If
a broader run reports failures only in files outside the current task, record
them as existing baseline failures; do not modify user-owned or unrelated work
merely to make the command pass, and do not repeatedly rerun the same unchanged
failing scan.

### Apple Silicon browser tests

In an Apple Silicon workspace, Puppeteer's downloaded Linux Chrome binary may
fail before test code runs because it requires the unavailable x86_64 loader
`/lib64/ld-linux-x86-64.so.2`. Use the ARM-native Firefox target in the same
isolated Hover development environment:

```console
./tools/dev exec -- tools/test-js-with-puppeteer --firefox <test-name>
```

This is a real Puppeteer browser run. Keep the required viewport screenshots
and inspect the original PNGs; do not replace the browser audit with fixtures
or conceptual images.

Puppeteer test databases are rebuilt between runs, but the shared memcached
service can retain entries under Puppeteer's default fixed prefix. If a repeated
run fails during login with a stale entity such as `Unknown user_id`, give that
run a workspace/task-specific cache prefix instead of flushing shared
memcached, for example:

```console
./tools/dev exec -- env HOVER_DEV_CACHE_PREFIX=<unique-task-prefix>: tools/test-js-with-puppeteer --firefox <test-name>
```

Never flush the shared memcached service to repair one workspace; doing so can
disrupt other Conductor workspaces.

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

### UI proposal approval

For every task that involves UI changes, use the `imagegen` skill to generate a
visual proposal image and give it to the user for approval before implementing
the production UI. The generated image is the primary design-approval artifact.
Use the `gpt-taste` and `design-taste-frontend` skills only as supporting design
critique and prompt-shaping guidance. Where their guidance conflicts with
Hover's dense product UI, dashboards, data tables, or multi-step flows, preserve
Hover's existing design system and product interaction patterns.

Whenever possible, provide imagegen with current real Hover screenshots as
references so the proposal preserves Hover's components, tokens, typography,
density, and layout. Do not begin production UI implementation until the user
approves the generated proposal image. After implementation, validate every
required state in the real Hover browser at the required viewports and give the
original-size screenshots to the user. The imagegen proposal does not replace
the final real-browser screenshot review.

### Issue tracker

Issues and PRDs live in GitHub Issues. Use the `gh` CLI. See
`docs/agents/issue-tracker.md`.

### Triage labels

Use the canonical `needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, and `wontfix` labels. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain glossary in `CONTEXT.md` with architectural
decisions under `docs/adr/`. See `docs/agents/domain.md`.
