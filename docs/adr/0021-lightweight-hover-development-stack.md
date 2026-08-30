# ADR 0021: Use shared infrastructure with isolated Hover application containers

## Status

Accepted

## Context

The inherited macOS workflow runs Vagrant inside a Colima-backed Docker
container. Every checkout therefore provisions an entire development machine,
including copies of PostgreSQL, Redis, RabbitMQ, and Memcached. That model is
expensive on the team's 4-CPU/8-GiB Colima baseline and prevents three active
workspaces from running comfortably.

Hover needs the reproducibility of a Linux toolchain without duplicating stateful
services or hiding lifecycle behavior behind guest SSH and machine-local
scripts.

## Decision

- `./tools/dev` is the single development interface for people, agents,
  Conductor, and targeted CI.
- macOS keeps one Colima VM. A fixed Compose project runs digest-pinned,
  health-checked PostgreSQL/PGroonga 16, Redis, RabbitMQ, and Memcached services
  on an internal-only network.
- Each worktree runs one native-architecture Ubuntu 24.04 application container
  with its source mounted at `/workspace`. The stable instance identity comes
  from `CONDUCTOR_WORKSPACE_ID`, or otherwise from the absolute worktree path;
  branch names are not identities.
- A PostgreSQL control registry allocates service slots transactionally and can
  reclaim old registrations only when no matching application container is
  running. A workspace receives its own PostgreSQL database, Redis logical
  database, RabbitMQ vhost, Memcached key prefix, and writable volumes.
- Seed databases are keyed by migration and fixture content. Their build claims
  are serialized with a PostgreSQL advisory lock, allowing incompatible branch
  schemas to run concurrently. PGroonga indexes are reindexed immediately after
  cloning because their database-local objects cannot be copied safely with
  PostgreSQL templates.
- The core profile runs Django, Tornado, and webpack/HMR. The full profile adds
  queue workers, scheduled delivery, PGroonga indexing, and uploads using the
  same image and workspace state.
- Dependency volumes are keyed by lockfiles, manifests, provisioning inputs,
  and CPU architecture. Running application containers mount them read-only.
- Development service variables are rejected in production settings.

## Consequences

Three core workspaces can share one infrastructure footprint while retaining
independent application data and ports. `down` preserves workspace state;
`reset --yes` destroys only validated resources belonging to the current
instance. Lockfile or schema changes create new dependency/template generations
without corrupting already-running workspaces.

The inherited `Vagrantfile` remains as a documented fallback until clean setup,
core/full behavior, isolation, reload, test, browser, and performance parity
gates pass on both amd64 and arm64. It is not the canonical Hover onboarding
path and can be retired separately after acceptance.
