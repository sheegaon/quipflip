# Test Instructions

See [testing strategy](../docs/development/testing-strategy.md) for which layer
proves which claim. Core rules:

- **Prove each claim at the lowest useful layer.** Scoring, pricing, vote
  eligibility, and prize-pool distribution are pure-function unit tests with seeded
  inputs — do not prove them through slow integration or localhost HTTP tests.
- **Lifecycle transitions and races** are integration tests with a **fake clock**
  and, where concurrency matters, multiple SQLite connections configured with the
  production pragmas. Assert conditional-update row counts and final invariants; do
  not rely on `FOR UPDATE`.
  Cover: claim/finalize, timeout refund, double-claim attempt, duplicate
  submission, reconnect-restores-state, and stale finalizer is a no-op.
- **Disclosure is a security property.** For every response returned before
  finalization, assert both that required fields are present **and** that forbidden
  fields are absent (authorship, the prompt shown to a copy player, which phrase is
  the original to a voter).
- **Regression-first for the bug classes.** Orphaned rounds, copy-availability
  races, and orphaned captions each get a test that **fails on the bug** before the
  fix and stays as a permanent guard. Prefer converting the root-level
  `cleanup_*` / `debug_*` / `fix_*` scripts into such tests.
- **Determinism.** Tests use isolated temporary SQLite files with foreign keys
  enabled, no network, and no wall-clock dependence. Reset caches/singletons, inject
  clocks, and seed randomness; print the seed on failure. Mark and
  quarantine anything flaky rather than letting it erode the gate — and record why.
- The `*_localhost*` suites that require a running server are integration-tier; keep
  them separate from the deterministic `verify` set and document how to run them
  (`tests/README_LOCALHOST_TESTS.md`).

Stress tests are a separate opt-in tier. The production-SQLite integration tier
uses WAL, busy timeout, and multiple connections and covers backup/restore and
restart reconstruction.

A temporary reproduction must fail before a fix and should become a permanent
regression test whenever practical.
