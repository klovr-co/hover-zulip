# Hover product truth

Hover turns authorized activity from external conversations and systems into a
private, source-backed organizational feed. It helps a confirmed group notice
meaningful change, review disputed detail, and turn explicit decisions into
durable work without copying raw provider data into the product.

## Product laws

- A Space is private during Setup. Launch creates its native feed and exposes it
  only to the exact cohort of confirmed Space members.
- Connected Accounts grant discovery authority; they never expose credentials or
  provider identifiers to the browser.
- Sources are provider-neutral identities. Attachments keep an explicit,
  immutable, bounded history window; Hover never defaults to all history.
- AI Modules are pinned, versioned installations with explicit Source bindings
  and structured triggers. Generated output always retains Source evidence.
- Membership suggestions grant no access. A Space administrator must confirm or
  remove every suggestion before launch.
- Reviews, Suggested Actions, and Todos are Hover-owned, auditable records. AI
  prose is guidance until a teammate makes an explicit state transition.
- Search and personal/shared projections re-check authorization and do not create
  copied feed records or hidden acknowledgement state.

## Launch contract

The Setup workbench shows the preflight facts available in the sanitized Space
projection: an active Source, at least one confirmed teammate, no pending
membership suggestions, and no paused Module bindings. Passing those checks
enables a final server-owned launch check. The server remains authoritative for
transactional validity, eligibility, Source capability, and name-collision
checks; a failed final check must surface its specific safe error and keep Setup
interactive.

## Experience boundary

The production interface is the Cofounder component system documented in
`DESIGN.md`. Product truth belongs here and domain language belongs in
`CONTEXT.md`; presentation tokens, component anatomy, and visual verification do
not belong in this document.
