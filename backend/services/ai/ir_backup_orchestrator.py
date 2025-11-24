"""
Initial Reaction Backup Orchestrator for AI-generated backronyms and votes.

This module handles the backup cycle logic for Initial Reaction game, finding stalled
backronym sets and generating AI entries and votes to keep the game moving.
"""

import logging
from sqlalchemy import select

from backend.services.ir.backronym_set_service import BackronymSetService
from backend.models.ir.backronym_entry import BackronymEntry
from backend.utils.model_registry import AIPlayerType

logger = logging.getLogger(__name__)


class IRBackupOrchestrator:
    """
    Orchestrates AI backup operations for Initial Reaction game.

    Handles finding stalled backronym sets and coordinates with AIService
    to generate appropriate AI entries and votes.
    """

    def __init__(self, ai_service):
        """
        Initialize the backup orchestrator.

        Args:
            ai_service: AIService instance for generating AI responses
        """
        self.ai_service = ai_service
        self.db = ai_service.db
        self.settings = ai_service.settings

    async def run_backup_cycle(self) -> None:
        """
        Run backup cycle for Initial Reaction game.

        Fills stalled backronym sets with AI entries and votes.
        """
        stats = {
            "sets_checked": 0,
            "entries_generated": 0,
            "votes_generated": 0,
            "errors": 0,
        }

        try:
            # Get or create IR AI player
            ai_player = await self.ai_service.get_or_create_ai_player(AIPlayerType.IR_PLAYER)

            set_service = BackronymSetService(self.db)

            # Get stalled open sets
            stalled_open = await set_service.get_stalled_open_sets(
                minutes=self.settings.ir_ai_backup_delay_minutes
            )
            stats["sets_checked"] = len(stalled_open)

            # Fill stalled open sets
            for set_obj in stalled_open:
                try:
                    while set_obj.entry_count < 5:
                        # Generate backronym
                        backronym = await self.ai_service.generate_backronym(set_obj.word)

                        # Add entry
                        entry = await set_service.add_entry(
                            set_id=str(set_obj.set_id),
                            player_id=str(ai_player.player_id),
                            backronym_text=backronym,
                            is_ai=True,
                        )
                        stats["entries_generated"] += 1
                        logger.info(
                            f"AI entry {entry.entry_id} added to set {set_obj.set_id}"
                        )

                        # Refresh set to get updated count
                        set_obj = await set_service.get_set_by_id(str(set_obj.set_id))
                        if not set_obj:
                            break

                except Exception as e:
                    logger.error(f"Error filling set {set_obj.set_id}: {e}")
                    stats["errors"] += 1

            # Get stalled voting sets
            stalled_voting = await set_service.get_stalled_voting_sets(minutes=self.settings.ir_ai_backup_delay_minutes)

            # Fill voting for stalled sets
            for set_obj in stalled_voting:
                try:
                    # Get entries for this set
                    entries_stmt = select(BackronymEntry).where(BackronymEntry.set_id == str(set_obj.set_id))
                    entries_result = await self.db.execute(entries_stmt)
                    entries = entries_result.scalars().all()

                    if len(entries) < 5:
                        logger.warning(f"Set {set_obj.set_id} has < 5 entries, skipping voting fill")
                        continue

                    # Generate votes until we have 5
                    while set_obj.vote_count < 5:
                        # Get backronym texts as word arrays
                        backronym_strs = [e.backronym_text for e in entries]

                        # Generate vote
                        chosen_index = await self.ai_service.generate_backronym_vote(set_obj.word, backronym_strs)
                        chosen_entry_id = entries[chosen_index].entry_id

                        # Add vote
                        vote = await set_service.add_vote(
                            set_id=str(set_obj.set_id),
                            player_id=str(ai_player.player_id),
                            chosen_entry_id=str(chosen_entry_id),
                            is_participant_voter=False,
                            is_ai=True,
                        )
                        stats["votes_generated"] += 1
                        logger.info(f"AI vote {vote.vote_id} added to set {set_obj.set_id}")

                        # Refresh set
                        set_obj = await set_service.get_set_by_id(str(set_obj.set_id))
                        if not set_obj:
                            break

                except Exception as e:
                    logger.error(f"Error filling votes for set {set_obj.set_id}: {e}")
                    stats["errors"] += 1

            await self.db.commit()
            logger.info(f"IR backup cycle completed: {stats}")

        except Exception as exc:
            logger.error(f"IR backup cycle failed: {exc}")
            await self.db.rollback()
            stats["errors"] += 1
