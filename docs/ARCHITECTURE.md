# Current Architecture

> **Document type:** Implementation reference
> **Status:** Current snapshot with known gaps
> **Last reviewed:** 2026-06-22

This document describes the code that exists today. The
[transition plan](transition-plan.md) and
[codebase guide](development/codebase-organization.md) describe the target.

## System shape

One async FastAPI application serves four game APIs:

| Game | API prefix | Frontend |
| --- | --- | --- |
| QuipFlip | `/qf` | `frontend/qf` |
| MemeMint | `/mm` | `frontend/mm` |
| Initial Reaction | `/ir` | `frontend/ir` |
| ThinkLink | `/tl` | `frontend/tl` |

The React/Vite frontends import shared contexts, hooks, components, types, and API
clients from `frontend/crowdcraft`. QuipFlip also exposes notification, online-user,
and Party WebSocket channels.

## Backend

`backend/main.py` configures logging, CORS, request middleware, routers, and lifespan
work. Startup currently:

- initializes the local phrase validator;
- synchronizes QuipFlip prompts and quests;
- imports MemeMint images/captions;
- seeds and cleans ThinkLink prompts/answers; and
- starts AI backup, stale-AI, token cleanup, and Party maintenance loops.

Several startup actions mutate data. The target deployment moves release/migration
work out of readiness-critical startup and distinguishes `/livez` from `/readyz`.
The current `/health` endpoint checks the database and queue backend, but its
database-failure tuple does not reliably set HTTP 503 and must not yet gate releases.

Routers live under `backend/routers`; services under `backend/services`; SQLAlchemy
models under `backend/models`; Pydantic wire schemas under `backend/schemas`; and
Alembic migrations under `backend/migrations`.

## Persistence and concurrency

The code supports Postgres through `asyncpg` and SQLite through `aiosqlite`. Local
development/tests default to `crowdcraft.db`; the legacy Heroku deployment uses
Postgres. The accepted Mac target is SQLite-only with exactly one Uvicorn worker.

Current lifecycle correctness is incomplete:

- `QueueClient` stores FIFO data in Redis or process memory separately from the
  database.
- `LockClient` uses synchronous Redis/thread locks, including inside async service
  methods.
- some candidate selection happens before a resource-level critical section;
- SQLite connections do not yet uniformly enable foreign keys, WAL, and busy
  timeout;
- several services use `.with_for_update()`, which does not provide the intended
  row-locking guarantee on SQLite; and
- transaction rows do not have one general idempotency key for every logical money
  movement.

Accordingly, current locks and queues should not be described as preventing double
claims. The target uses SQLite conditional updates, constraints, short transactions,
and idempotency keys; queues/async locks become rebuildable coordination.

## Authentication and transport

The unified `players` table owns account identity; per-game player-data tables own
wallet/vault/tutorial fields. JWT access and refresh tokens are stored in HttpOnly,
host-only cookies. QF/MM/TL reuse shared auth routes; IR has game-specific auth
surfaces.

WebSockets mint short-lived tokens through `/auth/ws-token` variants, then pass the
token in the WebSocket query string. QF channels are documented in
[WEBSOCKET.md](WEBSOCKET.md).

The shared frontend client currently defaults to `http://localhost:8000` when
`VITE_API_URL` is falsy, and the shared WebSocket hook falls back to the Heroku host.
The same-origin target therefore requires code changes; setting an empty environment
value is insufficient.

## Game flows

### QuipFlip

Solo play is quip/prompt → two impostor/copy submissions → vote → finalization and
payout. Durable state spans QF rounds, phrasesets, votes, result views, player data,
and transaction rows. Process/Redis queues accelerate prompt/phraseset assignment.

Party Mode uses `PartySession`, `PartyParticipant`, `PartyRound`, and
`PartyPhraseset` plus large session, coordination, scoring, and WebSocket services.
Actions are REST commands; sockets deliver presence/progress. The current atomic
phase-advance path contains a sync/async lock mismatch and lacks direct coverage.

### MemeMint

Players vote among captions and submit captions/riffs for images. Circles add social
membership workflows. Caption author integrity and vote/caption money movements are
high-risk lifecycle boundaries.

### Initial Reaction

Backronym sets collect entries, move to voting, and finalize payouts. The 2026-06-22
baseline includes IR model/transaction test failures and a failing frontend build;
the other three frontend builds pass when run independently.

### ThinkLink

Players submit guesses against prompt answer clusters with scoring and transaction
state. It is the newest flow and has substantial historical implementation notes;
current rules take precedence over those plans.

## Verification state

There is no single root gate. Pytest's default collection currently mixes
deterministic tests with localhost/stress suites. The legacy CI runs a hand-selected
backend list, uses Python 3.11, and omits the IR frontend job. See the transition
plan for exact dated results and the required tier split.
