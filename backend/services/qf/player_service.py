"""Player service for account management."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from datetime import datetime, UTC
from uuid import UUID
import uuid
import logging

from backend.models.player import Player
from backend.models.qf.player_data import QFPlayerData
from backend.models.qf.daily_bonus import QFDailyBonus
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.round import Round
from backend.config import get_settings
from backend.utils.exceptions import (
    DailyBonusNotAvailableError,
    UsernameTakenError,
    InvalidUsernameError,
)
from backend.services.player_service_base import PlayerServiceBase, PlayerError
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    normalize_username,
    is_username_input_valid,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class QFPlayerService(PlayerServiceBase):
    """Service for managing players."""

    @property
    def player_model(self):
        """Return the unified player model class."""
        return Player

    @property
    def player_data_model(self):
        """Return the QF player data model class."""
        return QFPlayerData

    @property
    def error_class(self):
        """Return the QF player error class."""
        return PlayerError

    @property
    def game_type(self):
        """Return the game type for this service."""
        from backend.utils.model_registry import GameType
        return GameType.QF

    def _get_initial_balance(self) -> int:
        """Get the initial balance for new QF players."""
        return settings.qf_starting_wallet

    async def get_player_by_id(self, player_id: UUID) -> Player | None:
        """Get player by ID."""
        result = await self.db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        player = result.scalar_one_or_none()
        return self.apply_admin_status(player)

    async def get_player_by_username(self, username: str) -> Player | None:
        """Get player by username lookup."""
        if not is_username_input_valid(username):
            return None
        username_service = UsernameService(self.db)
        player = await username_service.find_player_by_username(username)
        return self.apply_admin_status(player)

    async def create_player(self, *, username: str, email: str, password_hash: str) -> Player:
        """Create new Quipflip player using explicit credentials."""
        return await super().create_player(
            username=username,
            email=email,
            password_hash=password_hash,
        )

    async def update_username(self, player: Player, new_username: str) -> Player:
        """Update a player's username with QF-specific error handling."""
        try:
            return await super().update_username(player, new_username)
        except ValueError as e:
            error_msg = str(e)
            if "invalid characters" in error_msg:
                raise InvalidUsernameError("Username contains invalid characters or does not meet requirements")
            elif "inappropriate language" in error_msg or "safety checks" in error_msg:
                raise InvalidUsernameError("Username contains inappropriate language")
            elif "already in use" in error_msg:
                raise UsernameTakenError("Username is already in use by another player")
            raise

    async def is_daily_bonus_available(self, player: Player) -> bool:
        """Check if daily bonus can be claimed."""
        # Use UTC for "today" to match how timestamps are stored.
        # ``date.today()`` relies on the server's local timezone, which
        # could allow newly created users to claim the bonus if the server
        # is running behind UTC. Since ``created_at`` is stored in UTC,
        # convert the current time to UTC before comparing dates.
        today = datetime.now(UTC).date()

        # Guest players cannot claim daily bonuses
        if player.is_guest:
            return False

        # No bonus on creation date
        if player.created_at.date() == today:
            return False

        # Check if bonus was already claimed today by querying the DailyBonus table
        result = await self.db.execute(
            select(QFDailyBonus)
            .where(QFDailyBonus.player_id == player.player_id)
            .where(QFDailyBonus.date == today)
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

        today = datetime.now(UTC).date()

        # Create bonus record
        bonus = QFDailyBonus(
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
        from backend.services.qf.quest_service import QuestService
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
            select(func.count(Phraseset.phraseset_id))
            .where(Phraseset.prompt_round_id.in_(select(prompt_rounds_subq)))
            .where(Phraseset.status.in_(["open", "closing"]))
        )
        count = result.scalar() or 0
        logger.info(f"Player {player_id} has {count} outstanding prompts")
        return count

    async def can_start_prompt_round(self, player: Player) -> tuple[bool, str]:
        """
        Check if player can start prompt round.

        Returns:
            (can_start, error_code)
        """
        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        # Load game-specific player data for wallet and active_round_id
        result = await self.db.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()

        wallet = player_data.wallet if player_data else settings.qf_starting_wallet
        active_round_id = player_data.active_round_id if player_data else None

        # Check wallet (spendable balance)
        if wallet < settings.prompt_cost:
            return False, "insufficient_balance"

        # Check active round
        if active_round_id is not None:
            return False, "already_in_round"

        # Check outstanding prompts (guests have a lower limit)
        count = await self.get_outstanding_prompts_count(player.player_id)
        max_outstanding = (
            settings.guest_max_outstanding_quips
            if player.is_guest
            else settings.max_outstanding_quips
        )
        if count >= max_outstanding:
            return False, "max_outstanding_quips"

        return True, ""

    async def can_start_copy_round(self, player: Player) -> tuple[bool, str]:
        """Check if player can start copy round."""
        from backend.services.qf.queue_service import QFQueueService
        from backend.services.qf.round_service import QFRoundService

        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        # Load game-specific player data for wallet and active_round_id
        result = await self.db.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()

        wallet = player_data.wallet if player_data else settings.qf_starting_wallet
        active_round_id = player_data.active_round_id if player_data else None

        # Check wallet (spendable balance) against current copy cost
        copy_cost = QFQueueService.get_copy_cost()
        if wallet < copy_cost:
            return False, "insufficient_balance"

        # Check active round
        if active_round_id is not None:
            return False, "already_in_round"

        # Check prompts available for this player specifically (not just queue length)
        round_service = QFRoundService(self.db)
        available_prompts = await round_service.get_available_prompts_count(player.player_id)
        if available_prompts <= 0:
            return False, "no_prompts_available"

        return True, ""

    async def can_start_second_copy_round(self, player: Player) -> tuple[bool, str]:
        """Check if player can start a second copy round (2x cost, no queue check)."""
        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        # Load game-specific player data for wallet and active_round_id
        result = await self.db.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()

        wallet = player_data.wallet if player_data else settings.qf_starting_wallet
        active_round_id = player_data.active_round_id if player_data else None

        if active_round_id is not None:
            return False, "already_in_round"

        # Second copy costs 2x the normal cost
        second_copy_cost = settings.copy_cost_normal * 2
        if wallet < second_copy_cost:
            return False, "insufficient_balance"

        return True, ""

    async def can_start_vote_round(
        self,
        player: Player,
        vote_service=None,
        available_count: int | None = None,
    ) -> tuple[bool, str]:
        """Check if player can start vote round."""
        from backend.services.qf.queue_service import QFQueueService

        # Refresh vote lockout state for guests (clears expired lockouts)
        if player.is_guest:
            await self.refresh_vote_lockout_state(player)

        # Load game-specific player data for wallet, active_round_id, and vote_lockout_until
        result = await self.db.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()

        wallet = player_data.wallet if player_data else settings.qf_starting_wallet
        active_round_id = player_data.active_round_id if player_data else None
        vote_lockout_until = player_data.vote_lockout_until if player_data else None

        # Check if guest is locked out from voting
        if player.is_guest and vote_lockout_until:
            if datetime.now(UTC) < vote_lockout_until:
                return False, "vote_lockout_active"

        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        # Check wallet (spendable balance)
        if wallet < settings.vote_cost:
            return False, "insufficient_balance"

        # Check active round
        if active_round_id is not None:
            return False, "already_in_round"

        # Check phrasesets available
        if vote_service:
            if available_count is None:
                available_count = await vote_service.count_available_phrasesets_for_player(player.player_id)
            if available_count == 0:
                return False, "no_phrasesets_available"
        else:
            if not QFQueueService.has_phrasesets_available():
                return False, "no_phrasesets_available"

        return True, ""

    async def refresh_vote_lockout_state(self, player: Player) -> bool:
        """
        Refresh vote lockout state for guest players.
        
        Clears expired lockouts and resets consecutive incorrect votes.
        Only applies to guest players.
        
        Returns:
            bool: True if lockout was cleared, False if no change
        """
        if not player.is_guest:
            return False

        # Load player data
        result = await self.db.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()
        
        if not player_data or not player_data.vote_lockout_until:
            return False

        # Check if lockout has expired
        if datetime.now(UTC) >= player_data.vote_lockout_until:
            # Clear expired lockout
            player_data.vote_lockout_until = None
            player_data.consecutive_incorrect_votes = 0
            await self.db.commit()
            logger.info(f"Cleared expired vote lockout for guest player {player.player_id}")
            return True

        return False

    async def track_incorrect_vote(self, player: Player) -> None:
        """
        Track an incorrect vote for a guest player.
        
        Increments consecutive incorrect votes and applies lockout if threshold is reached.
        Only applies to guest players.
        """
        if not player.is_guest:
            return

        # Load or create player data
        result = await self.db.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()
        
        if not player_data:
            player_data = QFPlayerData(player_id=player.player_id)
            self.db.add(player_data)

        # Increment consecutive incorrect votes
        player_data.consecutive_incorrect_votes = (player_data.consecutive_incorrect_votes or 0) + 1

        # Apply lockout if threshold reached
        if player_data.consecutive_incorrect_votes >= settings.guest_vote_lockout_threshold:
            from datetime import timedelta
            player_data.vote_lockout_until = datetime.now(UTC) + timedelta(hours=settings.guest_vote_lockout_hours)
            logger.info(f"Applied vote lockout to guest player {player.player_id} for {settings.guest_vote_lockout_hours} hours")

        await self.db.commit()

    async def reset_incorrect_vote_count(self, player: Player) -> None:
        """
        Reset consecutive incorrect vote count for a guest player.
        
        Called when a guest makes a correct vote.
        Only applies to guest players.
        """
        if not player.is_guest:
            return

        # Load player data
        result = await self.db.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()
        
        if player_data and player_data.consecutive_incorrect_votes > 0:
            player_data.consecutive_incorrect_votes = 0
            # Also clear any active lockout since they got a correct vote
            player_data.vote_lockout_until = None
            await self.db.commit()
            logger.info(f"Reset consecutive incorrect vote count for guest player {player.player_id}")
