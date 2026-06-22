# Backend Instructions

The FastAPI backend is authoritative for all four games. See
[codebase organization](../docs/development/codebase-organization.md) for the full
layering rules. Highlights:

- **Routers are thin adapters.** A router handler should: authenticate/resolve the
  player, validate the request body with Pydantic, call **one** service command,
  and translate the result into a response schema or error. Do not implement
  lifecycle, scoring, or queue logic inside route handlers.
- **One transactional command per transition.** Round/phraseset/party-round
  transitions live in the service layer. A command conditionally mutates the
  expected status/version, verifies one winner, writes related ledger state, and
  commits atomically. Never duplicate transition logic in an endpoint, job, or
  cleanup script.
- **SQLite constraints are the correctness boundary.** Use compare-and-swap updates,
  unique/check constraints, and idempotency keys. `FOR UPDATE` is ineffective on
  SQLite. Keyed `asyncio.Lock` coordination may reduce contention but does not prove
  correctness. Never hold a synchronous thread/Redis lock across `await`.
- **Deadlines are server-side.** Schedulers may discover due rows per lifecycle, but
  they call the same owning transition commands. The grace period is a backend
  concept.
- **Finalizers are idempotent.** A timeout/finalization that runs after the state
  already advanced must be a no-op; it must not double-refund, double-pay, or
  re-queue.
- **Money is a ledger.** Route every flipcoin change through a uniquely keyed ledger
  write in the same transaction as cached balances and lifecycle state.
- **Never serialize ORM models.** Return explicit Pydantic response schemas. Before
  finalization, never disclose authorship, the originating prompt to a copy player,
  or which phrase/entry is the original to a voter.
- **Migrations:** use Alembic; review for data-loss and orphaning; never edit
  applied migrations. Adding/altering lifecycle columns is a high-risk change.
- Keep scoring, pricing (copy discount), eligibility, and prize distribution in
  **pure functions** so they can be unit-tested with seeded inputs and a fake clock.
- Pass clocks and randomness as dependencies in new lifecycle/scoring code rather
  than reading wall-clock time or `random` directly.

Production SQLite enables foreign keys, WAL, and a bounded busy timeout and runs
under exactly one Uvicorn worker. Background cycles (`ai_backup_cycle`,
`ai_stale_handler_cycle`, `cleanup_cycle`, `party_maintenance_cycle`) discover work
and invoke the same transactional commands as user actions.
