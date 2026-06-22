# Codebase Organization and Engineering Guide

> **Document type:** Engineering guidance
> **Status:** Active target
> **Audience:** Maintainers and contributors

This guide defines the intended boundaries for Crowdcraft Labs. The
[transition plan](../transition-plan.md) records the gap between this target and the
current implementation.

## Primary rule

```text
browser SPA
    ↓ validated REST commands + read-only WS subscriptions
FastAPI router
    ↓ one service command
transactional lifecycle command
    ↓ conditional status/version mutation + constraints + ledger write
SQLite (durable source of truth)
    ↑ due-row discovery calls the same commands
```

The server is authoritative. Clients display server projections and submit
commands; they do not decide assignment, pricing, eligibility, scoring,
finalization, or deadlines.

## Repository structure

```text
backend/
  routers/        # transport/auth adapters and WebSocket endpoints
  services/       # lifecycle commands, projections, schedulers, infrastructure
  models/         # SQLAlchemy models and database constraints
  schemas/        # Pydantic request and response contracts
  middleware/     # request-level cross-cutting behavior
  tasks/          # due-work discovery; no independent mutation paths
  migrations/     # Alembic migrations
  main.py         # app wiring and lifespan only
frontend/
  crowdcraft/     # shared API, context, hook, and UI library
  qf/ mm/ ir/ tl/ # four game SPAs
tests/            # deterministic, lifecycle, SQLite integration, and external tiers
scripts/          # guarded release, backup, restore, and repair tools
docs/             # rules, references, ADRs, plans, and runbooks
```

Organize by runtime and game concept. Avoid generic modules that mix transport,
mutation, projection, and rules.

## Boundaries

### Routers

A route handler normally:

1. authenticates and resolves the actor;
2. validates the request body;
3. calls one service command; and
4. maps the typed result to an explicit response schema or error.

Routers do not select queue candidates, mutate balances, advance phases, calculate
scores, or assemble broad dictionaries from ORM objects.

### Lifecycle commands

Each state transition has one owning command. The command:

1. starts a short SQLite transaction;
2. checks the actor and command idempotency key;
3. conditionally updates the expected status/version or inserts under a uniqueness
   constraint;
4. verifies that exactly one row changed;
5. writes every related lifecycle row and ledger movement;
6. commits; and
7. publishes rebuildable cache/notification work after commit.

SQLite does not provide meaningful row-level `FOR UPDATE` behavior. Use
compare-and-swap (`UPDATE ... WHERE id = ? AND status = ? AND version = ?`), unique
constraints, and check constraints. Use `BEGIN IMMEDIATE` sparingly for invariants
that cannot be represented by a conditional update.

Keyed `asyncio.Lock` coordination can reduce contention in the single worker. It
does not replace database invariants: retries, repair tools, and restarts must remain
safe when no lock is held. Never hold a synchronous thread or Redis lock across an
`await`.

### SQLite configuration

Production and production-shaped tests use the same settings:

- `PRAGMA foreign_keys=ON` on every connection;
- WAL journal mode;
- `busy_timeout=5000`;
- WAL with `synchronous=FULL`;
- exactly one Uvicorn worker;
- short write transactions with no network or AI call inside them.

The database file and WAL live outside the repository. Release procedures back up,
integrity-check, migrate, and restore-test the database. Readiness verifies the
expected migration revision and database configuration.

### Queues and caches

Claimability, ordering, and discount counts are database facts. In-memory or Redis
structures may accelerate reads or notification, but are disposable and rebuildable
from SQLite. A cache pop does not claim a round. The transactional conditional
update does.

### Deadlines and background work

There may be separate schedulers per game or lifecycle. A scheduler discovers due
rows and calls the owning transition command; it does not maintain a second version
of transition logic.

Deadline commands compare expected status/version/deadline inside the transaction.
They are idempotent and stale-safe: repeating an expiry, refund, finalization, or
AI-fill command cannot duplicate money or ownership.

Slow AI/network work happens outside the write transaction. Persist an intent/job,
perform the external work, then submit its result through the same validated command
with a stale-state check.

### Pure rules

Scoring, pricing, eligibility, payout allocation, phrase matching, and state-machine
decisions are pure functions where practical. Pass clocks and seeded randomness as
inputs. Pure rules do not import FastAPI, SQLAlchemy, browser APIs, or wall-clock
globals.

### Frontends

The four SPAs render server state and submit commands. Shared code belongs in
`frontend/crowdcraft`; game folders contain routes, assets, and game-specific UI.

In the target deployment, an absent production API override means the current
origin. Do not use `VITE_API_URL=''` with an `||` fallback. WebSocket origin also
derives from `window.location`. The validated host selects the game; clients cannot
use another game's prefix on that host. HttpOnly cookies remain host-only and tokens
never move to local storage.

## Protocol and privacy

ORM models are not a wire format. Every normal response, WebSocket event, dashboard
projection, and reconnect snapshot has an explicit Pydantic schema.

Before finalization, do not disclose:

- authorship or contributor relationships;
- the prompt hidden from a copy player;
- which entry is the original;
- stable internal IDs or ordering that allow those facts to be correlated;
- other players' private identity or balance data beyond the screen's requirement;
- lifecycle/queue bookkeeping.

Use actor-scoped opaque assignment tokens when a client must reference a hidden
resource later. Disclosure tests assert forbidden fields are absent.

## Money

Wallet/vault columns may be cached balances, but every movement has one ledger row
and both update in the same transaction. Each logical movement has a unique
idempotency key. Finalization owns prize distribution. Reconciliation tests compare
cached balances with ledger history and prove retries do not double-move funds.

## Migration discipline

- Use Alembic; do not edit an applied migration.
- Rehearse upgrades against a production-shaped copy and test downgrade/restore
  where rollback depends on it.
- Add data cleanup before a new constraint, then prove the constraint rejects the
  old invalid state.
- Back up before release migration and stop if integrity checks fail.
- Treat table rebuilds, foreign-key changes, and lifecycle/economy columns as
  high-risk.

## Review questions

Before merging a gameplay change, answer:

1. Which server command owns the transition?
2. What conditional update or constraint chooses the single winner?
3. What happens on duplicate, concurrent, late, and stale calls?
4. Which deadline and reconnect state is preserved?
5. Which idempotency key protects each money movement?
6. Which fields are forbidden before finalization?
7. Can the rule run under a fake clock and seeded RNG?
8. Which deterministic, multi-connection SQLite, smoke, and browser checks prove it?

## Non-negotiable invariants

- The server owns lifecycle and economy decisions.
- SQLite is durable truth; queues and locks are rebuildable coordination.
- Exactly one worker serves the SQLite production database.
- Conditional updates, constraints, and idempotency keys make invalid states
  uncommittable.
- Deadline commands are idempotent and stale-safe.
- Reconnect restores assignments, votes, allowances, counters, and deadlines.
- Internal models are never serialized and hidden relationships stay private.
- Core rules remain testable without HTTP, a real server, or wall-clock time.
