# Persistent Startup Services

> **Document type:** Operational runbook
> **Status:** Target — not active until the deployment workstream passes
> **Audience:** Maintainers

The target deployment runs one FastAPI worker and one Cloudflare tunnel under
launchd. Several prerequisites already exist in code (`/livez`, `/readyz`,
exact-host dispatch, same-origin client helpers), but the transition plan still
describes the remaining gap to the target topology.

## Topology and paths

```text
four exact crowdcraftlabs.com hosts
        ↓ one Cloudflare named tunnel
http://127.0.0.1:8000
        ↓ FastAPI, exactly one Uvicorn worker
~/Library/Application Support/Crowdcraft/crowdcraft.sqlite3
```

Recommended local paths:

- database: `~/Library/Application Support/Crowdcraft/crowdcraft.sqlite3`
- backups: `~/Library/Application Support/Crowdcraft/backups/`
- logs: `~/Library/Logs/Crowdcraft/`
- tunnel config: `~/.cloudflared/crowdcraft.yml`

The database, WAL, secrets, and logs do not live in the repository.

## Required application behavior

The service is not deployable until the following requirements are satisfied.
Some are already present in `main`; the remaining gaps are the release wrapper,
release automation, and cutover evidence:

- `/livez`: process liveness only;
- `/readyz`: real non-2xx failure for database access, expected Alembic revision,
  required static assets, and required runtime configuration;
- exact host allowlisting, host-to-game API isolation, and host-to-SPA dispatch;
- API routes before SPA fallback;
- production startup skips the one-time bootstrap mutations; explicit release
  tooling owns any seeding or repair work, currently exposed as
  `scripts/ops/crowdcraft_ops.py bootstrap`;
- production SQLite pragmas: foreign keys, WAL, `busy_timeout=5000`, and
  `synchronous=FULL`;
- production refusal of default/empty signing secrets and unsafe origins;
- an absent API/WS override resolving to `window.location` in built frontends.

Do not gate a restart on `/health`; use `/readyz` for release gating and keep
`/health` as compatibility-only.

## Services

`com.crowdcraft.server` launches a repository wrapper using an absolute interpreter,
for example:

```text
/Users/tfish/quipflip/.venv/bin/python
/Users/tfish/quipflip/scripts/run-production-server.py
```

The wrapper reads named secrets from macOS login Keychain, validates non-secret
configuration, then `exec`s `.venv/bin/uvicorn backend.main:app --host 127.0.0.1
--port 8000 --workers 1`. Secret values are never written to the plist, command
line, repository, or logs.

`com.crowdcraft.tunnel` runs:

```text
cloudflared tunnel --config /Users/tfish/.cloudflared/crowdcraft.yml --no-autoupdate run
```

Both jobs use `RunAtLoad` and `KeepAlive`. Standard output/error go to bounded files
under `~/Library/Logs/Crowdcraft`.

## Tunnel ingress

```yaml
ingress:
  - hostname: quipflip.crowdcraftlabs.com
    service: http://127.0.0.1:8000
  - hostname: mememint.crowdcraftlabs.com
    service: http://127.0.0.1:8000
  - hostname: initialreaction.crowdcraftlabs.com
    service: http://127.0.0.1:8000
  - hostname: thinklink.crowdcraftlabs.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

The application still validates `Host`; tunnel ingress is not the only boundary.

## One-time preparation

1. Complete the deterministic, production-SQLite, and smoke gates.
2. Heroku data is not preserved for cutover. If that policy changes later, rehearse
   the export/conversion and restore into a copy of the target SQLite database
   before changing the plan.
3. Create application, backup, and log directories with owner-only permissions.
4. Store runtime secrets in Keychain and install the Keychain-reading wrapper.
5. Build all four frontends and verify static deep links locally with exact Host
   headers.
6. Create the tunnel, DNS routes, and two launchd agents.
7. Run the full target-domain smoke matrix before DNS cutover.

Do not put real secret values into setup commands that will remain in shell history.

## Safe release sequence

The planned `scripts/restart-production-server.sh` must:

1. validate the LaunchAgent, Keychain item names, database path, free disk, and
   production configuration without printing secrets;
2. run the canonical verification required for the release;
3. build the four SPAs into a staging directory;
4. stop or quiesce writers, run SQLite checkpoint/integrity checks, and create a
   timestamped backup using SQLite's online backup API;
5. run `alembic upgrade head` with the target `DATABASE_URL`;
6. atomically publish the staged static assets;
7. `launchctl kickstart -k gui/$(id -u)/com.crowdcraft.server`;
8. wait for `http://127.0.0.1:8000/readyz`;
9. run the built-server smoke loop and target-host checks; and
10. print bounded, redacted diagnostics on failure.

Never copy only the main database file while WAL writes may be pending. Retain the
pre-migration backup until the soak window is accepted.

## Verification matrix

Local:

```bash
curl -fsS http://127.0.0.1:8000/livez
curl -fsS http://127.0.0.1:8000/readyz
lsof -iTCP:8000 -sTCP:LISTEN -P -n
```

For each public host, verify:

- `/livez` and `/readyz` return 200;
- `/` and a client-side deep link serve the correct game, never another game's SPA;
- a mismatched API prefix returns 404 and shared auth uses the validated host's game;
- API calls remain on the same origin and host-only cookies authenticate;
- registration/login/logout/refresh work;
- one complete game loop works;
- QF notification, presence, and Party WebSockets use the same host;
- reconnect restores state after a server restart.

Also restore the newest backup to a separate temporary path and run integrity and
smoke checks against it.

## Monitoring and rollback

Monitor readiness, disk space, backup age, SQLite busy/locked errors, WAL size,
deadline lag, queue age, WebSocket reconnects, HTTP 5xx, and ledger reconciliation.

During cutover, keep the previous deployment available. If migration or smoke
fails, stop the new service, restore the pre-migration SQLite backup or return DNS
to the previous deployment, and record the failed step. Do not attempt an ad-hoc
reverse migration on the production file.

## Troubleshooting

- **Wrong SPA/404:** verify exact Host dispatch, API-first order, staged `dist`, and
  deep-link fallback.
- **503 readiness:** inspect migration revision, database permissions/pragmas, static
  asset presence, and redacted server diagnostics.
- **`database is locked`:** do not add workers. Inspect transaction duration and
  network/AI calls inside transactions; confirm busy timeout and WAL mode.
- **WebSocket 1008:** mint a fresh actor-scoped token and verify same-origin URL
  construction and party membership.
- **Keychain failure:** unlock the login Keychain and rerun the secure configuration
  helper; never fall back to a plaintext secret.
- **Large WAL:** confirm checkpoints and long-lived readers before forcing any file
  operation.
