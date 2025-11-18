#!/usr/bin/env python3
"""
Cleanup script to remove test player data from the database.
This script uses the CleanupService to remove players and their associated data created during testing.
"""
import asyncio
import sys
import argparse
from backend.database import AsyncSessionLocal
from backend.services import CleanupService


async def list_test_players():
    """List all test players without deleting."""
    async with AsyncSessionLocal() as session:
        cleanup_service = CleanupService(session)
        test_players = await cleanup_service.get_test_players()

        if not test_players:
            print("No test players found.")
            return

        print(f"Found {len(test_players)} test player(s):")
        for player in test_players:
            print(f"  - {player.username} ({player.email}) - Balance: {player.balance}")


async def cleanup_test_data(dry_run: bool = False, verbose: bool = False):
    """
    Remove all test player data from the database.

    Args:
        dry_run: If True, show what would be deleted without deleting
        verbose: If True, show detailed information about deletions
    """
    async with AsyncSessionLocal() as session:
        try:
            cleanup_service = CleanupService(session)

            # Find test players first
            test_players = await cleanup_service.get_test_players()

            if not test_players:
                print("No test players found.")
                return

            print(f"Found {len(test_players)} test player(s):")
            for player in test_players:
                print(f"  - {player.username} ({player.email})")

            if dry_run:
                print("\nDRY RUN MODE - No data will be deleted.")
                print(f"Would delete {len(test_players)} player(s) and all associated data.")
                return

            # Confirm deletion (unless non-interactive)
            if sys.stdin and sys.stdin.isatty():
                confirm = input("\nProceed with deletion? (yes/no): ")
                if confirm.lower() not in ["yes", "y"]:
                    print("Deletion cancelled.")
                    return

            print("\nDeleting test player data...")

            # Use cleanup service to delete
            deletion_counts = await cleanup_service.cleanup_test_players(dry_run=False)

            print("\nDeletion complete!")
            if verbose:
                print("\nDeleted records:")
                for entity, count in deletion_counts.items():
                    if count > 0:
                        print(f"  - {entity}: {count}")

            total_deleted = sum(deletion_counts.values())
            print(f"\nTotal: {total_deleted} records removed.")

        except Exception as e:
            print(f"\nError during cleanup: {e}", file=sys.stderr)
            raise


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up test player data from the database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List test players without deleting"
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

    if args.list:
        asyncio.run(list_test_players())
    else:
        asyncio.run(cleanup_test_data(dry_run=args.dry_run, verbose=args.verbose))


if __name__ == "__main__":
    main()
