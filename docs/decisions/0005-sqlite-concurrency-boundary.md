# SQLite-Enforced Concurrency with One Worker

## Status

Accepted.

## Context

The current lock helper uses synchronous Redis or thread locks from async service
methods. Candidate selection can occur before a resource-level critical section.
One worker removes cross-process races but does not protect against retries,
maintenance tools, process restarts, or an expired coordination lease.

## Decision

SQLite transactions and constraints are the correctness boundary. Lifecycle
commands use status/version compare-and-swap updates, unique/check constraints, and
idempotency keys. Use short `BEGIN IMMEDIATE` transactions only where a conditional
update cannot express the invariant.

The Mac deployment runs exactly one Uvicorn worker. Keyed `asyncio.Lock` instances
may reduce same-process contention, but correctness cannot depend on them. Redis is
not required for the target deployment and no lifecycle fact may exist only in a
queue or cache.

## Consequences

Async code does not hold synchronous thread/Redis locks across `await`. Concurrency
tests use multiple SQLite connections configured like production and prove one
winner, bounded busy handling, and safe retry. Readiness verifies the expected
database mode and migration revision.

## Rejected alternatives

Multiple workers; Redis locks as the only integrity defense; one worker as the only
integrity defense; relying on `FOR UPDATE` under SQLite.

## Conditions for revisiting

If measured write contention requires multiple workers, revisit the database choice
before scaling. Do not add workers while SQLite remains the single-writer store.
