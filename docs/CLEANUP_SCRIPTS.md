# Cleanup and Repair Tools

> **Document type:** Operational reference
> **Status:** Current repair tooling; not lifecycle architecture
> **Audience:** Maintainers

Cleanup scripts repair or remove already-invalid data. They are not a substitute for
foreign keys, conditional lifecycle commands, idempotency keys, or durable queue
state. The transition plan converts reproducible bug classes into regression tests
and keeps only guarded repair operations under `scripts/ops/`.

## Current entry points

- `run_cleanup.py` — wrapper around `QFCleanupService` tasks.
- `cleanup_test_players.py` — anonymizes matching test accounts and removes selected
  non-essential data.
- `cleanup_orphaned_rounds.py` — reports or removes rounds whose player is missing.
- `fix_orphaned_captions.py` and `debug_copy_availability.py` — symptom-specific
  tools that should become tests or guarded repair commands.

`backend.main` also starts hourly token/guest cleanup and Party maintenance. Any job
that changes gameplay lifecycle state must call the same transactional command as a
user request; cleanup code must not invent a second transition path.

## Safe procedure

1. Read the script and service implementation.
2. Stop or quiesce application writers.
3. Check free disk, checkpoint WAL, create a verified SQLite backup with the online
   backup API, and record its path.
4. Run the narrowest available dry-run/report mode.
5. Review row counts and sample identifiers without exposing player data.
6. Run the targeted repair without `--yes` on first use.
7. Run foreign-key/integrity checks, ledger reconciliation, and the affected smoke
   flow.
8. Preserve the backup through the soak window and record the repair result.

Never copy only the SQLite main file while WAL writes may be pending. Never run a
destructive repair concurrently with the server.

## Current commands

Inspect each script's `--help` before use. Typical report-first commands are:

```bash
.venv/bin/python run_cleanup.py --dry-run
.venv/bin/python cleanup_orphaned_rounds.py --dry-run
.venv/bin/python cleanup_test_players.py --list
```

Do not add these commands to cron or launchd as a correctness mechanism. Scheduled
token retention is operational cleanup; orphan/assignment/payout repair indicates a
bug that needs a permanent test and invariant.

## Retirement criteria

A symptom-specific script can be removed when:

- the invalid state has a failing-then-passing regression test;
- the database or transactional command prevents recurrence;
- existing production data has been repaired and verified; and
- no documented rollback/recovery procedure still needs the tool.
