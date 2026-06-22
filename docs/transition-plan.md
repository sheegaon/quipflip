# Crowdcraft Labs Reliability and Deployment Plan

> **Document type:** Delivery roadmap
> **Status:** Active proposal
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Purpose

Bring QuipFlip, MemeMint, Initial Reaction, and ThinkLink to the reliability and
operating standard demonstrated by the sibling `pixel-plagiarist` repository, then
serve them at:

- `quipflip.crowdcraftlabs.com`
- `mememint.crowdcraftlabs.com`
- `initialreaction.crowdcraftlabs.com`
- `thinklink.crowdcraftlabs.com`

The product remains four asynchronous, database-backed games plus QuipFlip Party
Mode. This is not a rewrite onto Pixel Plagiarist's Socket.IO room engine. The work
imports its useful properties: server authority, stale-safe commands, private
projections, deterministic tests, a real smoke loop, reproducible operations, and
evidence-based delivery.

## Verified baseline

The following evidence was collected on 2026-06-22. It is a snapshot, not a
permanent claim.

### Pixel Plagiarist reference

- `npm run verify`: passed; 16 test files and 141 tests passed, followed by a
  production build.
- `npm run smoke`: passed a built-server, five-client Socket.IO flow covering
  authenticated profiles, isolation, phase reconnects, telemetry attribution,
  restart persistence, and reset.
- `https://pixel.crowdcraftlabs.com/healthz`: returned HTTP 200.
- Browser check: the production landing page rendered and connected.

The useful reference is not merely its framework choice. It has one command
boundary for game mutation, phase-scoped stale-command rejection, explicit private
projections, fake-clock lifecycle tests, a deterministic gate, and a production
smoke test.

### Crowdcraft Labs current repository

- `.venv/bin/python -m pytest -q`: 355 passed, 44 failed, 90 errors, 9 skipped.
  The default collection incorrectly includes localhost and stress suites that
  require a separately running server. The remaining failures also show shared
  database/singleton state, AI mocks, IR model drift, and genuine rule regressions.
- `npm run build:qf` and `npm run build:mm`: passed.
- `npm run build:ir`: failed TypeScript compilation; the chained build therefore
  did not reach ThinkLink.
- `https://quipflip.xyz/`: returned HTTP 200 and rendered the landing page, but its
  browser console recorded a failed guest-account request.
- `https://quipflip-c196034288cd.herokuapp.com/health`: returned Heroku
  maintenance-mode HTTP 503.
- No Crowdcraft service was listening on local port 8000, and the four target
  `crowdcraftlabs.com` hostnames were not yet deployed.

### Code-level findings that change this plan

1. The database is intended to be authoritative, but the QF prompt and phraseset
   queues can be in-memory/Redis lists whose mutation is not atomic with database
   commits. Queue contents and copy-discount pricing can therefore diverge from
   durable state.
2. `LockClient` uses synchronous Redis/thread locks inside async service methods.
   Contention can block the event loop. Copy candidates are selected before the
   prompt-level critical section, and the existing lock is commonly scoped only to
   the player, so it cannot prove exclusive assignment of a prompt.
3. A single worker or Redis lock is not a correctness boundary. Redis leases can
   expire; processes can restart; scripts can bypass them. Database transactions,
   compare-and-swap updates, unique/check constraints, and idempotency
   keys must make invalid states uncommittable.
4. SQLite tests do not enable `PRAGMA foreign_keys=ON`; `FOR UPDATE` is ineffective
   on SQLite; and the current engine does not configure production pragmas such as
   WAL and a busy timeout. The gate therefore does not exercise the chosen
   production concurrency model.
5. The ledger has transaction rows and cached wallet/vault balances, but it lacks a
   general uniqueness key that makes retries provably idempotent.
6. Party phase advancement contains an `async with` call against the synchronous
   lock context manager and lacks direct test coverage for that path.
7. `VITE_API_URL=''` does not currently select same-origin because the clients use
   `value || localhostFallback`. Same-origin deployment needs a code change and
   tests, not only an environment change.
8. `/health` returns a Python tuple on database failure rather than an explicit
   503 response. It is not yet a safe readiness gate. Startup also performs data
   seeding/cleanup, so process liveness and readiness must be separated.
9. The current CI uses Python 3.11 while repository guidance requires 3.12, omits
   the IR frontend job, does not run the whole backend collection, and does not pin
   actions to immutable SHAs.

## Architectural decisions

### Authority and lifecycle ownership

The server decides eligibility, queue assignment, prices, vote validity, scoring,
payouts, and transitions. Each state transition has one named command that:

1. validates the authenticated actor and request;
2. opens a database transaction;
3. performs a conditional update against the expected state/version, using a short
   `BEGIN IMMEDIATE` write transaction only where compare-and-swap is insufficient;
4. re-validates the lifecycle precondition;
5. writes state, ledger entries, and an outbox/job record atomically;
6. commits; and
7. performs cache/queue notification after commit.

Process or Redis locks may reduce contention, but correctness must survive their
absence, expiry, and retry. Public command retries need a client command key or a
server-generated idempotency key with a database uniqueness constraint.

### Database and queues

SQLite is the production source of truth for the Mac deployment. The decision is
intentional: one host, one Uvicorn worker, current traffic, and minimal operational
machinery. Every connection enables foreign keys and a 5-second busy timeout;
production uses WAL with `synchronous=FULL`. The database file,
WAL, backups, and restore drills live outside the repository.

SQLite does not implement useful `SELECT ... FOR UPDATE` behavior. Lifecycle
commands therefore use status/version compare-and-swap updates, unique/check
constraints, and short transactions. A single async worker reduces contention but
does not replace these invariants because retries and maintenance tools can still
race.

Queue availability and discount counts are database-derived facts. An in-memory
queue may cache or notify, but restarting the process must not lose a claimable
round or change the economy. Prefer an indexed conditional update against a
claimable row over a durable lifecycle split between a list and a row.

### Deadlines and background jobs

There does not need to be one global finalizer for every game. Each lifecycle has
one transition command; one or more schedulers may discover due rows and call that
command. Discovery is not mutation ownership.

Deadline commands are idempotent and stale-safe. They compare the expected status,
version, and deadline inside the database transaction. Re-running a job cannot
double-refund, double-pay, or re-queue. AI-fill jobs and cleanup jobs use the same
command boundary or restrict themselves to non-gameplay operational data.

### Money

Wallet and vault columns may remain cached balances for efficient reads, but every
movement has exactly one ledger row and both are updated in the same transaction.
Each logical movement has a unique idempotency key. Tests reconcile cached balances
against ledger sums and prove duplicate refund/payout commands are no-ops.

### Private protocol

Every response is an explicit Pydantic projection. Before finalization, responses
must not reveal authorship, the prompt hidden from a copy player, which entry is the
original, or stable internal relationships that let clients correlate those facts.
Where a later command needs a reference, issue an opaque, actor-scoped assignment
token rather than exposing a canonical lifecycle ID without review.

### Deployment

One FastAPI process serves the four APIs and four built SPAs behind one Cloudflare
named tunnel. Host dispatch occurs after exact host validation, each host permits
only its game prefix plus shared health/auth routes, and API routes take precedence
over SPA fallback. Shared auth derives game scope from the validated host rather
than trusting a client hint. Cookies remain host-only; WebSocket URLs and API URLs
derive from `window.location`.

The Mac service uses a local SQLite database and exactly one Uvicorn worker, an
absolute virtual-environment executable, and secrets loaded from macOS Keychain by
a wrapper. Secrets do not live in the repository, plist, command line, or logs.

## Workstreams

### A. Trustworthy verification

- **A1 — Define test tiers.** Add pytest markers and configuration so the default
  deterministic gate excludes `*_localhost*` and stress suites. A test that needs a
  server must not fail inside the unit/integration gate merely because port 8000 is
  closed.
- **A2 — Isolate tests.** Give each run a temporary database and reset global
  caches, queue singletons, validator state, clocks, and settings. Prohibit network
  calls in the deterministic tier.
- **A3 — Enforce SQLite integrity.** Enable `PRAGMA foreign_keys=ON` for every
  SQLite connection and prove it with a test.
- **A4 — Test production SQLite semantics.** Run the complete Alembic chain plus
  multi-connection concurrency/constraint tests against a temporary SQLite file
  configured with the production pragmas. Add explicit tests for busy handling,
  compare-and-swap losers, restart recovery, and backup/restore.
- **A5 — Repair frontend gates.** Fix IR compilation, then lint/typecheck/build all
  four apps and the shared library from one root command using `npm ci`.
- **A6 — Create canonical commands.** Add `verify`, `test:sqlite-integration`, and `smoke`
  entry points. CI uses Python 3.12, Node 20, pinned actions, minimal permissions,
  concurrency cancellation, timeouts, secret scanning, npm audit, and a Python
  dependency audit.

Exit: a clean checkout can run one documented deterministic command; production-
configured SQLite integration and smoke are separate named gates; failures are
reproducible.

### B. Lifecycle inventory and database invariants

- **B1 — State-machine inventory.** For QF solo, QF Party, MM, IR, and TL, document
  states, commands, actors, deadlines, money movements, forbidden disclosures, and
  every current mutation caller. Mark observations separately from hypotheses.
- **B2 — Schema invariants.** Add status/check constraints, required foreign-key
  actions, uniqueness for active assignments/votes/result collection, lifecycle
  versions where needed, and idempotency keys for ledger movements. Rehearse every
  migration against a production-shaped backup.
- **B3 — Remove queue authority.** Make claimability and pricing database-derived.
  Treat Redis/in-memory queues as rebuildable accelerators or remove them.
- **B4 — Async-safe coordination.** Replace synchronous locks in async paths. Use
  database conditional updates, constraints, and short write transactions for
  correctness. Use keyed `asyncio.Lock` coordination only to reduce same-process
  contention; it is not an integrity guarantee.
- **B5 — One command per transition.** Route endpoints, AI workers, deadline jobs,
  and Party orchestration through the same service command. Keep public behavior
  stable unless a protocol privacy fix requires a versioned change.

Exit: invalid ownership, duplicate payout, and double-claim states are rejected by
the database even if coordination is bypassed.

### C. QuipFlip solo hardening

- Regression-first coverage for concurrent prompt/copy/vote claims, one active
  assignment per player, queue restart, duplicate submission, timeout refund,
  stale finalizer, contributor vote exclusion, and duplicate payout.
- Put copy selection, claim, charge, active-round assignment, and durable queue
  state in one transaction.
- Add opaque assignment tokens and forbidden-field assertions for start, detail,
  reconnect, dashboard, and result payloads.
- Convert symptom scripts (`cleanup_orphaned_rounds.py`,
  `debug_copy_availability.py`, `fix_orphaned_captions.py`) into regression tests or
  guarded `scripts/ops/` tools. Keep repair tools only for already-corrupt data.
- Extract scoring, discount, eligibility, and prize distribution into pure rules
  with seeded tests. Preserve the intended economy in the game-rules documents.

Exit: the complete QF solo smoke passes on a built server and production-configured
SQLite; repeated or concurrent commands cannot corrupt ownership or money.

### D. QuipFlip Party Mode

- Reconcile the intent of remote branches `party-refactor` and
  `refactor-round-names`; do not merge them blindly.
- Replace the broken lock usage and define a session phase/version plus authoritative
  deadline for every Party phase.
- Reconnect restores the same participant, assignment, counters, votes, and
  deadline. A disconnected socket is presence, not lifecycle authority.
- Add fake-clock tests for join, ready, start, submit, disconnect, reconnect,
  duplicate REST calls, stale WebSocket/status updates, timeout, and AI fills.
- Split oversized Party services by command/projection/rule boundaries only while
  adding tests; avoid a mechanical rewrite.

Exit: a multi-client Party smoke completes through results, including reconnect and
a stale phase command.

### E. MemeMint, Initial Reaction, and ThinkLink

Apply the B/C guarantees game by game, prioritizing money and lifecycle risk:

1. IR build/model drift and transaction tests;
2. MM caption author integrity and vote/caption atomicity;
3. TL scoring, matching, and round finalization;
4. cross-game auth/session and shared-client behavior.

Each game gets a state-machine page, pure-rule tests, SQLite lifecycle tests,
private-projection tests, and one built-server smoke loop before cutover.

### F. Mac + Cloudflare deployment

- **F1 — Production prerequisites.** Decide data retention before schema work.
  Inventory Heroku data, take and verify a backup, rehearse conversion/restore into
  local SQLite, and document rollback. Production configuration must reject default
  secrets and unsafe origins.
- **F2 — Readiness.** Add `/livez` for process liveness and `/readyz` for database,
  migration revision, required static assets, and required runtime dependencies.
  Failures return real non-2xx responses. Move destructive/slow startup mutation to
  explicit, idempotent release commands.
- **F3 — Same-origin client/server.** Change the clients so an absent production
  API override means `window.location.origin`; do not use an empty value with `||`.
  Derive WebSocket origin the same way. Add exact-host dispatch, host-to-game API
  isolation, TrustedHost validation, API-first routing, SPA fallback, and cache
  headers for hashed assets.
- **F4 — Service wrapper.** Use an absolute `.venv/bin/uvicorn`, a SQLite database
  outside the repository, exactly one worker, Keychain-loaded secrets,
  bounded/redacted diagnostics, and logs under `~/Library/Logs/Crowdcraft` (or
  another durable, rotated location).
- **F5 — Safe release script.** In order: verify clean configuration, build to a
  staging directory, back up the database, run `alembic upgrade head`, atomically
  publish static assets, restart, wait for `/readyz`, and run smoke. A failure stops
  the release and prints redacted diagnostics.
- **F6 — Tunnel and DNS.** Route all four exact hostnames through one named tunnel
  to `http://127.0.0.1:8000`; reject unmatched hosts.
- **F7 — Parallel cutover.** Keep Heroku/Vercel available during staging. Verify
  registration/login, cookies, one game loop per app, QF WebSockets/Party reconnect,
  static deep links, backup/restore, and restart recovery through the target
  subdomains. Cut DNS only after the smoke matrix passes.
- **F8 — Soak and retire.** Monitor readiness, error rate, WebSocket reconnects,
  queue age, finalizer lag, and ledger reconciliation. Retire old services only
  after the rollback window and a recorded soak decision.

## Delivery sequence and exit criteria

| Phase | Scope | Exit criteria |
| --- | --- | --- |
| 0. Operating model | Docs and ADRs | Current/target/historical docs are unambiguous; database correctness boundary accepted |
| 1. Green baseline | A | Deterministic verify passes; IR builds; production-SQLite and smoke tiers exist |
| 2. Durable QF solo | B + C | QF constraints, idempotency, private DTOs, and SQLite smoke pass |
| 3. Party reliability | D | Multi-client fake-clock and built-server Party smoke pass |
| 4. Remaining games | E | MM, IR, and TL each pass rules, lifecycle, privacy, and smoke gates |
| 5. Staged deployment | F1–F6 | Restore rehearsal, release script, host dispatch, services, and tunnel pass locally |
| 6. Cutover | F7 | Four target domains pass the browser/API/WS matrix with rollback ready |
| 7. Soak and retirement | F8 | Monitoring window accepted; Heroku/Vercel retired deliberately |

Phases describe merge gates, not a ban on parallel work. Deployment scripts and
host dispatch can be developed after Phase 1, but public cutover waits for all four
game smoke loops and the restore rehearsal.

## Risk register and decisions still required

| Risk or decision | Required resolution |
| --- | --- |
| Heroku data retention | Decide before schema migration; default recommendation is preserve and rehearse restore |
| SQLite ownership on the Mac | Name database/backup locations, retention, restore owner, integrity checks, and disk monitoring |
| In-memory queues/locks | Rebuildable optimization only; never a required source of lifecycle truth |
| AI providers unavailable | Define degraded behavior per game; readiness should not fail for an explicitly optional provider |
| Mac/network outage | Document accepted availability target, remote recovery, and rollback to old hosting during cutover |
| SQLite contention/corruption | WAL, busy timeout, short writes, integrity checks, backups, and multi-connection tests |
| Hidden-information protocol | Inventory every normal and reconnect projection before versioning fields |
| Scope growth | One lifecycle/game at a time; no framework rewrite or visual redesign |

## Target topology

```text
quipflip.crowdcraftlabs.com       ─┐
mememint.crowdcraftlabs.com        │  Cloudflare named tunnel
initialreaction.crowdcraftlabs.com ├────────────► 127.0.0.1:8000
thinklink.crowdcraftlabs.com      ─┘              FastAPI, one worker
                                                       │
                                                       ▼
                                                local SQLite
```

Host mapping:

| Host | API prefix | SPA |
| --- | --- | --- |
| `quipflip.crowdcraftlabs.com` | `/qf` | `frontend/qf` |
| `mememint.crowdcraftlabs.com` | `/mm` | `frontend/mm` |
| `initialreaction.crowdcraftlabs.com` | `/ir` | `frontend/ir` |
| `thinklink.crowdcraftlabs.com` | `/tl` | `frontend/tl` |

## Source references

- Pixel Plagiarist: `AGENTS.md`, `docs/development/`, `docs/decisions/`,
  `scripts/smoke.mjs`, and `scripts/restart-production-server.sh`.
- Crowdcraft runtime: `backend/main.py`, `backend/database.py`,
  `backend/utils/{lock_client,queue_client}.py`, `backend/services/{qf,mm,ir,tl}`,
  `backend/models/`, `backend/migrations/`, and `frontend/crowdcraft/src`.
- Current deployment: [DEPLOYMENT.md](DEPLOYMENT.md).
- Target operations: [persistent startup services](development/persistent-startup-services.md).
