# Hover development environment

The canonical Hover development workflow uses one Colima virtual machine, one
shared set of infrastructure services, and one isolated application container
per Git worktree. It replaces Vagrant-over-Colima for normal Hover work while
keeping the inherited Vagrant path available during the parity rollout.

## Requirements

On macOS, install Colima with the Docker runtime and Docker Compose v2. Hover's
three-workspace baseline is 4 CPUs and 8 GiB of memory. Colima must use VirtioFS
and forward file notifications; the repository checks these settings but never
changes them. Linux can use the same commands with a native Docker daemon.

Before setup, validate the host without changing it:

```console
$ ./tools/dev doctor
```

If `doctor` reports a Colima configuration problem, update Colima deliberately
outside this script and rerun the check. Existing Colima data is not recreated
automatically.

## Set up and run Hover

Prepare this worktree and its isolated data:

```console
$ ./tools/dev setup
```

Setup builds the native Ubuntu 24.04 application image when its dependency
inputs change, starts the shared PostgreSQL/PGroonga, Redis, RabbitMQ, and
Memcached services, and clones a migration-keyed seed database. Repeating setup
is safe.

Start the default core profile in the foreground:

```console
$ ./tools/dev up
```

Core runs Django, Tornado, webpack/HMR, and the reverse proxy. The full profile
adds queue processing, scheduled delivery, PGroonga indexing, and uploads:

```console
$ ./tools/dev up --profile full
```

The host port is chosen in this order: `--port`, `CONDUCTOR_PORT`,
`HOVER_DEV_PORT`, then `9991`. A collision is an error; Hover never stops a
different worktree to take its port.

## Tests and maintenance

Run repository commands in this worktree's application container:

```console
$ ./tools/dev exec -- ./tools/lint --groups=frontend --skip=gitlint
$ ./tools/dev exec -- ./tools/test-js-with-node web/tests/hover.test.cjs
$ ./tools/dev exec -- ./tools/test-backend zerver.tests.test_home
$ ./tools/dev exec -- ./manage.py shell
```

Inspect logs or stop only this application while preserving its data:

```console
$ ./tools/dev logs
$ ./tools/dev down
```

Reset is deliberately explicit. It drops only this worktree's database, flushes
only its Redis logical database, recreates only its RabbitMQ vhost, rotates its
Memcached prefix state, and removes only its writable volumes:

```console
$ ./tools/dev reset --yes
```

Shared infrastructure can be stopped only when no Hover application containers
are running:

```console
$ ./tools/dev infra stop
```

Dependency volumes are read-only in running application containers and keyed by
the relevant Python/Node lockfiles, manifests, architecture, and provisioning
inputs. Writable `var`, upload, and generated-state volumes are scoped to the
stable worktree instance ID. Local service credentials live under the user's
state directory and are never committed or exposed on host ports.

## Conductor

Repository Conductor settings run setup automatically and allocate a distinct
port to each workspace. The `dev`, `dev-full`, `logs`, and `down` actions call
the same `./tools/dev` interface used by humans and CI.

After this configuration reaches the default branch, remove any machine-local
`.conductor/settings.local.toml` that enables Spotlight or overrides these
scripts, then archive the corresponding machine-local Hover scripts. Local
settings override repository settings, so leaving the old override in place
will intentionally keep the legacy workflow active on that machine.

## Legacy Vagrant fallback

`Vagrantfile` and the inherited Zulip Vagrant documentation remain available
while core and full-profile parity is being accepted. They are a fallback, not
the supported Hover onboarding path. Do not run Vagrant and `./tools/dev up` on
the same host port.
