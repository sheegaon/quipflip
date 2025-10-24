#!/usr/bin/env python3
"""
Cleanup script to remove orphaned rounds from the database.

Orphaned rounds are rounds that reference player_ids that no longer exist in the players table.
This can happen when test players are deleted but their rounds are left behind.
"""
import asyncio
import sys
import argparse
from sqlalchemy import text
from backend.database import AsyncSessionLocal


async def count_orphaned_rounds():
    """Count orphaned rounds in the database."""
    async with AsyncSessionLocal() as db:
        # Count rounds with player_id not in players table
        result = await db.execute(text("""
            SELECT COUNT(*)
            FROM rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
        """))
        orphaned_count = result.scalar()

        # Count by type
        result = await db.execute(text("""
            SELECT round_type, COUNT(*) as count
            FROM rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
            GROUP BY round_type
        """))
        by_type = {row.round_type: row.count for row in result}

        return orphaned_count, by_type


async def cleanup_orphaned_rounds(dry_run: bool = False, verbose: bool = False):
    """
    Remove orphaned rounds from the database.

    Args:
        dry_run: If True, show what would be deleted without deleting
        verbose: If True, show detailed information
    """
    async with AsyncSessionLocal() as db:
        try:
            # Count orphaned rounds
            orphaned_count, by_type = await count_orphaned_rounds()

            if orphaned_count == 0:
                print("No orphaned rounds found.")
                return

            print(f"Found {orphaned_count} orphaned round(s):")
            for round_type, count in by_type.items():
                print(f"  - {round_type}: {count}")

            if dry_run:
                print("\nDRY RUN MODE - No data will be deleted.")
                print(f"Would delete {orphaned_count} orphaned round(s).")
                return

            # Confirm deletion (unless non-interactive)
            if sys.stdin and sys.stdin.isatty():
                confirm = input("\nProceed with deletion? (yes/no): ")
                if confirm.lower() not in ["yes", "y"]:
                    print("Deletion cancelled.")
                    return

            print("\nDeleting orphaned rounds...")

            # Delete orphaned rounds
            result = await db.execute(text("""
                DELETE FROM rounds
                WHERE player_id NOT IN (SELECT player_id FROM players)
            """))
            deleted_count = result.rowcount

            await db.commit()

            print(f"\nDeletion complete! Deleted {deleted_count} orphaned round(s).")

        except Exception as e:
            await db.rollback()
            print(f"\nError during cleanup: {e}", file=sys.stderr)
            raise


async def show_orphaned_examples(limit: int = 10):
    """Show examples of orphaned rounds."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(f"""
            SELECT r.round_id, r.player_id, r.round_type, r.status,
                   r.submitted_phrase, r.created_at
            FROM rounds r
            WHERE r.player_id NOT IN (SELECT player_id FROM players)
            ORDER BY r.created_at DESC
            LIMIT {limit}
        """))

        print(f"Example orphaned rounds (most recent {limit}):")
        for row in result:
            phrase = row.submitted_phrase[:30] + "..." if row.submitted_phrase else "None"
            print(f"  - {row.round_type} round {row.round_id}")
            print(f"    Player ID: {row.player_id} (deleted)")
            print(f"    Status: {row.status}")
            print(f"    Created: {row.created_at}")
            print(f"    Phrase: {phrase}")
            print()


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up orphaned rounds from the database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--examples",
        action="store_true",
        help="Show examples of orphaned rounds"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed deletion information"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt (for automated scripts)"
    )

    args = parser.parse_args()

    # Override stdin for --yes flag
    if args.yes:
        sys.stdin = None

    if args.examples:
        asyncio.run(show_orphaned_examples())
    else:
        asyncio.run(cleanup_orphaned_rounds(dry_run=args.dry_run, verbose=args.verbose))


if __name__ == "__main__":
    main()
