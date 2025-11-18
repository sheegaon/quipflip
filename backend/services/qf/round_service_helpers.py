from uuid import UUID
import logging
from sqlalchemy import select, func, text, or_, union, bindparam
from sqlalchemy.types import DateTime, String
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC, timedelta

from backend.models.qf.round import Round
from backend.models.qf.prompt import Prompt
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.player_abandoned_prompt import PlayerAbandonedPrompt
from backend.models.qf.player import QFPlayer

logger = logging.getLogger(__name__)


class PromptQueryBuilder:
    """Helper class for building complex prompt-related queries."""
    
    @staticmethod
    def build_unseen_prompts_query(player_id: UUID) -> select:
        """Build query to find prompts the player hasn't seen yet."""
        copy_round_alias = aliased(Round)
        copy_prompt_round_alias = aliased(Round)
        vote_round_alias = aliased(Round)
        vote_prompt_round_alias = aliased(Round)
        phraseset_alias = aliased(Phraseset)

        prompt_round_seen = (
            select(Round.prompt_id)
            .where(Round.player_id == player_id)
            .where(Round.prompt_id.is_not(None))
        )

        copy_round_seen = (
            select(copy_prompt_round_alias.prompt_id)
            .select_from(copy_round_alias)
            .join(
                copy_prompt_round_alias,
                copy_round_alias.prompt_round_id == copy_prompt_round_alias.round_id,
            )
            .where(copy_round_alias.player_id == player_id)
            .where(copy_round_alias.round_type == "copy")
            .where(copy_prompt_round_alias.prompt_id.is_not(None))
        )

        vote_round_seen = (
            select(vote_prompt_round_alias.prompt_id)
            .select_from(vote_round_alias)
            .join(
                phraseset_alias,
                vote_round_alias.phraseset_id == phraseset_alias.phraseset_id,
            )
            .join(
                vote_prompt_round_alias,
                phraseset_alias.prompt_round_id == vote_prompt_round_alias.round_id,
            )
            .where(vote_round_alias.player_id == player_id)
            .where(vote_round_alias.round_type == "vote")
            .where(vote_prompt_round_alias.prompt_id.is_not(None))
        )

        seen_prompts_subquery = (
            union(
                prompt_round_seen,
                copy_round_seen,
                vote_round_seen,
            ).subquery()
        )

        base_stmt = select(Prompt).where(Prompt.enabled == True)

        return (
            base_stmt.outerjoin(
                seen_prompts_subquery,
                seen_prompts_subquery.c.prompt_id == Prompt.prompt_id,
            )
            .where(seen_prompts_subquery.c.prompt_id.is_(None))
            .order_by(func.random())
            .limit(1)
        )

    @staticmethod
    def build_available_prompts_count_query() -> text:
        """Build optimized query for counting available prompts for a player."""
        query = text("""
                WITH player_prompt_rounds AS (
                    SELECT r.round_id
                    FROM qf_rounds r
                    WHERE LOWER(REPLACE(CAST(r.player_id AS TEXT), '-', '')) = :player_id_clean
                    AND r.round_type = 'prompt'
                    AND r.status = 'submitted'
                ),
                player_copy_rounds AS (
                    SELECT r.prompt_round_id
                    FROM qf_rounds r
                    WHERE LOWER(REPLACE(CAST(r.player_id AS TEXT), '-', '')) = :player_id_clean
                    AND r.round_type = 'copy'
                    AND r.status = 'submitted'
                ),
                player_abandoned_cooldown AS (
                    SELECT pap.prompt_round_id
                    FROM qf_player_abandoned_prompts pap
                    WHERE LOWER(REPLACE(CAST(pap.player_id AS TEXT), '-', '')) = :player_id_clean
                    AND pap.abandoned_at > :cutoff_time
                ),
                all_available_prompts AS (
                    SELECT r.round_id
                    FROM qf_rounds r
                    LEFT JOIN qf_phrasesets p ON p.prompt_round_id = r.round_id
                    WHERE r.round_type = 'prompt'
                    AND r.status = 'submitted'
                    AND (r.phraseset_status IS NULL OR r.phraseset_status NOT IN ('flagged_pending','flagged_removed'))
                    AND p.phraseset_id IS NULL
                )
                SELECT COUNT(*) as available_count
                FROM all_available_prompts a
                WHERE NOT EXISTS (SELECT 1 FROM player_prompt_rounds ppr WHERE ppr.round_id = a.round_id)
                AND NOT EXISTS (SELECT 1 FROM player_copy_rounds pcr WHERE pcr.prompt_round_id = a.round_id)
                AND NOT EXISTS (SELECT 1 FROM player_abandoned_cooldown pac WHERE pac.prompt_round_id = a.round_id)
            """)
        return query.bindparams(
            bindparam("player_id_clean", type_=String),
            bindparam("cutoff_time", type_=DateTime(timezone=True)),
        )

    @staticmethod
    def build_queue_rehydration_query() -> select:
        """Build query to find available prompts for queue rehydration."""
        return (
            select(Round.round_id)
            .join(Phraseset, Phraseset.prompt_round_id == Round.round_id, isouter=True)
            .where(Round.round_type == "prompt")
            .where(Round.status == "submitted")
            .where(
                or_(
                    Round.phraseset_status.is_(None),
                    Round.phraseset_status.notin_(["flagged_pending", "flagged_removed"]),
                )
            )
            .where(Phraseset.phraseset_id.is_(None))
            .order_by(Round.created_at.asc())
        )


class RoundValidationHelper:
    """Helper class for round validation logic."""
    
    @staticmethod
    async def check_prompt_round_eligibility(db: AsyncSession, player: QFPlayer, prompt_round: Round,
                                             abandoned_prompt_cooldown_hours: int) -> tuple[bool, bool]:
        """
        Determine if the candidate prompt should be skipped and requeued.
        
        Returns:
            Tuple of (should_skip, should_requeue)
        """
        if prompt_round.player_id == player.player_id:
            logger.debug(f"Player {player.player_id} got their own prompt {prompt_round.round_id}, retrying...")
            return True, True

        # Check if player already submitted a copy for this prompt
        existing_copy_result = await db.execute(
            select(Round.round_id)
            .where(Round.round_type == "copy")
            .where(Round.prompt_round_id == prompt_round.round_id)
            .where(Round.player_id == player.player_id)
        )
        if existing_copy_result.scalar_one_or_none():
            logger.debug(
                f"Player {player.player_id} already submitted a copy for prompt {prompt_round.round_id}, retrying...")
            return True, True

        # Check abandoned prompt cooldown
        cutoff = datetime.now(UTC) - timedelta(hours=abandoned_prompt_cooldown_hours)
        result = await db.execute(
            select(PlayerAbandonedPrompt)
            .where(PlayerAbandonedPrompt.player_id == player.player_id)
            .where(PlayerAbandonedPrompt.prompt_round_id == prompt_round.round_id)
            .where(PlayerAbandonedPrompt.abandoned_at > cutoff)
        )
        if result.scalar_one_or_none():
            logger.debug(f"Player {player.player_id} abandoned prompt {prompt_round.round_id} recently, retrying...")
            return True, True

        return False, False

    @staticmethod
    async def validate_second_copy_eligibility(db: AsyncSession, player: QFPlayer, prompt_round_id: UUID
                                               ) -> tuple[bool, str]:
        """
        Validate if player is eligible for second copy.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        prompt_round = await db.get(Round, prompt_round_id)
        if not prompt_round or prompt_round.round_type != "prompt":
            return False, "Invalid prompt round ID for second copy"

        if prompt_round.copy2_player_id is not None:
            return False, "Second copy slot for this prompt is already filled"

        # Verify player has already done first copy
        existing_copies_count = (
            await db.execute(
                select(func.count())
                .select_from(Round)
                .filter(
                    Round.player_id == player.player_id,
                    Round.round_type == "copy",
                    Round.prompt_round_id == prompt_round_id,
                    Round.status == "submitted",
                )
            )
        ).scalar()

        if existing_copies_count == 0:
            return False, "Player must complete first copy before requesting second copy"
        if existing_copies_count >= 2:
            return False, "Player has already completed two copies for this prompt"

        return True, ""


class CostCalculationHelper:
    """Helper class for calculating round costs and contributions."""
    
    @staticmethod
    def calculate_copy_round_cost(settings, queue_service) -> tuple[int, bool, int]:
        """Return copy round cost, discount flag, and system contribution."""
        copy_cost = queue_service.get_copy_cost()
        is_discounted = copy_cost == settings.copy_cost_discount
        system_contribution = settings.copy_cost_normal - copy_cost if is_discounted else 0
        return copy_cost, is_discounted, system_contribution

    @staticmethod
    def calculate_second_copy_info(prompt_round: Round, is_first_copy: bool, player_wallet: int, settings) -> dict:
        """Calculate second copy eligibility and cost info."""
        second_copy_info = {
            "eligible_for_second_copy": False,
            "second_copy_cost": None,
            "prompt_round_id": None,
            "original_phrase": None,
        }

        if prompt_round and is_first_copy:
            # Calculate second copy cost (2x the normal cost)
            second_copy_cost = settings.copy_cost_normal * 2

            if player_wallet >= second_copy_cost:
                second_copy_info = {
                    "eligible_for_second_copy": True,
                    "second_copy_cost": second_copy_cost,
                    "prompt_round_id": prompt_round.round_id,
                    "original_phrase": None,  # Will be set by caller
                }

        return second_copy_info

    @staticmethod
    def calculate_abandon_refund(round_cost: int, abandoned_penalty: int) -> tuple[int, int]:
        """Calculate refund amount and penalty for abandoned rounds."""
        penalty_kept = abandoned_penalty
        refund_amount = max(round_cost - penalty_kept, 0)
        return refund_amount, penalty_kept


class PhrasesetCreationHelper:
    """Helper class for phraseset creation logic."""
    
    @staticmethod
    async def get_copy_rounds_for_prompt(db: AsyncSession, prompt_round_id: UUID) -> list[Round]:
        """Get submitted copy rounds for a prompt, ordered by creation time."""
        result = await db.execute(
            select(Round)
            .where(Round.prompt_round_id == prompt_round_id)
            .where(Round.round_type == "copy")
            .where(Round.status == "submitted")
            .order_by(Round.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    def validate_phraseset_data(prompt_round: Round, copy_rounds: list[Round]) -> tuple[bool, str]:
        """Validate that all required data is present for phraseset creation."""
        if len(copy_rounds) < 2:
            return False, f"Only {len(copy_rounds)} copy rounds found"

        if not prompt_round.submitted_phrase:
            return False, "Prompt has no submitted_phrase"

        if not prompt_round.prompt_text:
            return False, f"Prompt_round {prompt_round.round_id} missing prompt_text"

        copy1, copy2 = copy_rounds[0], copy_rounds[1]
        
        if not copy1.copy_phrase:
            return False, f"Copy_round {copy1.round_id} missing copy_phrase"

        if not copy2.copy_phrase:
            return False, f"Copy_round {copy2.round_id} missing copy_phrase"

        return True, ""

    @staticmethod
    def calculate_phraseset_pool(copy_rounds: list[Round], settings) -> tuple[int, int, int]:
        """Calculate initial pool, system contribution, and second copy contribution."""
        copy1, copy2 = copy_rounds[0], copy_rounds[1]
        
        system_contribution = copy1.system_contribution + copy2.system_contribution
        initial_pool = settings.prize_pool_base
        
        # Check if both copies are from the same player (second copy feature)
        second_copy_contribution = 0
        if copy1.player_id == copy2.player_id:
            second_copy_contribution = settings.copy_cost_normal
            initial_pool += second_copy_contribution
            
        return initial_pool, system_contribution, second_copy_contribution


class RoundTimeoutHelper:
    """Helper class for handling round timeouts."""
    
    @staticmethod
    async def handle_prompt_timeout(round_object: Round, settings, transaction_service) -> int:
        """Handle timeout for prompt round."""
        round_object.status = "expired"
        round_object.phraseset_status = "abandoned"
        refund_amount = max(settings.prompt_cost - settings.abandoned_penalty, 0)

        await transaction_service.create_transaction(
            round_object.player_id,
            refund_amount,
            "refund",
            round_object.round_id,
        )
        
        return refund_amount

    @staticmethod
    async def handle_copy_timeout(db: AsyncSession, round_object: Round, settings, transaction_service, queue_service
                                  ) -> int:
        """Handle timeout for copy round."""
        round_object.status = "abandoned"
        refund_amount = max(round_object.cost - settings.abandoned_penalty, 0)

        await transaction_service.create_transaction(
            round_object.player_id,
            refund_amount,
            "refund",
            round_object.round_id,
        )

        # Return prompt to queue
        queue_service.add_prompt_round_to_queue(round_object.prompt_round_id)

        # Track abandonment for cooldown
        from backend.models.qf.player_abandoned_prompt import PlayerAbandonedPrompt
        import uuid
        
        abandonment = PlayerAbandonedPrompt(
            id=uuid.uuid4(),
            player_id=round_object.player_id,
            prompt_round_id=round_object.prompt_round_id,
        )
        db.add(abandonment)
        
        return refund_amount

    @staticmethod
    async def handle_vote_timeout(round_object: Round, settings, transaction_service) -> int:
        """Handle timeout for vote round."""
        round_object.status = "expired"
        refund_amount = max(round_object.cost - settings.abandoned_penalty, 0)

        await transaction_service.create_transaction(
            round_object.player_id,
            refund_amount,
            "refund",
            round_object.round_id,
        )
        
        return refund_amount


class QueueManagementHelper:
    """Helper class for queue management operations."""
    
    @staticmethod
    async def requeue_prompt_ids(queue_service, prompt_ids: list[UUID]) -> None:
        """Requeue a list of prompt IDs."""
        for prompt_id in prompt_ids:
            queue_service.add_prompt_round_to_queue(prompt_id)

    @staticmethod
    async def prefetch_prompt_rounds(db: AsyncSession, prompt_ids: list[UUID], prefetched_rounds: dict[UUID, Round]
                                     ) -> None:
        """Load prompt rounds for the provided IDs, updating the cache."""
        ids_to_fetch = [pid for pid in prompt_ids if pid not in prefetched_rounds]
        if not ids_to_fetch:
            return

        result = await db.execute(select(Round).where(Round.round_id.in_(ids_to_fetch)))
        prefetched_rounds.update(
            {round_obj.round_id: round_obj for round_obj in result.scalars()}
        )


async def generate_ai_hints_background(prompt_round_id: UUID) -> None:
    """Generate AI hints without blocking the prompt submission response."""

    from backend.database import AsyncSessionLocal
    from backend.services import AIService, AICopyError

    async with AsyncSessionLocal() as background_db:
        ai_service = AIService(background_db)

        try:
            prompt_round = await background_db.get(Round, prompt_round_id)
            if not prompt_round:
                logger.warning(f"{prompt_round_id=} not found for background AI hint generation")
                return

            await ai_service.generate_and_cache_phrases(prompt_round)
            logger.info(f"Generated and cached AI hints for {prompt_round_id=}")
        except AICopyError as exc:
            logger.warning(f"Failed to generate AI hints for {prompt_round_id=}: {exc}", exc_info=True)
        except Exception as exc:  # Catch-all to avoid unhandled background task errors
            logger.warning(f"Unexpected error during AI hint generation for {prompt_round_id=}: {exc}", exc_info=True)


async def revalidate_ai_hints_background(prompt_round_id: UUID) -> None:
    """Re-run AI hint validation in the background after the first copy submission."""

    from backend.database import AsyncSessionLocal
    from backend.services import AIService

    async with AsyncSessionLocal() as background_db:
        ai_service = AIService(background_db)

        try:
            prompt_round = await background_db.get(Round, prompt_round_id)
            if not prompt_round:
                logger.warning(
                    f"{prompt_round_id=} not found for background AI hint revalidation"
                )
                return

            await ai_service.revalidate_cached_phrases(prompt_round)
            logger.info(f"Revalidated cached AI hints for {prompt_round_id=}")
        except Exception as exc:  # Catch-all to avoid unhandled background task errors
            logger.warning(
                f"Unexpected error during AI hint revalidation for {prompt_round_id=}: {exc}",
                exc_info=True,
            )
