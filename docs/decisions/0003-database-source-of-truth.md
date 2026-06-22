# SQLite as the Durable Source of Truth

## Status

Accepted. SQLite-only Mac deployment decided 2026-06-22.

## Context

Crowdcraft games are asynchronous: assignments and the economy must survive server
restarts and players return across sessions. In-memory room state or Redis lists
cannot be authoritative. The target is one Mac and one application worker, and the
maintainer has chosen SQLite rather than local Postgres.

## Decision

SQLite is the source of truth for lifecycle, claimability, pricing inputs, the
economy, and Party sessions. Every connection enables foreign keys and
`busy_timeout=5000`; production uses WAL with `synchronous=FULL`. Lifecycle
commands use conditional status/version updates, constraints, and short write
transactions because SQLite does not provide useful `SELECT ... FOR UPDATE`
semantics.

In-memory queues and locks are rebuildable accelerators only. Restarting the process
cannot lose durable work or change pricing. The database, WAL, and backups live
outside the repository.

## Consequences

The deployment runs exactly one Uvicorn worker. Tests run the complete Alembic chain
and multi-connection contention scenarios against a temporary SQLite file with the
production pragmas. Release and recovery procedures include backup, integrity
check, restore rehearsal, disk monitoring, and bounded handling of `database is
locked` failures.

## Rejected alternatives

In-memory/Redis authority; local or remote Postgres; SQLite without foreign-key or
contention configuration; event sourcing.

## Conditions for revisiting

Revisit if write contention, data volume, availability requirements, or the need for
multiple workers exceeds the measured SQLite envelope. Migration requires a tested
export/import and rollback plan.
