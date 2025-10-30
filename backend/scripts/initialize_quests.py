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
            quest_service = QuestService(db)
            starter_quest_types = QuestService.STARTER_QUEST_TYPES
            starter_quest_values = {quest_type.value for quest_type in starter_quest_types}

            players_result = await db.execute(
                select(Player.player_id, Player.username)
            )
            players = players_result.all()
            logger.debug(f"Found {len(players)} total players")

            if not players:
                return

            quest_rows = await db.execute(
                select(Quest.player_id, Quest.quest_type).where(
                    Quest.quest_type.in_(starter_quest_values)
                )
            )

            quests_by_player = {}
            for player_id, quest_type in quest_rows.all():
                quests_by_player.setdefault(player_id, set()).add(quest_type)

            initialized_count = 0
            topped_up_count = 0
            skipped_count = 0

            for player_id, username in players:
                existing_quests = quests_by_player.get(player_id, set())
                missing_quest_types = [
                    quest_type
                    for quest_type in starter_quest_types
                    if quest_type.value not in existing_quests
                ]

                if missing_quest_types:
                    quest_names = ", ".join(qt.value for qt in missing_quest_types)
                    logger.debug(
                        f"Ensuring starter quests for player {username} ({player_id}); {len(missing_quest_types)} "
                        f"missing quests: {quest_names}"
                    )
                    await quest_service.create_missing_starter_quests(
                        player_id,
                        missing_quest_types,
                        auto_commit=False,
                    )
                    if len(existing_quests) == 0:
                        initialized_count += 1
                        logger.debug(
                            f"Ensured starter quests exist for {username} (processed {len(missing_quest_types)} quests)"
                        )
                    else:
                        topped_up_count += 1
                        logger.debug(
                            f"Ensured {len(missing_quest_types)} missing starter quests exist for {username}"
                        )
                    quests_by_player[player_id] = existing_quests.union(
                        {quest_type.value for quest_type in missing_quest_types}
                    )
                    continue

                logger.debug(f"Player {username} ({player_id}) already has all starter quests, skipping")
                skipped_count += 1

            await db.commit()

            logger.info("=== Summary ===")
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
