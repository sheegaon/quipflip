# Testing Strategy

> **Document type:** Engineering guidance
> **Status:** Active target
> **Audience:** Maintainers and contributors

Choose the lowest layer that proves the claim and keep environment-dependent tests
out of the deterministic gate.

## Test tiers

| Claim | Required tier |
| --- | --- |
| Scoring, pricing, eligibility, payout allocation | Pure unit/property test |
| Request validation and private response shape | Contract/disclosure test |
| One command changes lifecycle state | SQLite service integration |
| Concurrent claims produce one winner | Multi-connection production-SQLite integration |
| Foreign keys/checks/uniqueness reject invalid state | Migration/schema integration |
| Deadline retry is stale-safe; reconnect restores state | Fake-clock lifecycle integration |
| Alembic upgrades a production-shaped database | Migration-chain test plus restore rehearsal |
| Built API, static assets, cookies, and WebSockets work | Smoke |
| Touch/mobile layout works | Browser |
| Capacity and busy-timeout envelope are acceptable | Explicit stress/load tier |

## Deterministic `verify`

The default pytest collection must not require localhost, network access, wall-clock
sleeps, production credentials, or external AI providers. Mark and exclude
`*_localhost*` and stress tests from this tier instead of letting a closed port
produce dozens of setup errors.

Each run uses an isolated temporary database and resets settings caches, queue
singletons, validator state, random seeds, and fake clocks. Print seeds on failure.
SQLite connections enable foreign keys. Mock AI at the provider boundary and forbid
unexpected network calls.

The root gate also lints/typechecks/builds the shared library and all four frontends,
runs secret scanning, and checks formatting. A chained frontend command must report
which app failed; it must not imply later apps ran.

## Production-SQLite integration

Run a separate tier against a temporary file configured like production: WAL,
foreign keys, `busy_timeout=5000`, and `synchronous=FULL`. Use multiple
connections to test:

- two players claiming the same assignment;
- duplicate command/idempotency keys;
- timeout versus submit/finalize races;
- payout/refund retry;
- process/queue reconstruction after restart;
- bounded busy handling and retry;
- backup, integrity check, migration, and restore.

Do not use `.with_for_update()` as evidence under SQLite. Assert the conditional
update row count and final database invariants.

## Privacy and money

Every pre-finalization response and reconnect snapshot asserts both required fields
and forbidden-field absence. Test canonical IDs/order and cross-response correlation,
not only obvious author-name fields.

For money, prove:

- one ledger row per logical movement;
- a duplicate key cannot move wallet/vault twice;
- cached balances reconcile with ledger history;
- finalizing an already-finalized object is a no-op;
- state and ledger changes roll back together.

## State-machine coverage

Generate seeded sequences containing start, submit, duplicate submit, concurrent
claim, timeout, stale timeout, reconnect, AI result, and clock advancement. Assert
continuously that ownership is unique, contributor voting is excluded, hidden fields
remain absent, and stale work cannot reset or re-pay state.

## Smoke, browser, and stress

The smoke runner boots the built server with a temporary production-configured
SQLite database and built static assets. It drives one complete loop per game plus a
QF Party flow over real REST/WebSocket transports, including restart and reconnect.

Browser checks prove rendered desktop/mobile behavior, deep-link fallback, same-
origin requests, cookies, and visible reconnect state. They do not replace rules
tests.

Stress tests are opt-in. Record the hardware, seed, concurrency, duration, SQLite
settings, busy/timeout count, and pass threshold. A stress test is not part of
default pytest collection.

## Current baseline

On 2026-06-22, full pytest collected localhost/stress suites and reported 355 passed,
44 failed, 90 errors, and 9 skipped. QF/MM built; IR failed TypeScript compilation.
TL passed when run independently. This section is evidence for Phase 1, not an
accepted permanent failure list. Update or remove it when the canonical gates are
green.
