#!/usr/bin/env python3
"""
Unified cleanup script that runs all database cleanup tasks.

This script combines:
- Test player cleanup
- Orphaned rounds cleanup
- Refresh token cleanup (orphaned, expired, and old revoked)

Usage:
    python run_cleanup.py                     # Run all cleanup tasks (safe defaults)
    python run_cleanup.py --dry-run           # Show what would be cleaned without doing it
    python run_cleanup.py --all               # Run all cleanup including test players
    python run_cleanup.py --test-players      # Only cleanup test players
    python run_cleanup.py --orphaned-rounds   # Only cleanup orphaned rounds
    python run_cleanup.py --tokens            # Only cleanup tokens
    python run_cleanup.py -y                  # Skip confirmation prompts
"""
import asyncio
import sys
import argparse
from backend.database import AsyncSessionLocal
from backend.services import QFCleanupService


async def run_cleanup(
    dry_run: bool = False,
    verbose: bool = False,
    include_test_players: bool = False,
    test_players_only: bool = False,
    orphaned_rounds_only: bool = False,
    tokens_only: bool = False,
    skip_confirmation: bool = False,
):
    """
    Run database cleanup tasks.

    Args:
        dry_run: Show what would be cleaned without actually cleaning
        verbose: Show detailed information
        include_test_players: Include test player cleanup
        test_players_only: Only run test player cleanup
        orphaned_rounds_only: Only run orphaned rounds cleanup
        tokens_only: Only run token cleanup
        skip_confirmation: Skip confirmation prompts
    """
    async with AsyncSessionLocal() as session:
        try:
            cleanup_service = QFCleanupService(session)

            # Determine which tasks to run
            run_all = not (test_players_only or orphaned_rounds_only or tokens_only)

            print("=" * 60)
            print("DATABASE CLEANUP")
            print("=" * 60)

            if dry_run:
                print("\n🔍 DRY RUN MODE - No data will be deleted\n")

            results = {}

            # ===== Test Players Cleanup =====
            if test_players_only or (run_all and include_test_players):
                print("\n--- Test Players Cleanup ---")
                test_players = await cleanup_service.get_test_players()

                if test_players:
                    print(f"Found {len(test_players)} test player(s):")
                    for player in test_players[:10]:  # Show first 10
                        print(f"  - {player.username} ({player.email})")
                    if len(test_players) > 10:
                        print(f"  ... and {len(test_players) - 10} more")

                    if not dry_run and not skip_confirmation:
                        if sys.stdin and sys.stdin.isatty():
                            confirm = input("\nDelete test players? (yes/no): ")
                            if confirm.lower() not in ["yes", "y"]:
                                print("Test player cleanup skipped.")
                            else:
                                deletion_counts = await cleanup_service.cleanup_test_players(dry_run=False)
                                results.update(deletion_counts)
                    elif not dry_run:
                        deletion_counts = await cleanup_service.cleanup_test_players(dry_run=False)
                        results.update(deletion_counts)
                    else:
                        results["would_delete_test_players"] = len(test_players)
                else:
                    print("No test players found.")

            # ===== Orphaned Rounds Cleanup =====
            if orphaned_rounds_only or run_all:
                print("\n--- Orphaned Rounds Cleanup ---")
                orphaned_count, by_type = await cleanup_service.count_orphaned_rounds()

                if orphaned_count > 0:
                    print(f"Found {orphaned_count} orphaned round(s):")
                    for round_type, count in by_type.items():
                        print(f"  - {round_type}: {count}")

                    if not dry_run:
                        deleted = await cleanup_service.cleanup_orphaned_rounds()
                        results["orphaned_rounds"] = deleted
                    else:
                        results["would_delete_orphaned_rounds"] = orphaned_count
                else:
                    print("No orphaned rounds found.")

            # ===== Token Cleanup =====
            if tokens_only or run_all:
                print("\n--- Token Cleanup ---")

                # Orphaned tokens
                if not dry_run:
                    orphaned_tokens = await cleanup_service.cleanup_orphaned_refresh_tokens()
                    results["orphaned_tokens"] = orphaned_tokens
                    if orphaned_tokens > 0:
                        print(f"Cleaned up {orphaned_tokens} orphaned refresh token(s)")
                    else:
                        print("No orphaned tokens found")
                else:
                    print("Would check for orphaned tokens")

                # Expired tokens
                if not dry_run:
                    expired_tokens = await cleanup_service.cleanup_expired_refresh_tokens()
                    results["expired_tokens"] = expired_tokens
                    if expired_tokens > 0:
                        print(f"Cleaned up {expired_tokens} expired/revoked token(s)")
                    else:
                        print("No expired tokens found")
                else:
                    print("Would check for expired tokens")

                # Old revoked tokens
                if not dry_run:
                    old_revoked = await cleanup_service.cleanup_old_revoked_tokens()
                    results["old_revoked_tokens"] = old_revoked
                    if old_revoked > 0:
                        print(f"Cleaned up {old_revoked} old revoked token(s)")
                    else:
                        print("No old revoked tokens found")
                else:
                    print("Would check for old revoked tokens")

            # ===== Summary =====
            print("\n" + "=" * 60)
            print("CLEANUP SUMMARY")
            print("=" * 60)

            if results:
                if verbose:
                    print("\nDetailed results:")
                    for key, value in results.items():
                        if value > 0:
                            print(f"  {key}: {value}")

                total_cleaned = sum(results.values())
                if dry_run:
                    print(f"\nWould clean: {total_cleaned} total items")
                else:
                    print(f"\nCleaned: {total_cleaned} total items")
            else:
                print("\nNo items needed cleanup.")

            print()

        except Exception as e:
            print(f"\n❌ Error during cleanup: {e}", file=sys.stderr)
            raise


def main():
    """Main entry point for the unified cleanup script."""
    parser = argparse.ArgumentParser(
        description="Run database cleanup tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Run all safe cleanup tasks
  %(prog)s --dry-run            # Show what would be cleaned
  %(prog)s --all -y             # Run everything including test players
  %(prog)s --test-players       # Only cleanup test players
  %(prog)s --orphaned-rounds    # Only cleanup orphaned rounds
  %(prog)s --tokens             # Only cleanup tokens
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all cleanup tasks including test players"
    )
    parser.add_argument(
        "--test-players",
        action="store_true",
        help="Only run test player cleanup"
    )
    parser.add_argument(
        "--orphaned-rounds",
        action="store_true",
        help="Only run orphaned rounds cleanup"
    )
    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Only run token cleanup"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed information"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompts (for automated scripts)"
    )

    args = parser.parse_args()

    # Override stdin for --yes flag
    if args.yes:
        sys.stdin = None

    asyncio.run(run_cleanup(
        dry_run=args.dry_run,
        verbose=args.verbose,
        include_test_players=args.all,
        test_players_only=args.test_players,
        orphaned_rounds_only=args.orphaned_rounds,
        tokens_only=args.tokens,
        skip_confirmation=args.yes,
    ))


if __name__ == "__main__":
    main()
