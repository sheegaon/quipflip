"""Player service for account management."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from datetime import date
from uuid import UUID
import uuid
import logging

from backend.models.player import Player
from backend.models.daily_bonus import DailyBonus
from backend.models.phraseset import PhraseSet
from backend.models.round import Round
from backend.config import get_settings
from backend.utils.exceptions import DailyBonusNotAvailableError
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    normalize_username,
    is_username_input_valid,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class PlayerService:
    """Service for managing players."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_player(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        pseudonym: str,
        pseudonym_canonical: str,
    ) -> Player:
        """Create new player using explicit credentials."""

        normalized_username = normalize_username(username)
        canonical_username = canonicalize_username(normalized_username)
        if not canonical_username:
            raise ValueError("invalid_username")

        player = Player(
            player_id=uuid.uuid4(),
            username=normalized_username,
            username_canonical=canonical_username,
            pseudonym=pseudonym,
            pseudonym_canonical=pseudonym_canonical,
            email=email.strip().lower(),
            password_hash=password_hash,
            balance=settings.starting_balance,
            last_login_date=date.today(),  # Set to today so no bonus on creation
        )
        self.db.add(player)
        try:
            await self.db.commit()
            await self.db.refresh(player)
            logger.info(
                "Created player: %s username=%s pseudonym=%s balance=%s",
                player.player_id,
                player.username,
                player.pseudonym,
                player.balance,
            )
            return player
        except IntegrityError as exc:
            await self.db.rollback()
            error_message = str(exc).lower()
            if "uq_players_username" in error_message or "uq_players_username_canonical" in error_message:
                raise ValueError("username_taken") from exc
            if "uq_players_email" in error_message or "email" in error_message:
                raise ValueError("email_taken") from exc
            raise

    async def get_player_by_id(self, player_id: UUID) -> Player | None:
        """Get player by ID."""
        result = await self.db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        return result.scalar_one_or_none()

    async def get_player_by_username(self, username: str) -> Player | None:
        """Get player by username lookup."""
        if not is_username_input_valid(username):
            return None
        username_service = UsernameService(self.db)
        return await username_service.find_player_by_username(username)

    async def is_daily_bonus_available(self, player: Player) -> bool:
        """Check if daily bonus can be claimed."""
        today = date.today()

        # No bonus on creation date
        if player.created_at.date() == today:
            return False

        # Check if bonus was already claimed today by querying the DailyBonus table
        result = await self.db.execute(
            select(DailyBonus)
            .where(DailyBonus.player_id == player.player_id)
            .where(DailyBonus.date == today)
        )
        bonus_today = result.scalar_one_or_none()

        # Bonus available if NOT claimed today
        return bonus_today is None

    async def claim_daily_bonus(self, player: Player, transaction_service) -> int:
        """
        Claim daily bonus, returns amount.

        Raises:
            DailyBonusNotAvailableError: If bonus not available
        """
        if not await self.is_daily_bonus_available(player):
            raise DailyBonusNotAvailableError("Daily bonus not available")

        today = date.today()

        # Create bonus record
        bonus = DailyBonus(
            bonus_id=uuid.uuid4(),
            player_id=player.player_id,
            amount=settings.daily_bonus_amount,
            date=today,
        )
        self.db.add(bonus)

        # Create transaction
        await transaction_service.create_transaction(
            player.player_id,
            settings.daily_bonus_amount,
            "daily_bonus",
            bonus.bonus_id,
        )

        await self.db.commit()

        # Track quest progress for login streak
        from backend.services.quest_service import QuestService
        quest_service = QuestService(self.db)
        try:
            await quest_service.check_login_streak(player.player_id)
        except Exception as e:
            logger.error(f"Failed to update quest progress for login: {e}", exc_info=True)

        logger.info(f"Player {player.player_id} claimed daily bonus: ${settings.daily_bonus_amount}")
        return settings.daily_bonus_amount

    async def get_outstanding_prompts_count(self, player_id: UUID) -> int:
        """Count phrasesets player created that are still open/closing."""
        # Find all rounds where player was the prompt player
        prompt_rounds_subq = (
            select(Round.round_id)
            .where(Round.player_id == player_id)
            .where(Round.round_type == "prompt")
            .where(Round.status == "submitted")
            .subquery()
        )

        # Count phrasesets linked to those rounds that are open/closing
        result = await self.db.execute(
            select(func.count(PhraseSet.phraseset_id))
            .where(PhraseSet.prompt_round_id.in_(select(prompt_rounds_subq)))
            .where(PhraseSet.status.in_(["open", "closing"]))
        )
        count = result.scalar() or 0
        logger.debug(f"Player {player_id} has {count} outstanding prompts")
        return count

    async def can_start_prompt_round(self, player: Player) -> tuple[bool, str]:
        """
        Check if player can start prompt round.

        Returns:
            (can_start, error_code)
        """
        # Check balance
        if player.balance < settings.prompt_cost:
            return False, "insufficient_balance"

        # Check active round
        if player.active_round_id is not None:
            return False, "already_in_round"

        # Check outstanding prompts
        count = await self.get_outstanding_prompts_count(player.player_id)
        if count >= settings.max_outstanding_quips:
            return False, "max_outstanding_quips"

        return True, ""

    async def can_start_copy_round(self, player: Player) -> tuple[bool, str]:
        """Check if player can start copy round."""
        from backend.services.queue_service import QueueService

        # Check balance (need to check against current cost)
        copy_cost = QueueService.get_copy_cost()
        if player.balance < copy_cost:
            return False, "insufficient_balance"

        # Check active round
        if player.active_round_id is not None:
            return False, "already_in_round"

        # Check prompts available
        if not QueueService.has_prompts_available():
            return False, "no_prompts_available"

        return True, ""

    async def can_start_vote_round(
        self,
        player: Player,
        vote_service=None,
        available_count: int | None = None,
    ) -> tuple[bool, str]:
        """Check if player can start vote round."""
        from backend.services.queue_service import QueueService

        # Check balance
        if player.balance < settings.vote_cost:
            return False, "insufficient_balance"

        # Check active round
        if player.active_round_id is not None:
            return False, "already_in_round"

        # Check phrasesets available
        if vote_service:
            if available_count is None:
                available_count = await vote_service.count_available_wordsets_for_player(player.player_id)
            if available_count == 0:
                return False, "no_wordsets_available"
        else:
            if not QueueService.has_wordsets_available():
                return False, "no_wordsets_available"

        return True, ""

