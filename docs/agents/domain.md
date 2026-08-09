# Domain docs

These rules define how engineering skills consume this repository's domain
documentation.

## Before exploring

Read `CONTEXT.md` at the repository root and relevant decisions under
`docs/adr/`. If these paths do not exist, proceed silently. Domain-modeling
flows create them lazily when terminology or a hard-to-reverse decision is
actually resolved.

## Layout

This repository uses a single domain context:

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── application source
```

`CONTEXT.md` is a glossary, not a specification or implementation plan.

## Use the glossary vocabulary

Use canonical terms from `CONTEXT.md` in issue titles, tests, implementation
plans, and product discussion. Do not drift to synonyms the glossary rejects.

If a required concept is missing, reconsider whether new terminology is
necessary or resolve the gap through domain modeling.

## Flag ADR conflicts

If proposed work contradicts an existing ADR, surface the conflict explicitly
instead of silently overriding the earlier decision.
