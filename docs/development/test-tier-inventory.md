# Test Tier Inventory

> **Owner:** Platform engineering
> **Runtime budgets:** deterministic 5 minutes, SQLite integration 3 minutes,
> smoke 10 minutes, stress 20 minutes, external 10 minutes.

Pytest assigns one tier and one owner marker to every collected test in
`tests/conftest.py`. Marker registration is strict, so misspelled or undeclared
tiers fail collection.

| Match | Tier | Owner |
| --- | --- | --- |
| `tests/sqlite_integration/**` | `sqlite_integration` | Platform unless explicitly marked |
| `tests/test_stress_localhost.py` | `stress`, `localhost` | QuipFlip |
| `tests/test_*localhost*.py` | `smoke`, `localhost` | QuipFlip |
| `tests/test_tl_similarity_debug.py` | `external` | ThinkLink |
| Explicit `external` marker | `external` | Explicit subsystem marker |
| `tests/party/**`, `test_*party*.py` | `deterministic` | Party |
| `test_mm_*.py` | `deterministic` | MemeMint |
| `test_ir_*.py` | `deterministic` | Initial Reaction |
| `test_tl_*.py` | `deterministic` | ThinkLink |
| Shared database/config/cache/tooling files listed in `tests/conftest.py` | `deterministic` | Platform |
| Remaining tests | `deterministic` | QuipFlip |

The deterministic tier blocks socket connections, seeds Python randomness from
`CROWDCRAFT_TEST_SEED`, uses a per-run temporary SQLite file, and resets queue,
lock, validator, cache, and ThinkLink service singletons between tests.

Known environment-dependent behavior:

- Localhost suites use real HTTP and wall-clock sleeps.
- The stress suite uses threads, real HTTP, and randomized generated input.
- AI provider tests mock the provider boundary; live provider checks belong in
  the explicit `external` tier and require credentials.
- SQLite integration uses real file locks and multiple independent connections.

Canonical commands are documented in the root `README.md` and exposed by
`scripts/verify.py`.

## Current deterministic failure families

Two isolated runs on 2026-06-22 produced the same 69 failing node IDs:
329 passed, 67 failed, 2 errored, 10 skipped, and 58 environment-tier tests
deselected. These are recorded as product/test-contract work, not accepted
snapshots:

- QF lifecycle and queue tests that construct states now rejected by enforced
  foreign keys or current service preconditions.
- Cleanup tests that intentionally create orphan rows, which SQLite now rejects
  at insertion time.
- Initial Reaction service tests written against pre-unification auth, wallet,
  and transaction APIs.
- AI tests whose provider mocks or service signatures have drifted.
- Scoring, guest lockout, rate-limit, stale-content, statistics, and timezone
  expectation mismatches.

Workstreams B-E own the gameplay and lifecycle corrections. Workstream A keeps
the failures isolated and reproducible without weakening foreign keys or adding
retries.
