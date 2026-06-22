# Workstream B - Lifecycle Inventory and Database Invariants

> **Document type:** Implementation plan
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Make SQLite constraints, conditional transitions, and idempotency keys the
correctness boundary for QF solo, QF Party, MM, IR, and TL, with one owning command
for every lifecycle transition.

## Starting point

The database is intended to be authoritative, but queue mutations can diverge from
database commits, synchronous locks are used in async paths, SQLite foreign keys
are not consistently enabled in tests, and ledger rows lack a general uniqueness
key for retry-safe money movement.

## Dependencies and boundaries

- Phase B1 inventory can run alongside workstream A.
- Schema migrations and concurrency tests depend on A's production-shaped SQLite
  harness.
- Game-specific behavior changes are delivered through workstreams C-E.
- This plan defines shared invariants; canonical game rules still define intended
  scoring, eligibility, and economy.

## Repository anchors and gotchas (verified 2026-06-22)

- **An idempotent-collection pattern already exists; copy it for money.**
  `backend/models/qf/result_view.py` is titled "Result view tracking for idempotent
  prize collection" and carries
  `UniqueConstraint('player_id','phraseset_id', name='uq_player_phraseset_result')`;
  IR has `uq_ir_result_view_player_set`. The real gap (roadmap finding 5) is the
  *ledger*: `backend/models/qf/transaction.py` (`qf_transactions`) has only
  `ix_transactions_player_created` and no idempotency key. Extend the existing
  pattern rather than inventing one.
- **There is no centralized pragma hook.** `backend/database.py` configures only
  pool/SSL settings; add pragmas via `event.listens_for(engine.sync_engine, "connect")`.
  SQLite uses NullPool (database.py:80), so the hook must run on each new connection.
- **FK actions are declared but unenforced.** QF models alone declare `ondelete=` on
  many tables (`qf_transactions`, notifications, party rounds, flagged prompts, etc.),
  but with `foreign_keys=ON` never set, SQLite ignores them today. B2's cleanup
  queries must run *before* the pragma is enabled, or previously tolerated orphans
  will start rejecting writes and cascade deletes will begin firing.
- **The concrete async-lock defect (B4) is `backend/services/qf/party_session_service.py:959`**:
  `async with lock_client.lock(...)` against the synchronous `@contextmanager` in
  `backend/utils/lock_client.py` raises `AttributeError`. Synchronous
  `with lock_client.lock(...)` also appears in `backend/services/qf/round_service.py`
  (lines 92, 375, 869, 1170) and `vote_service.py:428`, blocking the event loop.
  (Shared with workstream D.)
- **These invariants implement existing ADRs**:
  [0001 server-authoritative lifecycle](../decisions/0001-server-authoritative-lifecycle.md)
  (B5), [0002 private response projection](../decisions/0002-private-response-projection.md)
  (cross-cutting), [0003 database source of truth](../decisions/0003-database-source-of-truth.md)
  (B3), and [0005 SQLite-enforced concurrency](../decisions/0005-sqlite-concurrency-boundary.md)
  (B2/B4). Cite them in migration and review notes.

## Phase B1 - State-machine inventory

- [ ] Create one state-machine page for QF solo.
- [ ] Create one state-machine page for QF Party.
- [ ] Create one state-machine page for MemeMint.
- [ ] Create one state-machine page for Initial Reaction.
- [ ] Create one state-machine page for ThinkLink.
- [ ] For every state, record valid commands, actors, preconditions, deadlines,
      money movements, and next states.
- [ ] Inventory every router, worker, scheduler, WebSocket handler, startup hook,
      admin action, and repair script that mutates lifecycle state.
- [ ] Inventory every normal and reconnect projection plus forbidden
      pre-finalization fields.
- [ ] Mark code observations, rule-document intent, and unresolved hypotheses
      separately.
- [ ] Resolve conflicting transition ownership before implementation.

Gate:

- [ ] Every lifecycle mutation caller maps to one intended owning command.

## Phase B2 - Schema and SQLite invariants

- [ ] Define lifecycle status/check constraints for each aggregate.
- [ ] Define required foreign-key actions and orphan prevention.
- [ ] Define uniqueness for active assignments, claims, votes, result collection,
      and other single-winner relationships.
- [ ] Add lifecycle version columns where status alone cannot reject stale commands.
- [ ] Define a stable idempotency-key format and uniqueness scope for ledger
      movements and retriable public commands.
- [ ] Write cleanup queries for existing rows that violate proposed constraints.
- [ ] Decide migration ordering, rollback behavior, and data-retention impact.
- [ ] Rehearse migrations against a production-shaped backup before merge.

Gate:

- [ ] The migration plan explains how every pre-existing invalid row is detected,
      repaired, rejected, or deliberately retained.

### SQLite correctness boundary

- [ ] Centralize SQLite connection pragmas for application, tests, migrations, and
      operational scripts.
- [ ] Implement conditional status/version updates and verify exactly one winner.
- [ ] Use short `BEGIN IMMEDIATE` transactions only where constraints and
      compare-and-swap cannot represent the invariant.
- [ ] Remove reliance on `SELECT ... FOR UPDATE` for SQLite correctness.
- [ ] Add constraint tests that bypass process coordination.
- [ ] Add multi-connection tests for double claim, duplicate vote, stale deadline,
      and duplicate ledger movement.
- [ ] Add reconciliation tests between ledger history and cached balances.

Gate:

- [ ] Invalid ownership and duplicate money states are rejected when locks and
      queues are bypassed.

## Phase B3 - Remove queue authority

- [ ] Make claimability database-derived.
- [ ] Make copy availability and discount counts database-derived.
- [ ] Ensure a cache/queue pop cannot claim or price a round.
- [ ] Make all in-memory and Redis queue state rebuildable after restart.
- [ ] Add restart tests proving no claimable work or economy fact is lost.
- [ ] Remove superseded queue code after all callers migrate.

Gate:

- [ ] Restarting without queue state preserves lifecycle ownership, eligibility,
      and pricing.

## Phase B4 - Async-safe coordination

- [ ] Replace synchronous Redis/thread locks held across `await`.
- [ ] Use keyed async coordination only as a contention optimization.
- [ ] Keep database conditional updates and constraints as the integrity boundary.
- [ ] Add contention tests with process coordination disabled.
- [ ] Remove superseded lock code after all callers migrate.

Gate:

- [ ] Concurrent commands remain correct without Redis, thread locks, or
      same-process async coordination.

## Phase B5 - One command per transition

- [ ] Implement a named command for each inventoried transition.
- [ ] Revalidate actor, expected status/version, deadline, and ownership inside the
      transaction.
- [ ] Write lifecycle rows, ledger movements, and durable job/outbox intent in the
      same transaction.
- [ ] Move AI/network calls outside write transactions.
- [ ] Route REST endpoints through the owning commands.
- [ ] Route deadline and cleanup jobs through the same commands.
- [ ] Route AI result submission and Party orchestration through the same commands.
- [ ] Make duplicate, concurrent, late, and stale command results explicit.
- [ ] Delete alternative mutation paths after callers migrate.

Gate:

- [ ] The mutation inventory has exactly one live owner for every transition.

## Cross-cutting phase - Explicit private projections

- [ ] Replace internal-model serialization with explicit response schemas.
- [ ] Define actor-scoped opaque assignment tokens where clients need hidden
      references.
- [ ] Add negative assertions for authorship, hidden prompts, original-entry
      identity, internal IDs, and other correlatable relationships.
- [ ] Cover normal responses, dashboards, notifications, WebSocket events, and
      reconnect snapshots.
- [ ] Version any unavoidable protocol break and migrate all four clients.

Gate:

- [ ] Pre-finalization disclosure tests pass for every game and transport.

## Required verification

- [ ] Run migration rehearsal against a production-shaped database copy.
- [ ] Run deterministic pure-rule and command tests.
- [ ] Run multi-connection SQLite constraint and concurrency tests.
- [ ] Run ledger reconciliation and duplicate-command tests.
- [ ] Run game smoke loops affected by each command migration.
- [ ] Obtain independent concurrency/lifecycle review.
- [ ] Obtain independent money and disclosure reviews where applicable.

## Exit criteria

- [ ] Database constraints and conditional updates select every single winner.
- [ ] Ledger movement retries are idempotent.
- [ ] Queues and locks can disappear without corrupting durable state.
- [ ] Every transition has one command owner and every projection has an explicit
      schema.

## Non-goals

- Replacing SQLite with another database.
- Treating a single worker or Redis lease as an integrity guarantee.
- Changing game economy or rules without a separately approved rule change.
