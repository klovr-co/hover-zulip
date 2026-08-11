# AIMTO Events Hover pilot rollout

This runbook configures AIMTO Events through normal reusable Hover records. It
does not deploy code, call Studio, change GitHub/Apify webhooks, or write Reviews
or Todos to Monday. The only AIMTO-specific input is an uncommitted private JSON
file.

## Private values still required

Copy `docs/examples/hover-pilot-v1.example.json` to a gitignored path ending in
`.private.json`, normally `.context/aimto-pilot.private.json`. Replace every
sanitized value with a reviewed value from the deployment inventory:

- organization string ID and active organization-administrator email;
- approved Connected Account UUIDs and the incoming GitHub/Apify bot emails;
- the three permitted WhatsApp Source references and their exact bounded UTC
  history starts/timezones;
- GitHub and Apify Source references, HTTPS links, allowed actors,
  repository(s), and event types;
- internal teammate emails, Contributor/Subscriber roles, Space Administrator
  responsibility, pilot-cohort membership, and verified opaque participant and
  observation references.

The three permitted WhatsApp Groups are the reviewed AIMTO inventory entries
represented in the approved demo: All Learn-a-thon Mentors & Volunteers,
Resident Lounge, and 500 volunteers @ Learnathon. Do not copy their opaque
references or raw messages into this repository.

## Validate and review

Dry-run is the default and performs no writes:

```bash
./manage.py configure_hover_pilot \
  --realm=<realm> \
  --config=.context/aimto-pilot.private.json \
  --report=.context/aimto-pilot-report.json
```

Review the report with the pilot owner. It must show three WhatsApp Sources,
two reviewed native provenance routes, six enabled Modules, Signal Monitor off,
zero Monday writeback, and all six acceptance gates. The command rejects extra
schema fields, unknown or forbidden Modules, missing mappings, external guests,
unreviewed routes, unsafe URLs, implicit history windows, and route bot drift.

Also verify the declared actor/repository/event allowlists in the GitHub and
Apify webhook configuration itself. Hover reports those controls but does not
duplicate an unenforced provider policy in its database; see ADR 0019.

## Apply deliberately

Apply accepts only a schema-valid config whose metadata has
`private_config: true`, whose filename ends in `.private.json`, and whose exact
confirmation token is supplied:

```bash
./manage.py configure_hover_pilot \
  --realm=<realm> \
  --config=.context/aimto-pilot.private.json \
  --apply \
  --confirm=<realm>:aimto-events \
  --report=.context/aimto-pilot-applied-report.json
```

Re-running the same command is safe. It reuses normal Category, Space,
Connected Account, grant, Source, attachment, teammate mapping, membership,
Module installation, and Integration Route records. It refuses history-window
changes, detached Sources, changed immutable Module policies, unreviewed setup
members or administrators, extra active grants/selectors/attachments/Modules/
routes, or launched subscription drift so those changes receive a new human
review.

Conversation Digest, Progress Tracker, Suggested Actions (the Todo-producing
Module), Decisions (Decision Capture), Marketing Digest, and Topic Analysis are
installed. Signal Monitor is present in the reusable catalog but not installed.
Email, Weekly Roundup, AI Slides, and Topics You Follow are denied. Morning
Daily Brief and End-of-Day Roundup become available only to reviewed cohort
members who have a verified `SourceParticipantBinding` and confirmed Space
membership.

## Shadow-mode acceptance checklist

Expansion to another Space is blocked until the report records `passed` for:

- **Access:** exact internal cohort, roles, administrators, grants, Sources,
  native subscriptions, and absence of external guests.
- **Duplication:** one generated update per immutable publication and no
  duplicate native provenance or Todo on replay.
- **Evidence:** exact permission-checked evidence opens from generated updates;
  raw Source records and opaque references remain hidden.
- **Audit history:** Reviews, Suggested Action transitions, Todo Events, and
  source detach/revocation history remain append-only and attributable.
- **Notifications:** only native configured Review and Todo notifications reach
  eligible confirmed members.
- **Voluntary use:** pilot users can ignore Hover while the current workflow
  continues; no Hover Review or Todo is written back to Monday.

## Sanitized development smoke path

The config declares a non-production fixture key and explicitly states that it
contains no real Source content. Run the source-backed path with the in-memory
adapter and sanitized test evidence:

```bash
./tools/test-backend \
  zerver.tests.test_hover_publication_sync.HoverPublicationSyncTest.test_all_six_outputs_materialize_once_and_replay_advances_cursor \
  zerver.tests.test_hover_publication_sync.HoverPublicationSyncTest.test_material_dispute_creates_one_native_targeted_request_and_resolves \
  zerver.tests.test_hover_suggested_actions.HoverSuggestedActionTest.test_approval_is_atomic_idempotent_and_preserves_publication \
  zerver.tests.test_hover_awareness.HoverAwarenessTest.test_linked_development_projects_latest_reviewed_state_and_native_read_state \
  zerver.tests.test_hover_personal_editions.HoverPersonalEditionsTest.test_ingests_and_projects_only_native_update_links_without_creating_todos
```

This proves the ordered development path from sanitized evidence to generated
update, Review, confirmed Todo, Home awareness, and permission-filtered personal
edition without contacting or mutating live Sources, Studio, GitHub, Apify, or
Monday.
