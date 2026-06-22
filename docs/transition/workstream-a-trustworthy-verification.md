# Workstream A - Trustworthy Verification

> **Document type:** Implementation plan
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Produce deterministic, production-representative verification gates that separate
fast repository checks from SQLite integration, built-server smoke, stress, and
external environment tests.

## Starting point

The 2026-06-22 baseline had 355 passing, 44 failing, 90 erroring, and 9 skipped
backend tests. Default collection included suites requiring a server on port 8000.
QuipFlip, MemeMint, and ThinkLink built; Initial Reaction failed TypeScript
compilation. CI used Python 3.11, omitted IR, and did not provide one canonical
gate.

## Dependencies and boundaries

- This workstream is the first delivery gate and can start immediately.
- It may expose product defects but should not silently redefine game behavior to
  make the gate green.
- Lifecycle fixes discovered here belong in workstreams B-E unless required only
  for deterministic isolation.
- Follow the [testing strategy](../development/testing-strategy.md) and
  [dependency policy](../development/dependency-policy.md).

## Repository anchors and gotchas (verified 2026-06-22)

Concrete current state so an implementer does not rediscover it:

- **CI does not run the whole collection.** `.github/workflows/testing.yml`
  enumerates ~30 specific files (lines 42-71) instead of running `pytest`. That is
  why `*_localhost` and stress suites pass CI today: they are never invoked. It also
  means files such as `test_ai_service.py`, `test_stale_ai_service.py`,
  `test_rate_limiting.py`, `test_phraseset_service.py`, and `test_ai_player_pooling.py`
  run nowhere. The `verify` gate must be a marker-filtered collection, not a
  hand-maintained file list, or A2's isolation gains can be silently bypassed.
- **The version gap is Python, not Node.** CI runs Python 3.11 while `AGENTS.md` and
  local dev use 3.12; CI already runs Node 22, which satisfies the "Node.js 20+"
  floor (see the A6 correction below).
- **CI has QF/MM/TL frontend jobs but none for IR** (`testing.yml`). A5/A6 must add
  the IR job, not only fix its build.
- **No aggregate frontend build exists.** `package.json` has only per-app
  `build:qf|mm|ir|tl` (plus `build:crowdcraft`), and `install:all` uses
  `npm install --workspaces`, not `npm ci`. A5's "earlier chained build fails"
  describes a command that does not exist yet; A5/A6 must create the aggregate build
  and ensure it does not stop at the first failing app.
- **Isolation today is shared, not per-run.** `tests/conftest.py` sets
  `os.environ["DATABASE_URL"]` at import (line 12), then a session-scoped autouse
  fixture runs `alembic upgrade head` once against that single `test.db`, and
  `test_engine` is session-scoped. There is no per-test database and no reset of
  `queue_client`, caches, validator, clock, or settings singletons. A2 must replace
  the import-time env mutation and the session-scoped engine.
- **`tests/test_migration_chain.py` already exists** — extend it for the
  production-pragma file database in A4 rather than starting fresh.
- **A localhost tier already has tooling**: `run_localhost_tests.py`,
  `run_localhost_tests.sh`, and `tests/{README_LOCALHOST_TESTS,QUICK_START_TESTS,TROUBLESHOOTING_TESTS}.md`.
  A1 should classify these, not re-document them.
- **Playwright infra already exists** (`playwright.config.ts`, `tests/e2e/`,
  `playwright-report/`). Reconcile the new built-server `smoke` gate with it instead
  of adding a parallel browser harness.
- **No SQLite pragmas are set anywhere** (see workstream B). A3/A4 are net-new
  connection configuration, and enabling `foreign_keys=ON` will begin enforcing many
  existing `ondelete=` rules, so sequence A3 with B2's cleanup queries.

## Phase A1 - Define test tiers

- [ ] Inventory every backend test by deterministic, SQLite integration, smoke,
      stress, or external tier.
- [ ] Identify tests that perform network access, use wall-clock sleeps, share
      module state, or require a running server.
- [ ] Record the current IR TypeScript failures and all backend failure families
      without converting individual stack traces into permanent acceptance rules.
- [ ] Define canonical names and expected runtime budgets for each tier.
- [ ] Confirm the deterministic tier can run with no credentials or external
      services.

Gate:

- [ ] Every collected test has one documented tier and one owning subsystem.

## Phase A2 - Isolate the deterministic backend gate

- [ ] Register strict pytest markers for non-default tiers.
- [ ] Exclude localhost, stress, and external tests from the default gate.
- [ ] Replace shared database paths with per-run temporary databases.
- [ ] Reset queue clients, settings, validators, clocks, AI mocks, and other
      process-global state between tests.
- [ ] Block unexpected network access in the deterministic tier.
- [ ] Replace timing-sensitive waits with injected clocks or bounded polling.
- [ ] Make random behavior seeded and reproducible.
- [ ] Add a regression proving the default gate succeeds when port 8000 is closed.

Gate:

- [ ] Two consecutive deterministic backend runs produce the same result.

## Phase A3 - Enforce SQLite integrity

- [ ] Enable `foreign_keys=ON` on every SQLite connection and test enforcement.
- [ ] Prove application, migration, test, and operational-script connections all
      reject invalid foreign-key writes.

Gate:

- [ ] Foreign-key enforcement is enabled and tested on every SQLite connection
      path.

## Phase A4 - Production-shaped SQLite verification

- [ ] Configure file-backed integration databases with WAL,
      `busy_timeout=5000`, and `synchronous=FULL`.
- [ ] Run the complete Alembic upgrade chain against a fresh temporary database.
- [ ] Test multiple-connection compare-and-swap winners and losers.
- [ ] Test bounded busy handling and rollback after interrupted writes.
- [ ] Test process restart with queues/caches rebuilt from durable rows.
- [ ] Add backup, integrity-check, restore, and post-restore query verification.
- [ ] Keep production-SQLite tests separate from the fast deterministic gate.

Gate:

- [ ] The named SQLite integration command passes against a temporary file using
      production pragmas.

## Phase A5 - Frontend gates

- [ ] Fix Initial Reaction model/type drift without weakening type checks.
- [ ] Define shared-library lint and typecheck coverage.
- [ ] Add root commands that lint, typecheck, and build QF, MM, IR, and TL.
- [ ] Use `npm ci` and the committed lockfile in CI.
- [ ] Ensure game builds cannot be skipped because an earlier chained build fails.
- [ ] Add focused tests for shared API/WebSocket origin behavior before workstream
      F changes deployment defaults.

Gate:

- [ ] All four production builds and the shared-library checks pass from a clean
      install.

## Phase A6 - Canonical commands and CI

- [ ] Add one deterministic `verify` entry point.
- [ ] Add separately named `test:sqlite-integration` and `smoke` entry points.
- [ ] Move CI from Python 3.11 to 3.12 (the version `AGENTS.md` requires and local
      dev already uses). Keep Node on the `AGENTS.md` floor of 20+; CI already runs
      Node 22, so this is not a Node downgrade.
- [ ] Pin third-party actions to immutable commit SHAs.
- [ ] Set minimal workflow permissions, concurrency cancellation, and job timeouts.
- [ ] Add secret scanning, npm audit, and Python dependency audit gates with
      documented exception handling.
- [ ] Upload useful failure artifacts without credentials, tokens, or player data.
- [ ] Document exact local and CI commands in the root entry points.

Gate:

- [ ] A clean checkout can run the documented deterministic command, while SQLite
      integration and smoke remain explicit separate gates.

## Required verification

- [ ] Run the deterministic gate twice.
- [ ] Run the production-shaped SQLite integration gate.
- [ ] Run all four frontend production builds.
- [ ] Run `git diff --check` and inspect the complete CI/configuration diff.
- [ ] Obtain independent CI/security review for workflow and dependency changes.

## Exit criteria

- [ ] Failures are reproducible and assigned to the correct tier.
- [ ] Default verification has no hidden server, network, or credential dependency.
- [ ] SQLite integration exercises the selected production concurrency model.
- [ ] CI and local commands use the same supported runtime versions.

## Non-goals

- Fixing every gameplay lifecycle defect exposed by the new gate.
- Folding stress or live-production checks into deterministic verification.
- Adding test retries to conceal nondeterminism.
