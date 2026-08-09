# Issue tracker: GitHub

Issues and PRDs for this repository live as GitHub issues. Use the `gh` CLI for
all operations.

## Conventions

- **Create an issue:** `gh issue create --title "..." --body "..."`. Use a
  heredoc for multi-line bodies.
- **Read an issue:** `gh issue view <number> --comments`, including its labels.
- **List issues:** `gh issue list --state open --json number,title,body,labels,comments`
  with appropriate label and state filters.
- **Comment:** `gh issue comment <number> --body "..."`.
- **Apply or remove labels:** `gh issue edit <number> --add-label "..."` or
  `--remove-label "..."`.
- **Close:** `gh issue close <number> --comment "..."`.

Infer the repository from `git remote -v`; `gh` does this automatically when
run inside the clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** Pull requests are not treated as incoming
feature requests by the triage flow.

GitHub shares one number space across issues and pull requests. Resolve an
ambiguous `#42` with `gh pr view 42`, falling back to `gh issue view 42`.

## Skill operations

- When a skill says **publish to the issue tracker**, create a GitHub issue.
- When a skill says **fetch the relevant ticket**, run
  `gh issue view <number> --comments`.

## Wayfinding operations

The map is one issue with child issues as decision tickets.

- Label the map `wayfinder:map`.
- Link child tickets using GitHub sub-issues when available. Otherwise use a
  task list in the map and put `Part of #<map>` in each child.
- Label children by type: `wayfinder:research`, `wayfinder:prototype`,
  `wayfinder:grilling`, or `wayfinder:task`.
- Represent blocking relationships with GitHub's native issue dependencies.
  If unavailable, put `Blocked by: #<n>` at the top of the child issue.
- A ticket is available when it is open, unassigned, and all blockers are
  closed. Claim it with `gh issue edit <n> --add-assignee @me`.
- Resolve it by recording the answer in a comment, closing the child, and
  adding the decision pointer to the map.
