# Workstream F - Mac and Cloudflare Deployment

> **Document type:** Implementation plan
> **Status:** Target
> **Audience:** Maintainers and operators
> **Last reviewed:** 2026-06-22

## Objective

Deploy one FastAPI worker and four built SPAs on the target Mac behind one
Cloudflare named tunnel, with same-origin clients, verified data migration,
readiness gates, rollback, and a deliberate retirement of the legacy remote
deployment.

## Starting point

On 2026-06-22 the four target hostnames were not deployed, the legacy backend
returned maintenance-mode HTTP 503, and the existing client still contained
localhost origin fallbacks. `/health` was not a reliable readiness response, and
startup performed mutation that should be explicit release work.

## Dependencies and boundaries

- Deployment tooling can be developed after workstream A, but public cutover waits
  for the game smoke gates in C-E.
- Schema release work depends on B's migration and SQLite invariants.
- The target operating model is defined by
  [ADR 0004](../decisions/0004-same-origin-cloudflare-deployment.md) and the
  [startup-services runbook](../development/persistent-startup-services.md).
- Exactly one Uvicorn worker owns the production SQLite database.

## Repository anchors and gotchas (verified 2026-06-22)

- **`/health` is the readiness bug to fix (F2).** `backend/routers/health.py:25-28`
  does `return {"status": "error", ...}, 503` — a `(dict, int)` tuple, which FastAPI
  serializes as a **200 OK body**, not a 503. It also opens a DB connection on every
  call. A sibling `/status` endpoint exists; `/livez` and `/readyz` do not.
- **Exact same-origin fallbacks to remove (F3).**
  `frontend/crowdcraft/src/api/client.ts:74`
  (`import.meta.env.VITE_API_URL || 'http://localhost:8000'`);
  `src/hooks/useWebSocket.ts:65` (`|| http://${window.location.hostname}:8000`).
  The same file's `client.ts:76` prefix regex omits `ir` (see workstream E), so
  the same-origin rewrite must cover all four game prefixes.
- **Startup mutation to relocate (F2).** `backend/main.py` starts hourly token/guest
  cleanup and Party maintenance on startup (see
  [`docs/CLEANUP_SCRIPTS.md`](../CLEANUP_SCRIPTS.md)); these are the destructive/slow
  startup mutations to move into explicit idempotent release commands.
- **Backup tooling exists.** `scripts/backup_db.py` is present for F1b; the
  legacy deployment scripts have been removed.
- Implements [ADR 0004](../decisions/0004-same-origin-cloudflare-deployment.md)
  (already linked) and [ADR 0005](../decisions/0005-sqlite-concurrency-boundary.md)
  (one worker).

## Implementation contract

### Problem

The current application cannot be safely cut over by changing DNS. The backend has
no trustworthy readiness gate, performs database mutation during startup, accepts
client-selected game scope in shared auth paths, and does not serve the four SPAs.
The clients still know legacy backend origins. The existing backup and deployment
scripts are provider-specific and do not supply a reversible SQLite release.

### Expected behavior

One production checkout on the target Mac builds and serves all four games through
one FastAPI process bound only to `127.0.0.1:8000`. A validated exact host selects
the only allowed game API, auth scope, WebSocket scope, and SPA. One named
Cloudflare tunnel publishes the four hosts. A release is a guarded state machine:
preflight, verify, stage, quiesce, back up, migrate, publish, start, prove, and
record. A failed state stops and produces one bounded rollback command.

### Acceptance criteria

- Production refuses to start with an unknown host map, default secret, repository
  database, missing static release, unsafe cookie/origin settings, or more than one
  worker.
- `/livez` proves only that the process event loop is responding. `/readyz` proves
  that the exact running release is safe to receive traffic.
- Host scope is derived once at the outer ASGI boundary and is reused by auth,
  REST, WebSocket, online-user tracking, and SPA dispatch. Query parameters and
  JWT claims cannot change the host-selected game.
- The release tool never migrates before producing and verifying a restorable
  pre-migration backup.
- Static publication and release metadata publication are atomic. Database
  replacement uses SQLite's backup API or an offline restore, never a raw copy of
  a live main file.
- Rollback restores the previous code revision, static release, and database
  backup as one recorded operation.
- Local exact-`Host` tests and public-host browser tests cover all four games,
  cross-game rejection, auth cookies, WebSockets, deep links, and restart recovery.

### Invariants that remain true

- Exactly one Uvicorn worker owns the production SQLite database.
- SQLite constraints, compare-and-swap updates, and idempotency keys remain the
  lifecycle correctness boundary; deployment serialization is not a replacement.
- Optional AI providers may degrade game fill/hint behavior only where C-E define
  that behavior. They do not make the core service unready.
- No secret value, signed Heroku export URL, player data, token, or database
  contents enters Git, process arguments, release records, or logs.
- Startup wiring does not seed, clean, repair, pay, refund, or advance gameplay.
- Heroku/Vercel remain available until the soak decision and rollback-window
  expiry are explicitly recorded.

### Non-goals for this workstream

- Changing game rules, payout behavior, or lifecycle ownership.
- Supporting a second Uvicorn worker or a second writer process.
- Building a general container/orchestration platform.
- Making Cloudflare Access part of player authentication.
- Treating monitoring as a substitute for deterministic and smoke gates.

## Target topology and filesystem contract

Use a dedicated clean production checkout. Do not deploy from an agent worktree or
a developer checkout containing unrelated changes.

```text
quipflip.crowdcraftlabs.com
mememint.crowdcraftlabs.com
initialreaction.crowdcraftlabs.com
thinklink.crowdcraftlabs.com
        |
        v
Cloudflare named tunnel: crowdcraft
        |
        v
127.0.0.1:8000
        |
        +-- exact-host ASGI boundary
        +-- FastAPI REST and WebSocket routers
        +-- host-specific SPA fallback
        |
        v
~/Library/Application Support/Crowdcraft/crowdcraft.sqlite3
```

Proposed production paths are centralized in one non-secret
`CROWDCRAFT_RUNTIME_ROOT` setting, defaulting to
`~/Library/Application Support/Crowdcraft`:

| Purpose | Path |
| --- | --- |
| Dedicated checkout | `/Users/tfish/quipflip` |
| Database | `$CROWDCRAFT_RUNTIME_ROOT/crowdcraft.sqlite3` |
| SQLite WAL/SHM | Adjacent to the database; never copied independently |
| Static release staging | `$CROWDCRAFT_RUNTIME_ROOT/static/staging/<release-id>` |
| Immutable static releases | `$CROWDCRAFT_RUNTIME_ROOT/static/releases/<release-id>` |
| Active static pointer | `$CROWDCRAFT_RUNTIME_ROOT/static/current` |
| Database backups | `$CROWDCRAFT_RUNTIME_ROOT/backups/<backup-id>/` |
| Release records | `$CROWDCRAFT_RUNTIME_ROOT/releases/<release-id>.json` |
| Release lock | `$CROWDCRAFT_RUNTIME_ROOT/locks/release.lock` |
| Logs | `~/Library/Logs/Crowdcraft/` |
| Server LaunchAgent | `~/Library/LaunchAgents/com.crowdcraft.server.plist` |
| Tunnel config | `~/.cloudflared/crowdcraft.yml` |

Every runtime directory is created with owner-only write access. Database, backup,
release-record, and Keychain access are limited to the login user that owns the
LaunchAgents. The release record contains identifiers and hashes, never environment
values or command output.

## Proposed code and operations layout

The implementation should converge on these files. Names may change during a
reviewable slice, but responsibilities must not be merged back into `backend/main.py`.

```text
backend/
  application.py                    # create_app(), middleware/router ordering
  runtime/
    config.py                       # validated production-only runtime settings
    host_scope.py                   # immutable host -> game/prefix/static mapping
    logging.py                      # durable rotated, redacted logging config
    readiness.py                    # bounded readiness checks and result schema
  middleware/
    host_scope.py                   # HTTP + WebSocket exact-host ASGI boundary
  routers/
    health.py                       # /livez, /readyz, legacy /health transition
    static.py                       # API-first host-specific SPA fallback
  commands/
    release.py                      # idempotent content/release commands
scripts/
  ops/
    crowdcraft_ops.py               # operator CLI entry point
    sqlite_backup.py                # create, verify, restore
    migrate_legacy_data.py          # authenticated PG export/import/reconcile
    release.py                      # guarded deployment state machine
    rollback.py                     # recorded rollback state machine
    smoke.py                        # local/public host matrix orchestration
  run-production-server.py          # Keychain loader + one-worker exec
  install-launch-agents.py          # render/lint/install non-secret plists
  templates/
    com.crowdcraft.server.plist
    com.crowdcraft.tunnel.plist
    crowdcraft.yml
frontend/crowdcraft/src/
  api/origins.ts                    # pure HTTP/WS same-origin derivation
  api/origins.test.ts
tests/
  deployment/
    test_health.py
    test_runtime_config.py
    test_host_scope.py
    test_static_dispatch.py
    test_release_commands.py
    test_sqlite_backup.py
    test_legacy_migration.py
docs/operations/
  deployment-inventory.md           # F1 decisions and redacted inventory
  data-migration.md                 # rehearsal and reconciliation evidence
  release-and-rollback.md           # exact operator procedure
  cutover-checklist.md              # dated F6-F8 evidence
```

`backend/main.py` becomes a compatibility entry point that imports the app created
by `backend.application`. It must not own logging setup, seed data, or contain
release behavior.

## Application implementation

### Production runtime configuration

Add explicit settings instead of inferring production behavior from broad fallback
logic:

```text
ENVIRONMENT=production
CROWDCRAFT_RUNTIME_ROOT=...
CROWDCRAFT_STATIC_ROOT=.../static/current
CROWDCRAFT_DATABASE_PATH=.../crowdcraft.sqlite3
CROWDCRAFT_RELEASE_ID=...
CROWDCRAFT_EXPECTED_REVISION=...
CROWDCRAFT_LOG_DIR=...
CROWDCRAFT_TRUST_PROXY=true
CROWDCRAFT_WORKERS=1
```

The host map is code-defined from the accepted ADR, not a free-form client or
request value:

| Host | Game | API prefix | Static directory |
| --- | --- | --- | --- |
| `quipflip.crowdcraftlabs.com` | `qf` | `/qf` | `qf/` |
| `mememint.crowdcraftlabs.com` | `mm` | `/mm` | `mm/` |
| `initialreaction.crowdcraftlabs.com` | `ir` | `/ir` | `ir/` |
| `thinklink.crowdcraftlabs.com` | `tl` | `/tl` | `tl/` |

Production validation runs before the engine or app is created and fails closed
when:

- `SECRET_KEY` is empty, the development default, or below the accepted entropy
  policy;
- the database resolves inside the repository, is not SQLite, or is not an
  absolute path;
- the active static root is absent, writable by other users, or lacks all four
  release manifests and `index.html` files;
- workers is not exactly `1`;
- a trusted host contains a scheme, path, port, wildcard, duplicate, or unknown
  game;
- credentialed CORS is combined with a wildcard origin;
- production cookies would not be `Secure`, `HttpOnly`, host-only, and
  `SameSite=Lax`;
- a required local dependency such as the phrase dictionary is absent;
- `CROWDCRAFT_RELEASE_ID` or expected Alembic revision is missing.

Development retains explicit localhost behavior, but production has no automatic
database, origin, secret, or host fallback. Configuration errors must redact values
and name only the invalid setting.

### Exact-host ASGI boundary

Implement one outer ASGI middleware for both `http` and `websocket` scopes. It:

1. Parses the `Host` header with Starlette's trusted host semantics, normalizing
   case and rejecting malformed or duplicate values.
2. Resolves the host through the immutable host map.
3. Stores a typed `HostScope(game, api_prefix, static_dir, hostname)` in
   `scope["state"]`.
4. Rejects unmatched HTTP hosts before router execution and closes unmatched
   WebSockets before `accept`.
5. Rejects a path beginning with another game's prefix.
6. Permits only the selected game prefix and this shared route allowlist:
   `/livez`, `/readyz`, `/status`, and `/auth/*`.
7. Adds a bounded security event containing the rejected host hash/category and
   path class, not cookies, query strings, tokens, or request bodies.

Use `404` for a valid host requesting another game's API so the response does not
advertise the other surface. Use a non-success response for an unknown HTTP host
and WebSocket close code `1008` before acceptance. Disable `/docs`, `/redoc`, and
`/openapi.json` in production unless a separate authenticated operator decision
enables them.

Shared auth routes receive `HostScope` as a dependency. Remove `game_type` as an
authoritative query parameter. During one release-only compatibility window, an
exactly matching hint may be accepted but ignored; a mismatch is rejected and the
compatibility path has a named removal release. JWT game claims are checked against
host scope, never used to select it.

Online-user tracking also consumes host scope. It no longer defaults an unprefixed
path to QF. WebSocket token issuance includes the host-selected game and audience;
notification, presence, and Party handlers verify both before accepting a socket.
Canonical realtime paths are game-prefixed:

| Channel | Canonical path |
| --- | --- |
| Notifications | `/<game>/notifications/ws` |
| Presence | `/<game>/users/online/ws` |
| QF Party | `/qf/party/<session-id>/ws` |

Mount or refactor the current unprefixed notification router under each game prefix
and remove the unprefixed production route after clients move. Update every game's
notification configuration, including IR's separate context, so a valid host never
needs a globally shared WebSocket path.

### API-first static dispatch

Register every REST and WebSocket route before a final `GET`/`HEAD` catch-all.
The fallback:

- reads the validated host scope;
- rejects reserved API, auth, health, and WebSocket paths instead of serving HTML;
- safely resolves files beneath that host's static directory with no traversal or
  symlink escape;
- serves an existing asset when found;
- serves that host's `index.html` for a client-side deep link only when the request
  accepts HTML;
- never serves one game's file from another host.

Response policy:

| Response | Cache policy |
| --- | --- |
| Hashed Vite asset | `public, max-age=31536000, immutable` |
| `index.html` | `no-cache` with ETag or last-modified validation |
| Manifest/service worker | `no-cache` |
| API/auth/health | `no-store` where responses contain state |

Add `X-Content-Type-Options: nosniff`, a reviewed `Referrer-Policy`, frame
protection, and a tested Content Security Policy. Do not add a CSP from memory:
generate it from the built output and prove all four games work without console
violations.

### Same-origin frontend origins

Move URL construction into pure functions:

```ts
resolveHttpOrigin(override, window.location)
resolveWebSocketOrigin(override, window.location)
resolveGameApiBase(game, override, window.location)
resolveWebSocketUrl(path, token, override, window.location)
```

Rules:

- `undefined`, absent, or whitespace-only production overrides select
  `window.location.origin`;
- an explicit override is parsed with `URL`, stripped of a trailing slash, and
  rejected if it contains credentials, query, or fragment;
- HTTP maps to `ws`, HTTPS maps to `wss`;
- the root-prefix regex covers `qf`, `mm`, `ir`, and `tl`;
- paths are joined once, without duplicate or missing prefixes;
- no code contains the Heroku hostname or a production localhost fallback.

Use these helpers from the shared Axios clients, the shared WebSocket hook, and the
IR-specific notification client. Tests cover all four games, IPv6/ports in
development, explicit overrides, HTTPS/WSS, path normalization, and invalid
overrides.

### Liveness and readiness

`GET /livez` returns a small explicit schema and never touches the database,
filesystem, AI providers, queues, or migration state:

```json
{"status":"alive","version":"...","release_id":"..."}
```

`GET /readyz` runs bounded checks through a readiness service. It returns `200` only
when all mandatory checks pass and an explicit `503 JSONResponse` otherwise.

Mandatory checks:

1. production configuration was validated;
2. one database connection can execute `SELECT 1`;
3. that connection reports `foreign_keys=1`, `journal_mode=wal`,
   `busy_timeout>=5000`, and `synchronous=2` (`FULL`);
4. the current `alembic_version` set exactly matches Alembic heads and
   `CROWDCRAFT_EXPECTED_REVISION`;
5. all four active static release manifests match `CROWDCRAFT_RELEASE_ID` and their
   `index.html` files are readable;
6. the database parent and backup destination have the required permissions and a
   configured minimum free-space margin;
7. required local runtime data such as the phrase dictionary is readable;
8. every mandatory scheduler/discovery task reached its started state without
   performing a mutation during the check.

Optional AI credentials and provider reachability are reported only in a separate
operator status surface. They do not affect readiness when degraded behavior is
defined.

Each check has a short timeout, stable machine-readable name, and redacted
diagnostic code. A two-second success cache and single in-flight evaluation prevent
health polling from opening an unbounded number of connections. Failures are not
cached longer than needed to recover. The public body excludes paths, SQL, exception
strings, environment values, and provider details; full bounded diagnostics go to
the rotated operator log.

Keep `/health` temporarily as a deprecated alias with correct status semantics, or
remove it after every active monitor has moved. It must never retain the current
tuple-return bug.

### Startup and release commands

The FastAPI lifespan may:

- initialize read-only in-process services;
- validate that required local resources are loaded;
- start stale-safe due-work discovery loops already made safe by B-E; and
- cancel those loops on shutdown.

It may not seed prompts, create quests, import MemeMint rows, delete ThinkLink
prompts, clean tokens/guests, repair rows, or run migrations.

Move current startup mutation behind idempotent operator commands:

```text
crowdcraft-ops release validate-config
crowdcraft-ops release sync-content --dry-run
crowdcraft-ops release sync-content --apply --release-id <id>
crowdcraft-ops maintenance cleanup-retention --dry-run
crowdcraft-ops maintenance cleanup-retention --apply --command-id <id>
```

`sync-content` owns QF prompt synchronization, starter-quest backfill, MemeMint
image/caption import, and ThinkLink prompt/answer synchronization. It reports counts
before applying, uses a release-scoped idempotency key, and never deletes content
unless the command contract explicitly names and previews that deletion.
Lifecycle-sensitive Party maintenance remains a due-row scheduler that calls the
owning commands from D; it is not implemented as a deployment cleanup.

## SQLite, backup, and legacy-data implementation

### Production SQLite engine

Configure pragmas through SQLAlchemy connection events so every connection,
including readiness and command connections, receives:

```sql
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=FULL;
```

Set `journal_mode=WAL` during controlled database initialization/release and verify
it on every readiness check. Do not attempt to set persistent journal mode during
each request checkout. Production URL normalization must not add PostgreSQL SSL
arguments to SQLite.

### Backup artifact

Replace `scripts/backup_db.py` with an operations tool that has explicit
subcommands:

```text
sqlite-backup create --source <path> --destination <backup-dir>
sqlite-backup verify --backup <backup-dir>
sqlite-backup restore --backup <backup-dir> --destination <path>
```

`create` uses Python's SQLite online backup API, even when the server is stopped,
then runs `quick_check`, `integrity_check`, and `foreign_key_check` against the
backup. It records:

- backup ID and UTC timestamps;
- source release ID and Git SHA;
- Alembic revision set;
- database page count and size;
- SHA-256 of the closed backup file;
- check results and tool version.

The manifest contains no row data. `verify` recomputes the hash and checks.
`restore` requires the server to be quiesced, restores to a sibling temporary file,
checks it, preserves the failed/current database under an incident identifier, then
uses `os.replace` for atomic publication. It refuses to overwrite a database
without an explicit recorded rollback/recovery operation.

Retention is policy, not an implicit deletion in the backup command. F1 records the
number of daily/weekly backups, minimum free space, off-host copy destination,
encryption requirement, and named restore owner. A prune command defaults to
dry-run and never removes the last pre-migration or active-soak backup.

### Heroku/PostgreSQL migration

The current generic model-copy backup script is not sufficient evidence: it can
omit models, inserts alphabetically rather than by dependency, and does not retain
source revision/reconciliation metadata.

Implement the migration as a rehearsal-friendly pipeline:

1. Capture an authenticated Heroku Postgres backup and download it through a tool
   that keeps the signed URL out of shell history, process arguments, and logs.
2. Hash and store the raw private export outside the repository with owner-only
   permissions.
3. Record Heroku app/database identifiers, source Alembic revision, PostgreSQL
   version, export timestamp, and row counts without credentials or player data.
4. Restore the export into an isolated local PostgreSQL rehearsal database. Never
   point Alembic experimentation at the Heroku database.
5. Upgrade the rehearsal PostgreSQL database to the approved compatibility
   revision if required by the migration contract.
6. Create a new SQLite database at the corresponding pre-upgrade revision.
7. Copy tables in SQLAlchemy metadata dependency order in one controlled import,
   with explicit type adapters and deferred foreign-key checking. Do not discover
   the source solely from whichever models happened to be imported.
8. Run `foreign_key_check`, lifecycle/ledger reconciliation, and per-table counts.
9. Run the complete SQLite Alembic chain to head.
10. Repeat reconciliation, create a verified backup, restore it to a second path,
    and boot the app against the restored copy for read-only checks.

Reconciliation is a versioned query set under `scripts/ops/reconciliation/` and
must include:

- per-table source/target counts with an explicit allowlist for intentional
  transforms;
- orphan counts for every foreign key;
- active lifecycle status counts by game;
- duplicate active assignment/vote/result checks from B-E;
- wallet/vault totals and ledger sums by game;
- duplicate ledger idempotency keys;
- finalized-object payout/refund counts;
- refresh-token and guest-account counts;
- min/max timestamps and identifier preservation samples.

The migration emits a redacted JSON report with counts and pass/fail assertions.
Any unexplained difference blocks cutover. Reverse migration is not a rollback
strategy; rollback returns DNS to the legacy deployment or restores the recorded
pre-migration SQLite backup.

## Mac service and secret implementation

### Keychain wrapper

`scripts/run-production-server.py` is the only launchd server entry point. The
plist contains non-secret paths, release ID, hostnames, and Keychain item names.
The wrapper reads secret values with `/usr/bin/security find-generic-password`,
validates only length/presence, exports them to the child environment, clears local
references, then executes the absolute production
`/Users/tfish/quipflip/.venv/bin/uvicorn`.

Use one Keychain service such as `com.crowdcraft.production` with separate accounts
for `SECRET_KEY`, `OPENAI_API_KEY`, and `GEMINI_API_KEY`. The signing secret is
mandatory. Provider secrets are loaded only when that provider is enabled. There is
no plaintext fallback in production.

The wrapper executes exactly:

```text
.venv/bin/uvicorn backend.main:app
  --host 127.0.0.1
  --port 8000
  --workers 1
  --proxy-headers
  --forwarded-allow-ips 127.0.0.1
```

Cloudflare headers are accepted only from the loopback tunnel origin. Application
security never trusts `X-Forwarded-Host` to select game scope; the original
validated HTTP `Host` header does that. Tests prove a forged forwarded host cannot
change scope.

### LaunchAgents and logging

Commit templates, not machine-specific installed plist files. The installer:

- resolves absolute paths for the production checkout, Python, Uvicorn, and
  `cloudflared`;
- rejects a worktree or dirty checkout;
- renders only non-secret values;
- runs `plutil -lint`;
- installs with owner-only write permissions;
- bootstraps under `gui/$(id -u)`;
- prints exact status commands without values from the environment.

`com.crowdcraft.server` uses `RunAtLoad` and `KeepAlive` and points to the wrapper.
`com.crowdcraft.tunnel` invokes the absolute `cloudflared` binary with
`--config ~/.cloudflared/crowdcraft.yml --no-autoupdate run`.

Application, API, SQL, launcher, release, and tunnel logs go under
`~/Library/Logs/Crowdcraft`. Production logging configuration owns rotation and
retention. It removes the current import-time relative `logs/` creation and avoids
duplicate root/Uvicorn handlers. Request logging records method, route template,
status, duration, request ID, and bounded client/network metadata; it excludes
query strings, auth headers, cookies, request bodies, signed URLs, and raw exception
values. A regression test submits canary secrets through headers/query/body and
asserts none appear in captured logs.

## Release and rollback state machine

### Release command

Use one Python orchestrator with a single-process filesystem lock and a durable
release record. Shell scripts may wrap it but may not duplicate the sequence.

```text
crowdcraft-ops deploy release --revision <full-git-sha>
```

State transitions are append-only in the release record:

```text
CREATED
  -> PREFLIGHT_PASSED
  -> VERIFIED
  -> STATIC_STAGED
  -> SERVICE_QUIESCED
  -> BACKUP_VERIFIED
  -> DATABASE_MIGRATED
  -> CONTENT_SYNCED
  -> STATIC_PUBLISHED
  -> SERVICE_READY
  -> SMOKE_PASSED
  -> COMPLETE
```

The command:

1. Requires a full commit SHA reachable from the approved branch, a clean dedicated
   checkout, supported Python/Node/cloudflared/sqlite tools, valid LaunchAgents,
   readable Keychain items, enough disk for two databases plus builds, and no other
   release lock holder.
2. Records the current Git SHA, active static release, database revision, and
   service state.
3. Runs the canonical deterministic gate, production-SQLite integration gate,
   dependency/secret checks required by A, and all four frontend builds.
4. Builds into a new staging directory. It writes a manifest per game containing
   release ID, Git SHA, build timestamp, and asset hashes, then verifies no source
   map or environment secret was emitted unintentionally.
5. Runs local static tests against staging before touching the running release.
6. Quiesces the server with `launchctl bootout` and waits for the single listener
   and database connections to close. `KeepAlive` must not race the migration.
7. Checkpoints WAL, creates and verifies the pre-migration backup, and records its
   identifier.
8. Runs `alembic upgrade head` against the explicit production database path.
9. Runs `sync-content --apply` with the release ID, followed by integrity,
   foreign-key, migration, and ledger reconciliation checks.
10. Moves the staged static directory into immutable releases and atomically
    replaces the `static/current` symlink with a Python `os.replace`.
11. Records the actual Alembic head in the release manifest and LaunchAgent
    environment, bootstraps the server, waits for `/livez`, then waits for `/readyz`
    with separate bounded deadlines.
12. Runs local exact-host API/static/WebSocket smoke, then public staging-host smoke
    when requested.
13. Marks the release complete only after smoke passes and writes the final release
    record.

No step after a failure is reported as attempted or passing. Failure output includes
the failed state, release ID, pre-migration backup ID, previous static release ID,
previous Git SHA, and one redacted rollback command.

### Rollback command

```text
crowdcraft-ops deploy rollback --release-id <failed-or-current-release>
```

Rollback is also recorded and locked:

1. Confirm the referenced release record, previous Git SHA/static release, and
   verified pre-migration backup agree.
2. Quiesce the service.
3. Preserve the failed database as an incident artifact using the SQLite backup
   API.
4. Restore and verify the recorded pre-migration backup.
5. Return the dedicated checkout and dependencies to the recorded previous
   revision using a guarded, clean-checkout operation.
6. Atomically point `static/current` at the previous static release.
7. Start the service, wait for readiness, and run the rollback smoke matrix.
8. Record success or remain stopped with exact recovery diagnostics.

An application rollback that would run old code against a forward-only migrated
database is forbidden. If the previous code is schema-compatible, the release
record may say database restore is unnecessary; that decision must be explicit and
tested before release. DNS rollback to Heroku/Vercel remains separate and is used
only while the legacy deployment is retained and its data consistency implications
are understood.

## Cloudflare and staging implementation

Use a locally managed named tunnel with a config file containing the tunnel UUID,
credentials-file path, four exact hostname ingress entries, and a final
`http_status:404` catch-all. Validate it before restart:

```bash
cloudflared tunnel ingress validate
cloudflared tunnel ingress rule https://quipflip.crowdcraftlabs.com/
```

Create DNS routes explicitly for all four hosts and record their IDs. Do not put a
Cloudflare API token in the repository or release script; tunnel credentials remain
under `~/.cloudflared` with owner-only permissions.

Cloudflare currently documents
[named-tunnel configuration files](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/configuration-file/)
for multiple services and
[macOS login/boot service installation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/as-a-service/macos/).
This repository keeps its own LaunchAgent template so the tunnel lifecycle, paths,
and logs remain paired with the server runbook.
[WebSockets must be enabled for the zone](https://developers.cloudflare.com/network/websockets/)
and tested over the public `wss://` hosts; HTTP success alone is insufficient.

Staging uses either direct loopback requests carrying the four final `Host` values
or four dedicated staging aliases that do not displace the legacy public records.
If aliases are used, F1 records their exact names and the application contains an
explicit staging-only alias map from each name to one game. Never accept a wildcard
staging host or let a staging alias select game scope from a path/query hint.

## Verification design

### Automated host matrix

For every host, test:

| Request | Expected result |
| --- | --- |
| `/livez` | 200, no database access |
| `/readyz` | 200 only with exact release/database/static state |
| `/` | Correct SPA identity marker |
| Known deep link | Same SPA `index.html` |
| Hashed asset | Correct file and immutable cache header |
| Own API prefix | Routed normally |
| Other game's API prefix | 404 before other router/auth logic |
| `/auth/session` | Host-derived game snapshot |
| Own notification/presence WS | Upgrade and authenticated message |
| Other game's WS | Rejected before acceptance |
| Unknown host | Rejected, never a default SPA |

Run the matrix with direct loopback requests carrying exact `Host` headers, through
the tunnel staging hosts, and after public DNS cutover. Add negative tests for
forged `X-Forwarded-Host`, mixed-case/malformed hosts, explicit ports, traversal,
asset symlink escape, HTML fallback on API 404, and stale static manifests.

### Readiness failure tests

Each dependency is independently broken and restored:

- database missing/unreadable;
- wrong Alembic revision;
- `foreign_keys=OFF`, non-WAL mode, short busy timeout, or non-FULL synchronous;
- missing/wrong static manifest or `index.html`;
- insufficient free-space threshold;
- missing local dictionary;
- scheduler failed to start;
- optional AI provider absent.

The first seven return a bounded 503. The optional provider case remains ready and
reports degraded operator status.

### Release/rollback fault injection

Tests invoke the orchestrator with fake command runners and temporary SQLite/static
roots. Inject failure after every state transition and assert:

- no later state runs;
- the release record names the exact failed state;
- pre-migration backup precedes migration;
- static publication is atomic;
- restart is bounded;
- rollback selects only artifacts recorded by that release;
- logs and diagnostics contain canary values only in redacted form.

At least one Mac rehearsal runs the real launchd, Keychain, backup, migration,
static swap, readiness, smoke, and rollback paths before cutover.

## Reviewable implementation slices

Do not implement this workstream as one change. The intended sequence is:

1. **F-01 — Runtime config and SQLite production profile.** Add fail-closed
   production settings, connection pragmas, and configuration tests. No routing or
   deployment mutation.
2. **F-02 — Liveness/readiness and startup purity.** Add readiness service, remove
   startup mutation, and add idempotent release/maintenance command boundaries.
3. **F-03 — Frontend same-origin helpers.** Remove legacy origins and add pure URL
   tests across shared and IR-specific clients.
4. **F-04 — Host scope and auth isolation.** Add the outer ASGI boundary, derive
   auth/WS scope from host, and prove the negative matrix. Requires independent
   security review.
5. **F-05 — Static release serving.** Add per-host API-first SPA fallback, cache
   policy, security headers, and traversal/deep-link tests.
6. **F-06 — SQLite backup/restore and reconciliation.** Replace the current backup
   script and prove create/verify/restore against production-shaped SQLite.
7. **F-07 — Legacy data migration rehearsal.** Implement export/import reports and
   complete a private-data-safe rehearsal. Requires independent migration and money
   reviews.
8. **F-08 — Keychain wrapper and LaunchAgents.** Add templates/installer, durable
   logging, one-worker enforcement, restart verification, and service runbook.
9. **F-09 — Release and rollback orchestrators.** Implement the state machines,
   fault-injection tests, and one real Mac rollback rehearsal. Requires independent
   deployment/security review.
10. **F-10 — Tunnel, staging, cutover, and soak evidence.** Install the named
    tunnel, run the complete matrix, execute cutover, record soak decisions, and
    retire legacy providers only after acceptance.

Each slice updates the unchecked items it actually proves and uses the repository
pull-request evidence headings. F-04, F-07, and F-09 must not share the same sole
reviewer because they cover distinct high-risk boundaries.

## Decisions that F1 must record

The following operator defaults are now selected for this plan and should be
recorded verbatim in `docs/operations/deployment-inventory.md`:

- Heroku production data is not retained. Cutover starts from a fresh production
  SQLite database, and no DNS-rollback reconciliation path is planned for
  discarded historical data.
- Production checkout path: `/Users/tfish/quipflip`; operator account: `tfish`.
- Target Mac availability: always-on AC power, wired network, and auto-login for
  the operator account. Remote recovery is via SSH or Screen Sharing when
  available, otherwise physical access.
- Database and backup policy: keep the current rollback candidate plus the last 3
  successful backups, require at least 5 GiB free and at least 2x the current DB
  plus WAL size before release mutation, store off-host backups on an encrypted
  APFS volume or equivalent encrypted removable drive, and assign restore owner
  to `tfish`.
- Staging DNS: four dedicated aliases with a `staging.` prefix
  (`staging.quipflip.crowdcraftlabs.com`, `staging.mememint.crowdcraftlabs.com`,
  `staging.initialreaction.crowdcraftlabs.com`, and
  `staging.thinklink.crowdcraftlabs.com`), each routed through the named tunnel
  and mapped 1:1 to its game.
- Soak duration: 72 hours. Rollback window: 72 hours. Rollback decision owner:
  `tfish`. Rollback triggers: sustained readiness failure, integrity mismatch, or
  HTTP 5xx above 1% over 15 minutes.
- AI provider policy: OpenAI is the primary provider and Gemini is the fallback
  for AIService-driven fill/vote flows. ThinkLink semantic matching remains
  OpenAI-backed; if OpenAI is unavailable, that feature is disabled and the rest
  of the game stays up.
- Old browser clients are not supported through cutover. Only the updated
  same-origin clients are required.
- `cloudflared` ownership stays with the repository LaunchAgent after cutover.
  Cloudflare dashboard setup only provisions the tunnel and DNS records.

Any future unresolved item is represented as a blocking `TBD` in
`docs/operations/deployment-inventory.md`; production preflight rejects a cutover
record containing a blocking `TBD`.

## Phase F1a - Decisions, inventory, and rollback contract

- [ ] Record that Heroku production data will not be retained and that cutover
      starts from a fresh production database.
- [ ] Inventory databases, static assets, environment variables, domains, cookies,
      scheduled jobs, and external providers.
- [ ] Name production database, WAL, backup, staging-build, log, and release paths.
- [ ] Define backup retention, integrity checks, restore owner, and disk alerts.
- [ ] Define accepted Mac/network availability and remote recovery expectations.
- [ ] Define rollback triggers, decision owner, and maximum rollback window.
- [ ] Define optional-provider degraded behavior per game.
- [ ] Reject default secrets, unsafe origins, and missing production configuration.

Gate:

- [ ] Data retention and rollback decisions are recorded before schema or cutover
      work begins.

## Phase F1b - Data migration and restore rehearsal

- [ ] Take an authenticated legacy data export without committing private data.
- [ ] Verify source backup integrity and record schema/version metadata.
- [ ] Convert/import data into a local production-shaped SQLite database.
- [ ] Run pre-migration validation and reconciliation queries.
- [ ] Rehearse the complete Alembic upgrade chain.
- [ ] Run post-migration row, relationship, lifecycle, and ledger reconciliation.
- [ ] Back up the migrated database and restore it to a separate location.
- [ ] Start the application against the restored copy and run read-only checks.
- [ ] Document redacted commands, timing, failure recovery, and rollback.

Gate:

- [ ] A production-shaped backup can be migrated, integrity-checked, restored, and
      opened by the target application.

## Phase F2 - Liveness, readiness, and release commands

- [ ] Add `/livez` for process liveness only.
- [ ] Add `/readyz` for database access, expected migration revision, required
      static assets, and mandatory runtime dependencies.
- [ ] Return explicit non-2xx readiness responses on failure.
- [ ] Keep optional AI-provider outages out of readiness when degraded behavior is
      defined.
- [ ] Move seeding, cleanup, and other slow/destructive startup mutations to
      explicit idempotent commands.
- [ ] Add readiness tests for each failed dependency.
- [ ] Add bounded, redacted diagnostic output.

Gate:

- [ ] Liveness and readiness distinguish a running process from a service safe to
      receive traffic.

## Phase F3 - Same-origin client and exact-host server

- [ ] Make an absent API override resolve to `window.location.origin`.
- [ ] Derive WebSocket origin from the current location.
- [ ] Remove production localhost fallback behavior.
- [ ] Add tests for override-present, override-absent, HTTP, HTTPS, and WebSocket
      origin derivation.
- [ ] Validate exact trusted hosts before routing.
- [ ] Map each host to only its game API prefix and shared approved routes.
- [ ] Derive server auth/game scope from the validated host, not a client hint.
- [ ] Ensure API and WebSocket routes take precedence over SPA fallback.
- [ ] Serve the correct built SPA and deep links for each host.
- [ ] Set immutable cache headers for hashed assets and safe headers for HTML.
- [ ] Keep cookies host-only with production security attributes.

Gate:

- [ ] A host-dispatch test matrix proves correct SPA/API/WS routing and rejects
      unmatched or cross-game hosts.

## Phase F4 - Mac service and secrets

- [ ] Create a service wrapper using an absolute `.venv/bin/uvicorn` path.
- [ ] Enforce exactly one worker.
- [ ] Load secrets from macOS Keychain without putting them in the plist, command
      line, repository, or logs.
- [ ] Place the SQLite database outside the repository.
- [ ] Configure WAL, foreign keys, busy timeout, and synchronous mode at startup.
- [ ] Write rotated logs under a durable user-owned location.
- [ ] Define service start, stop, restart, status, and log-inspection commands.
- [ ] Verify restart recovery and launch-at-login/boot behavior as intended.
- [ ] Document filesystem ownership and backup access.

Gate:

- [ ] The service starts from a clean login context, passes readiness, and recovers
      durable state after restart without exposing secrets.

## Phase F5 - Safe release automation

- [ ] Validate configuration and required tools before mutation.
- [ ] Build all four frontends into a staging directory.
- [ ] Run deterministic verification and required release gates.
- [ ] Back up and integrity-check the production database.
- [ ] Run `alembic upgrade head` and stop on failure.
- [ ] Atomically publish static assets.
- [ ] Restart the service and wait with a bounded readiness timeout.
- [ ] Run API, static, WebSocket, and game smoke checks.
- [ ] Stop the release on any failure and print redacted rollback instructions.
- [ ] Record release revision, migration revision, backup identifier, and smoke
      result.

Gate:

- [ ] A failed release cannot silently continue to DNS/cutover, and the previous
      database/assets can be restored by the documented procedure.

## Phase F6 - Tunnel and staging

- [ ] Create one named Cloudflare tunnel.
- [ ] Route the four exact hostnames to `http://127.0.0.1:8000`.
- [ ] Reject unmatched hostnames at Cloudflare and application layers.
- [ ] Verify TLS, forwarded headers, client IP handling, and WebSocket upgrades.
- [ ] Keep the previous deployment available during staging.
- [ ] Run the full host/API/static/WS matrix through target subdomains.
- [ ] Verify deep links and cache behavior.
- [ ] Verify registration, login, logout, and host-only cookies.
- [ ] Verify restart recovery and a restore drill through the tunnel.

Gate:

- [ ] All four staged hostnames pass the browser, API, WebSocket, auth, and restore
      matrix while rollback remains available.

## Phase F7 - Cutover

- [ ] Take a final verified backup and record the rollback point.
- [ ] Run the safe release script against the approved revision.
- [ ] Run one complete game loop per app.
- [ ] Run QF Party multi-client reconnect smoke.
- [ ] Verify readiness and static deep links on all hosts.
- [ ] Change DNS only after the complete smoke matrix passes.
- [ ] Re-run the matrix after DNS propagation.
- [ ] Announce the rollback window and named decision owner.

Gate:

- [ ] The four public target domains pass the approved matrix with a tested rollback
      artifact available.

## Phase F8 - Soak and retirement

- [ ] Monitor readiness failures and HTTP error rate.
- [ ] Monitor WebSocket connection/reconnect behavior.
- [ ] Monitor queue age and finalizer lag from durable state.
- [ ] Run scheduled ledger reconciliation.
- [ ] Monitor SQLite disk use, busy errors, integrity checks, and backup success.
- [ ] Record incidents and rollback decisions during the soak window.
- [ ] Make and record an explicit accept/extend/rollback decision.
- [ ] Retire the previous deployment only after acceptance and rollback-window expiry.
- [ ] Update current deployment references and mark target runbooks active.

Gate:

- [ ] Old services are retired deliberately after a recorded soak decision, not
      merely because target DNS is live.

## Required verification

- [ ] Run deterministic, SQLite integration, frontend build, and all game smoke
      gates.
- [ ] Run backup/migrate/restore rehearsal.
- [ ] Run service restart and readiness failure tests.
- [ ] Run host/API/static/WS/auth browser matrix before and after DNS.
- [ ] Inspect release logs for secret or private-data leakage.
- [ ] Obtain independent security, migration, deployment, and rollback reviews.

## Exit criteria

- [ ] The Mac service is reproducible, one-worker, secret-safe, and restart-safe.
- [ ] Release and rollback are scripted and rehearsed.
- [ ] Every target host is isolated to its game and serves same-origin API/WS.
- [ ] Cutover and old-service retirement are gated by recorded evidence.

## Non-goals

- Multi-worker SQLite deployment.
- Removing rollback capacity before the soak decision.
- Treating a successful tunnel connection as proof of application readiness.
