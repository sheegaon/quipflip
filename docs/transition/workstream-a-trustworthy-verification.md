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
- [ ] Align CI with Python 3.12 and Node.js 20.
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
