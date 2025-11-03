"""Service for handling stale prompts and phrasesets with AI assistance."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.phraseset import Phraseset
from backend.models.player import Player
from backend.models.round import Round
from backend.models.vote import Vote
from backend.services.ai.ai_service import AIService
from backend.services.player_service import PlayerService
from backend.services.round_service import RoundService
from backend.services.transaction_service import TransactionService
from backend.services.vote_service import VoteService


logger = logging.getLogger(__name__)


AI_STALE_HANDLER_EMAIL = "ai_stale_handler@quipflip.internal"
AI_STALE_HANDLER_USERNAME = "StaleAIHandler"
AI_STALE_HANDLER_PSEUDONYM = "Stale AI Handler"


class StaleAIService:
    """Provide AI-generated copies and votes for stale game content."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.ai_service = AIService(db)

    async def _get_or_create_stale_handler(self) -> Player:
        """Ensure the dedicated stale AI player exists."""

        result = await self.db.execute(
            select(Player).where(Player.email == AI_STALE_HANDLER_EMAIL)
        )
        player = result.scalar_one_or_none()
        if player:
            return player

        player_service = PlayerService(self.db)
        try:
            player = await player_service.create_player(
                username=AI_STALE_HANDLER_USERNAME,
                email=AI_STALE_HANDLER_EMAIL,
                password_hash="not-used-for-ai-player",
                pseudonym=AI_STALE_HANDLER_PSEUDONYM,
                pseudonym_canonical=AI_STALE_HANDLER_PSEUDONYM.lower().replace(" ", ""),
            )
            logger.info("Created stale AI handler player: %s", player.player_id)
            return player
        except Exception as exc:
            logger.error("Failed to create stale AI handler player: %s", exc)
            raise

    async def _find_stale_prompts(self, stale_handler_id: UUID) -> List[Round]:
        """Locate prompt rounds that have been waiting for copies beyond the stale threshold."""

        cutoff_time = datetime.now(UTC) - timedelta(days=self.settings.ai_stale_threshold_days)

        result = await self.db.execute(
            select(Round)
            .where(Round.round_type == "prompt")
            .where(Round.status == "submitted")
            .where(Round.created_at <= cutoff_time)
            .where(Round.player_id != stale_handler_id)
            .outerjoin(Phraseset, Phraseset.prompt_round_id == Round.round_id)
            .where(Phraseset.phraseset_id.is_(None))
            .order_by(Round.created_at.asc())
        )

        prompt_rounds = list(result.scalars().all())

        stale_prompts: List[Round] = []
        for prompt_round in prompt_rounds:
            existing_copy_result = await self.db.execute(
                select(Round.round_id)
                .where(Round.prompt_round_id == prompt_round.round_id)
                .where(Round.round_type == "copy")
                .where(Round.player_id == stale_handler_id)
            )
            if existing_copy_result.scalar_one_or_none() is None:
                stale_prompts.append(prompt_round)

        return stale_prompts

    async def _find_stale_phrasesets(self, stale_handler_id: UUID) -> List[Phraseset]:
        """Locate phrasesets that have been waiting for votes beyond the stale threshold."""

        cutoff_time = datetime.now(UTC) - timedelta(days=self.settings.ai_stale_threshold_days)

        already_voted_subquery = select(Vote.phraseset_id).where(
            Vote.player_id == stale_handler_id
        )

        result = await self.db.execute(
            select(Phraseset)
            .where(Phraseset.status.in_(["open", "closing"]))
            .where(Phraseset.created_at <= cutoff_time)
            .where(~Phraseset.phraseset_id.in_(already_voted_subquery))
            .options(
                selectinload(Phraseset.prompt_round),
                selectinload(Phraseset.copy_round_1),
                selectinload(Phraseset.copy_round_2),
            )
            .order_by(Phraseset.created_at.asc())
        )

        return list(result.scalars().all())

    async def run_stale_cycle(self) -> None:
        """Process stale prompts and phrasesets with AI-generated participation."""

        stats = {
            "stale_prompts_found": 0,
            "stale_prompts_processed": 0,
            "stale_copies_generated": 0,
            "stale_phrasesets_found": 0,
            "stale_phrasesets_processed": 0,
            "stale_votes_generated": 0,
            "errors": 0,
        }

        try:
            stale_handler = await self._get_or_create_stale_handler()

            stale_prompts = await self._find_stale_prompts(stale_handler.player_id)
            stats["stale_prompts_found"] = len(stale_prompts)

            round_service = RoundService(self.db)

            for prompt_round in stale_prompts:
                try:
                    copy_phrase = await self.ai_service.generate_copy_phrase(
                        prompt_round.submitted_phrase,
                        prompt_round,
                    )

                    copy_round = Round(
                        round_id=uuid.uuid4(),
                        player_id=stale_handler.player_id,
                        round_type="copy",
                        status="submitted",
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(minutes=3),
                        cost=0,
                        prompt_round_id=prompt_round.round_id,
                        original_phrase=prompt_round.submitted_phrase,
                        copy_phrase=copy_phrase.upper(),
                        system_contribution=0,
                    )

                    self.db.add(copy_round)

                    if prompt_round.copy1_player_id is None:
                        prompt_round.copy1_player_id = stale_handler.player_id
                        prompt_round.phraseset_status = "waiting_copy1"
                    elif prompt_round.copy2_player_id is None:
                        prompt_round.copy2_player_id = stale_handler.player_id
                        if prompt_round.copy1_player_id is not None:
                            phraseset = await round_service.create_phraseset_if_ready(prompt_round)
                            if phraseset:
                                prompt_round.phraseset_status = "active"
                    else:
                        phraseset = await round_service.create_phraseset_if_ready(prompt_round)
                        if phraseset:
                            prompt_round.phraseset_status = "active"

                    stats["stale_prompts_processed"] += 1
                    stats["stale_copies_generated"] += 1

                except Exception as exc:
                    logger.error(
                        "Failed to process stale prompt %s: %s",
                        getattr(prompt_round, "round_id", "unknown"),
                        exc,
                    )
                    stats["errors"] += 1

            stale_phrasesets = await self._find_stale_phrasesets(stale_handler.player_id)
            stats["stale_phrasesets_found"] = len(stale_phrasesets)

            vote_service = VoteService(self.db)
            transaction_service = TransactionService(self.db)

            for phraseset in stale_phrasesets:
                try:
                    chosen_phrase = await self.ai_service.generate_vote_choice(phraseset)

                    await vote_service.submit_system_vote(
                        phraseset=phraseset,
                        player=stale_handler,
                        chosen_phrase=chosen_phrase,
                        transaction_service=transaction_service,
                    )

                    stats["stale_votes_generated"] += 1
                    stats["stale_phrasesets_processed"] += 1

                except Exception as exc:
                    logger.error(
                        "Failed to process stale phraseset %s: %s",
                        getattr(phraseset, "phraseset_id", "unknown"),
                        exc,
                    )
                    stats["errors"] += 1

            await self.db.commit()

            logger.info(
                "Stale AI cycle completed: %s/%s prompts processed, %s/%s phrasesets processed, %s errors",
                stats["stale_prompts_processed"],
                stats["stale_prompts_found"],
                stats["stale_phrasesets_processed"],
                stats["stale_phrasesets_found"],
                stats["errors"],
            )

        except Exception as exc:
            logger.error("Stale AI cycle failed: %s", exc)
            await self.db.rollback()
            raise
