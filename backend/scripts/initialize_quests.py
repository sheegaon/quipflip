"""Script to initialize quests for all existing players who don't have them."""
import asyncio
import logging
from sqlalchemy import select

from backend.database import AsyncSessionLocal
from backend.models.player import Player
from backend.models.quest import Quest
from backend.services.quest_service import QuestService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def initialize_quests_for_all_players():
    """Initialize starter quests for all players who don't have any quests yet."""
    async with AsyncSessionLocal() as db:
        try:
            # Get all players
            result = await db.execute(select(Player))
            players = result.scalars().all()

            logger.info(f"Found {len(players)} total players")

            initialized_count = 0
            skipped_count = 0

            for player in players:
                # Check if player already has quests
                quest_result = await db.execute(
                    select(Quest).where(Quest.player_id == player.player_id).limit(1)
                )
                existing_quest = quest_result.scalar_one_or_none()

                if existing_quest:
                    logger.info(f"Player {player.username} ({player.player_id}) already has quests, skipping")
                    skipped_count += 1
                    continue

                # Initialize quests for this player
                logger.info(f"Initializing quests for player {player.username} ({player.player_id})...")
                quest_service = QuestService(db)
                quests = await quest_service.initialize_quests_for_player(player.player_id)
                logger.info(f"  ✓ Initialized {len(quests)} quests for {player.username}")
                initialized_count += 1

            await db.commit()

            logger.info(f"\n=== Summary ===")
            logger.info(f"Players initialized: {initialized_count}")
            logger.info(f"Players skipped (already had quests): {skipped_count}")
            logger.info(f"Total players processed: {len(players)}")

        except Exception as e:
            logger.error(f"Error initializing quests: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(initialize_quests_for_all_players())
