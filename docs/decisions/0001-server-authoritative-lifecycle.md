# Server-Authoritative Lifecycle

## Status

Accepted.

## Context

Clients can disconnect, race, retry, and observe different private information.
Lifecycle state is currently mutated by REST endpoints, background cycles, and
repair tools, producing orphaned or double-claimed state.

## Decision

The server owns lifecycle, eligibility, pricing, assignment, vote validity,
scoring, finalization, and deadlines. Each transition has exactly one service
command. The command opens a SQLite transaction, performs a conditional mutation
against the expected status/version, re-validates the precondition, writes state
and ledger changes, and commits atomically.

Clients render projections and submit validated commands. Client timers and counts
are display-only. A scheduler may discover due rows, but it advances them only by
calling the owning transition command.

## Consequences

Stale commands and stale deadline jobs are no-ops. Process-local async locks may
reduce contention, but SQLite constraints, compare-and-swap updates, and idempotency
keys remain correct after retries or restarts. Reconnect restores existing server
state.

## Rejected alternatives

Client-driven progression; independent mutation paths for endpoints and jobs;
trusting a precondition checked before the transaction; treating one worker or a
process lock as the integrity boundary.

## Conditions for revisiting

Only if a different authority model preserves anti-cheat, money integrity, private
information, reconnect behavior, and deterministic transition guarantees.
