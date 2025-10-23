#!/usr/bin/env python3
"""
Cleanup script to remove test player data from the database.
This script removes players and their associated data created during testing.
"""
import asyncio
import sys
import argparse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import AsyncSessionLocal, engine
from backend.models import (
    Player,
    Round,
    Prompt,
    Vote,
    Transaction,
    DailyBonus,
    ResultView,
    PlayerAbandonedPrompt,
    PromptFeedback,
    PhrasesetActivity,
    RefreshToken,
    Quest,
)


# Test player identification patterns
TEST_PATTERNS = [
    "testplayer",
    "stresstest",
    "@example.com",
    "test_",
    "_test",
]


async def get_test_players(session: AsyncSession, dry_run: bool = False):
    """
    Find all players matching test patterns.

    Args:
        session: Database session
        dry_run: If True, only return count without deleting

    Returns:
        List of Player objects
    """
    # Build query to find test players
    stmt = select(Player)
    result = await session.execute(stmt)
    all_players = result.scalars().all()

    # Filter players matching test patterns
    test_players = []
    for player in all_players:
        is_test = False
        for pattern in TEST_PATTERNS:
            if (pattern.lower() in player.username.lower() or
                pattern.lower() in player.email.lower()):
                is_test = True
                break

        if is_test:
            test_players.append(player)

    return test_players


async def cleanup_test_data(dry_run: bool = False, verbose: bool = False):
    """
    Remove all test player data from the database.

    Args:
        dry_run: If True, show what would be deleted without deleting
        verbose: If True, show detailed information about deletions
    """
    async with AsyncSessionLocal() as session:
        try:
            # Find test players
            test_players = await get_test_players(session, dry_run)

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

            # Extract player IDs for cascade deletion
            player_ids = [player.player_id for player in test_players]

            # Delete related data first (in order to respect foreign keys)
            deletion_counts = {}

            # 1. Votes (references player_id)
            result = await session.execute(
                delete(Vote).where(Vote.player_id.in_(player_ids))
            )
            deletion_counts['votes'] = result.rowcount

            # 2. Transactions (references player_id)
            result = await session.execute(
                delete(Transaction).where(Transaction.player_id.in_(player_ids))
            )
            deletion_counts['transactions'] = result.rowcount

            # 3. Daily bonuses (references player_id)
            result = await session.execute(
                delete(DailyBonus).where(DailyBonus.player_id.in_(player_ids))
            )
            deletion_counts['daily_bonuses'] = result.rowcount

            # 4. Result views (references player_id)
            result = await session.execute(
                delete(ResultView).where(ResultView.player_id.in_(player_ids))
            )
            deletion_counts['result_views'] = result.rowcount

            # 5. Abandoned prompts (references player_id)
            result = await session.execute(
                delete(PlayerAbandonedPrompt).where(PlayerAbandonedPrompt.player_id.in_(player_ids))
            )
            deletion_counts['abandoned_prompts'] = result.rowcount

            # 6. Prompt feedback (references player_id)
            result = await session.execute(
                delete(PromptFeedback).where(PromptFeedback.player_id.in_(player_ids))
            )
            deletion_counts['prompt_feedback'] = result.rowcount

            # 7. Phraseset activities (references player_id)
            result = await session.execute(
                delete(PhrasesetActivity).where(PhrasesetActivity.player_id.in_(player_ids))
            )
            deletion_counts['phraseset_activities'] = result.rowcount

            # 8. Refresh tokens (references player_id)
            result = await session.execute(
                delete(RefreshToken).where(RefreshToken.player_id.in_(player_ids))
            )
            deletion_counts['refresh_tokens'] = result.rowcount

            # 9. Quests (references player_id)
            result = await session.execute(
                delete(Quest).where(Quest.player_id.in_(player_ids))
            )
            deletion_counts['quests'] = result.rowcount

            # 10. Delete rounds (references player_id)
            # Note: Prompts are shared across players and should not be deleted
            result = await session.execute(
                delete(Round).where(Round.player_id.in_(player_ids))
            )
            deletion_counts['rounds'] = result.rowcount

            # 11. Finally, delete players
            result = await session.execute(
                delete(Player).where(Player.player_id.in_(player_ids))
            )
            deletion_counts['players'] = result.rowcount

            # Commit the transaction
            await session.commit()

            print("\nDeletion complete!")
            if verbose:
                print("\nDeleted records:")
                for entity, count in deletion_counts.items():
                    if count > 0:
                        print(f"  - {entity}: {count}")

            print(f"\nTotal: {len(test_players)} test player(s) and all associated data removed.")

        except Exception as e:
            await session.rollback()
            print(f"\nError during cleanup: {e}", file=sys.stderr)
            raise


async def list_test_players():
    """List all test players without deleting."""
    async with AsyncSessionLocal() as session:
        test_players = await get_test_players(session, dry_run=True)

        if not test_players:
            print("No test players found.")
            return

        print(f"Found {len(test_players)} test player(s):")
        for player in test_players:
            print(f"  - {player.username} ({player.email}) - Balance: {player.balance}")


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
