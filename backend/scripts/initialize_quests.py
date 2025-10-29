"""Script to ensure all existing players have the full starter quest set."""
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
    """Ensure every player has the full starter quest set."""
    async with AsyncSessionLocal() as db:
        try:
            # Get all players
            result = await db.execute(select(Player))
            players = result.scalars().all()

            logger.info(f"Found {len(players)} total players")

            quest_service = QuestService(db)
            starter_quests = QuestService.STARTER_QUEST_TYPES

            initialized_count = 0
            topped_up_count = 0
            skipped_count = 0

            for player in players:
                # Fetch existing quests for the player
                quest_result = await db.execute(
                    select(Quest.quest_type).where(Quest.player_id == player.player_id)
                )
                existing_quests = {row[0] for row in quest_result.all()}

                missing_quest_types = [
                    quest_type for quest_type in starter_quests if quest_type.value not in existing_quests
                ]

                if not existing_quests:
                    logger.info(
                        "Ensuring starter quests for player %s (%s)...",
                        player.username,
                        player.player_id,
                    )
                    await quest_service.initialize_quests_for_player(
                        player.player_id,
                        auto_commit=False,
                    )
                    logger.info(
                        "  ✓ Ensured %d starter quests for %s",
                        len(starter_quests),
                        player.username,
                    )
                    initialized_count += 1
                    continue

                if missing_quest_types:
                    quest_names = ", ".join(qt.value for qt in missing_quest_types)
                    logger.info(
                        "Player %s (%s) is missing %d quests: %s. Adding missing quests.",
                        player.username,
                        player.player_id,
                        len(missing_quest_types),
                        quest_names,
                    )
                    new_quests = await quest_service.create_missing_starter_quests(
                        player.player_id,
                        missing_quest_types,
                        auto_commit=False,
                    )
                    logger.info(
                        "  ✓ Added %d missing starter quests for %s",
                        len(new_quests),
                        player.username,
                    )
                    topped_up_count += 1
                    continue

                logger.info(
                    f"Player {player.username} ({player.player_id}) already has all starter quests, skipping"
                )
                skipped_count += 1

            await db.commit()

            logger.info(f"\n=== Summary ===")
            logger.info(f"Players initialized: {initialized_count}")
            logger.info(f"Players topped up with missing quests: {topped_up_count}")
            logger.info(f"Players skipped (already had quests): {skipped_count}")
            logger.info(f"Total players processed: {len(players)}")

        except Exception as e:
            logger.error(f"Error initializing quests: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(initialize_quests_for_all_players())
