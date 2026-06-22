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

## Phase F1a - Decisions, inventory, and rollback contract

- [ ] Decide whether and how legacy production data will be retained.
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
