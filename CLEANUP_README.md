# Database Cleanup Scripts

This directory contains scripts for cleaning up database artifacts during development and maintenance.

## Overview

All cleanup scripts now use the centralized `CleanupService` class located in `backend/services/cleanup_service.py`. This ensures consistent cleanup logic across all scripts.

## Available Scripts

### 1. Unified Cleanup Script: `run_cleanup.py`

**Recommended for most use cases.** Runs all cleanup tasks in one command.

```bash
# Run all safe cleanup tasks (tokens and orphaned rounds)
python run_cleanup.py

# Show what would be cleaned without actually cleaning
python run_cleanup.py --dry-run

# Run everything including test players with confirmation
python run_cleanup.py --all

# Run everything including test players without confirmation
python run_cleanup.py --all -y

# Only cleanup test players
python run_cleanup.py --test-players

# Only cleanup orphaned rounds
python run_cleanup.py --orphaned-rounds

# Only cleanup tokens
python run_cleanup.py --tokens

# Show detailed output
python run_cleanup.py -v
```

### 2. Test Player Cleanup: `cleanup_test_players.py`

Removes test players and all associated data from the database.

Test players are identified by patterns:
- `testplayer` in username or email
- `stresstest` in username or email
- `@example.com` in email
- `test_` prefix or suffix in username

```bash
# List test players without deleting
python cleanup_test_players.py --list

# Preview what would be deleted
python cleanup_test_players.py --dry-run

# Delete test players with confirmation
python cleanup_test_players.py

# Delete test players without confirmation (for automation)
python cleanup_test_players.py -y

# Show detailed deletion counts
python cleanup_test_players.py -v
```

**Warning:** This permanently deletes:
- Players matching test patterns
- All rounds created by those players
- All votes by those players
- All transactions
- All daily bonuses
- All quest progress
- All refresh tokens
- All other associated data

### 3. Orphaned Rounds Cleanup: `cleanup_orphaned_rounds.py`

Removes rounds that reference deleted players.

```bash
# Show examples of orphaned rounds
python cleanup_orphaned_rounds.py --examples

# Preview what would be deleted
python cleanup_orphaned_rounds.py --dry-run

# Delete orphaned rounds with confirmation
python cleanup_orphaned_rounds.py

# Delete orphaned rounds without confirmation
python cleanup_orphaned_rounds.py -y
```

## CleanupService API

The `backend/services/cleanup_service.py` module provides the following methods:

### Token Cleanup
- `cleanup_orphaned_refresh_tokens()` - Remove tokens for deleted players
- `cleanup_expired_refresh_tokens()` - Remove expired/revoked tokens
- `cleanup_old_revoked_tokens(days_old=30)` - Remove old revoked tokens

### Rounds Cleanup
- `cleanup_orphaned_rounds()` - Remove rounds for deleted players
- `count_orphaned_rounds()` - Count orphaned rounds by type

### Test Player Cleanup
- `get_test_players()` - Find all test players
- `cleanup_test_players(dry_run=False)` - Remove test players and data

### Run All
- `run_all_cleanup_tasks(include_test_players=False)` - Run all cleanup tasks

## Usage in Code

```python
from backend.database import AsyncSessionLocal
from backend.services.cleanup_service import CleanupService

async with AsyncSessionLocal() as session:
    cleanup_service = CleanupService(session)

    # Run all safe cleanup tasks
    results = await cleanup_service.run_all_cleanup_tasks()
    print(f"Cleaned {sum(results.values())} items")

    # Or run specific cleanup
    deleted = await cleanup_service.cleanup_orphaned_rounds()
    print(f"Deleted {deleted} orphaned rounds")
```

## Automated Cleanup

You can schedule cleanup tasks using cron or a task scheduler:

```bash
# Daily cleanup of tokens and orphaned rounds at 2 AM
0 2 * * * cd /path/to/quipflip && .venv/bin/python run_cleanup.py -y

# Weekly cleanup including test players on Sundays at 3 AM
0 3 * * 0 cd /path/to/quipflip && .venv/bin/python run_cleanup.py --all -y
```

## Safety Features

All scripts include:
- **Dry-run mode** - Preview changes without making them
- **Confirmation prompts** - Interactive confirmation before deletion
- **Skip confirmation flag** (`-y`) - For automated scripts
- **Detailed logging** - Shows what was deleted
- **Transaction safety** - All deletions are transactional

## Best Practices

1. **Always use `--dry-run` first** to preview changes
2. **Review test player patterns** before bulk deletion
3. **Back up your database** before running cleanup on production
4. **Use `-y` flag carefully** - it skips all confirmations
5. **Run token cleanup regularly** to prevent table bloat
6. **Monitor orphaned rounds** after deleting test players

## Troubleshooting

### "No test players found" but you see test data
- Check the `TEST_PATTERNS` in `CleanupService`
- Your test data might not match the patterns

### Cleanup is slow
- Large volumes of test data may take time
- Consider using `--test-players` to run only that cleanup

### Foreign key errors
- The scripts handle cascade deletion automatically
- If you see errors, check database constraints

## Examples

```bash
# Development workflow: Clean up after integration tests
python run_cleanup.py --all -y

# Production maintenance: Clean tokens only
python run_cleanup.py --tokens

# Investigation: See what would be cleaned
python run_cleanup.py --dry-run -v

# Manual cleanup: Interactive test player cleanup
python cleanup_test_players.py

# Quick check: List test players
python cleanup_test_players.py --list
```
