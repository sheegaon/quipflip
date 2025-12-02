# Database Cleanup Scripts

This guide documents the cleanup tooling for QuipFlip data. All entrypoints share the same logic in `backend/services/qf/cleanup_service.py`, so scripts, scheduled tasks, and ad-hoc calls behave consistently.

## What the cleanup service actually does
- **Tokens:** Deletes orphaned refresh tokens (no player), expired/revoked tokens, and long-expired revoked tokens.
- **Rounds:** Deletes rounds whose players were removed, and also removes their prompt IDs from the in-memory queue.
- **Test players:** Finds known test/stress usernames/emails, anonymizes the accounts (preserves history), deletes non-essential data (votes, transactions, dailies, result views, feedback, phraseset activity, refresh tokens, quests), and clears queued prompt rounds that were never submitted. Submitted rounds are preserved to keep phrasesets intact.
- **Inactive guests:** Deletes guest accounts with zero activity older than a configurable horizon (default 1 hour).
- **Guest username recycling:** Reclaims old guest usernames (defaults to 30+ days) by appending `X`/`X2` suffixes so names can be reused while keeping canonical uniqueness.
- **Party sessions:** Calls `PartySessionService.cleanup_inactive_sessions()` to prune stale party participants/sessions.

> Default background schedule: `backend.main` starts `cleanup_cycle()` on app startup (hourly). The scheduled run **excludes test player cleanup**; run scripts manually for that.

## Available scripts

### Unified cleanup: `run_cleanup.py` (recommended)
Runs the same service methods used in the background task with optional flags.

```bash
# Safe defaults (tokens, orphaned rounds, inactive guests, username recycle, party cleanup)
python run_cleanup.py

# Preview only
python run_cleanup.py --dry-run

# Include test-player anonymization and associated deletions
python run_cleanup.py --all
python run_cleanup.py --all -y      # skip confirmation

# Narrow scope
python run_cleanup.py --test-players
python run_cleanup.py --orphaned-rounds
python run_cleanup.py --tokens

# Verbose output
python run_cleanup.py -v
```

Behavior notes:
- Without `--all` test-player cleanup is skipped.
- `--dry-run` reports counts without mutating data.
- `-y/--yes` bypasses interactive confirmations (useful for cron).

### Test player cleanup: `cleanup_test_players.py`
Anonymizes test/stress users and deletes their non-essential data.

Patterns matched (case-insensitive):
- `testplayer<counter>_<timestamp>@example.com`
- `stresstest<counter>_<timestamp>@example.com`
- `test_user_<8 hex>@example.com`

Commands:
```bash
python cleanup_test_players.py --list       # show matches
python cleanup_test_players.py --dry-run    # counts only
python cleanup_test_players.py              # anonymize + delete related data
python cleanup_test_players.py -y           # no confirmation
python cleanup_test_players.py -v           # detailed counts
```

What happens:
- Accounts are anonymized (not deleted) to keep phrasesets/history valid.
- Votes, transactions, daily bonuses, result views, abandoned prompt records, feedback, phraseset activity, refresh tokens, quests are deleted.
- Non-submitted prompt rounds are removed and pulled from the queue; submitted rounds are preserved.

### Orphaned rounds cleanup: `cleanup_orphaned_rounds.py`
Targets rounds with missing players and removes their prompt IDs from the queue.

```bash
python cleanup_orphaned_rounds.py --examples   # show sample rows
python cleanup_orphaned_rounds.py --dry-run
python cleanup_orphaned_rounds.py              # interactive delete
python cleanup_orphaned_rounds.py -y           # no prompt
```

## CleanupService API (for integrators)
`backend/services/qf/cleanup_service.py` exposes:
- `cleanup_orphaned_refresh_tokens()`
- `cleanup_expired_refresh_tokens()`
- `cleanup_old_revoked_tokens(days_old=30)`
- `count_orphaned_rounds()` / `cleanup_orphaned_rounds()`
- `get_test_players()` / `cleanup_test_players(dry_run=False)`
- `cleanup_inactive_guest_players(hours_old=1)`
- `recycle_inactive_guest_usernames(days_old=30)`
- `delete_player(player_id)`
- `run_all_cleanup_tasks()` (includes party session cleanup and username recycling; test players if invoked directly)

Example usage:
```python
from backend.database import AsyncSessionLocal
from backend.services import QFCleanupService

async with AsyncSessionLocal() as db:
    svc = QFCleanupService(db)
    results = await svc.run_all_cleanup_tasks()
    print(results)
```

## Automation examples
```bash
# Hourly safe cleanup (matches app's background task)
0 * * * * cd /path/to/quipflip && .venv/bin/python run_cleanup.py -y

# Weekly deep clean including test players
0 3 * * 0 cd /path/to/quipflip && .venv/bin/python run_cleanup.py --all -y
```

## Safety & best practices
- Start with `--dry-run` to see impact.
- Avoid `-y` on production unless you are confident in the scope.
- Back up the database before running test-player cleanup in prod.
- Preserve history: submitted rounds are intentionally kept; accounts are anonymized instead of deleted.
- Watch logs: scripts print counts; the service logs to standard logging handlers.

## Troubleshooting
- **“No test players found” but you see data:** Confirm your test data matches the documented patterns.
- **Foreign key errors:** The service deletes in dependency order and uses CASCADE for guests; if errors appear, ensure migrations match the running schema.
- **Queue still shows deleted prompts:** The service removes prompt IDs from the in-memory queue after deletion; restart workers if a stale queue persists.
- **Slow runs on large datasets:** Use targeted flags (`--tokens`, `--test-players`) and consider running during off-peak hours.
