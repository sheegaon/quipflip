"""Player service for account management."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from datetime import datetime, UTC
from uuid import UUID
import uuid
import logging

from backend.models.qf.player import QFPlayer
from backend.models.qf.daily_bonus import QFDailyBonus
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.round import Round
from backend.config import get_settings
from backend.utils.exceptions import (
    DailyBonusNotAvailableError,
    UsernameTakenError,
    InvalidUsernameError,
)
from backend.utils.passwords import hash_password
from backend.services.player_service_base import PlayerServiceBase, PlayerServiceError
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    normalize_username,
    is_username_input_valid,
    is_username_profanity_free,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class PlayerError(PlayerServiceError):
    """Raised when QF player service fails."""


class PlayerService(PlayerServiceBase):
    """Service for managing players."""

    @property
    def player_model(self):
        """Return the QF player model class."""
        return QFPlayer

    @property
    def error_class(self):
        """Return the QF player error class."""
        return PlayerError

    @property
    def game_type(self):
        """Return the game type for this service."""
        from backend.services.auth_service import GameType
        return GameType.QF

    def get_guest_domain(self) -> str:
        """Get the domain for QF guest email addresses."""
        return "quipflip.xyz"

    def get_guest_password(self) -> str:
        """Get the default QF guest password."""
        return "Guest"

    def _get_initial_balance(self) -> int:
        """Get the initial balance for new QF players."""
        return settings.starting_balance

    def _should_be_admin(self, email: str | None) -> bool:
        """Determine if the provided email belongs to an administrator."""
        return settings.is_admin_email(email)

    async def get_player_by_id(self, player_id: UUID) -> QFPlayer | None:
        """Get player by ID."""
        result = await self.db.execute(
            select(QFPlayer).where(QFPlayer.player_id == player_id)
        )
        player = result.scalar_one_or_none()
        return self.apply_admin_status(player)

    async def get_player_by_username(self, username: str) -> QFPlayer | None:
        """Get player by username lookup."""
        if not is_username_input_valid(username):
            return None
        username_service = UsernameService(self.db)
        player = await username_service.find_player_by_username(username)
        return self.apply_admin_status(player)

    async def create_player(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
    ) -> QFPlayer:
        """Create new player using explicit credentials."""

        normalized_username = normalize_username(username)
        canonical_username = canonicalize_username(normalized_username)
        if not canonical_username:
            raise ValueError("invalid_username")

        player = QFPlayer(
            player_id=uuid.uuid4(),
            username=normalized_username,
            username_canonical=canonical_username,
            email=email.strip().lower(),
            password_hash=password_hash,
            wallet=settings.starting_balance,
            vault=0,
            last_login_date=datetime.now(UTC),  # Track creation login time with precision
            is_admin=self._should_be_admin(email),
        )
        self.db.add(player)
        try:
            await self.db.commit()
            await self.db.refresh(player)
            logger.info(
                f"Created player: {player.player_id} username={player.username} wallet={player.wallet} vault={player.vault}"
            )
            return player
        except IntegrityError as exc:
            await self._handle_integrity_error(exc, "create")

    async def update_username(self, player: QFPlayer, new_username: str) -> QFPlayer:
        """Update a player's username with QF-specific error handling."""
        try:
            return await super().update_username(player, new_username)
        except ValueError as e:
            error_msg = str(e)
            if "invalid characters" in error_msg:
                raise InvalidUsernameError("Username contains invalid characters or does not meet requirements")
            elif "inappropriate language" in error_msg:
                raise InvalidUsernameError("Username contains inappropriate language")
            elif "already in use" in error_msg:
                raise UsernameTakenError("Username is already in use by another player")
            raise

    async def is_daily_bonus_available(self, player: QFPlayer) -> bool:
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

    async def claim_daily_bonus(self, player: QFPlayer, transaction_service) -> int:
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
        logger.debug(f"Player {player_id} has {count} outstanding prompts")
        return count

    async def can_start_prompt_round(self, player: QFPlayer) -> tuple[bool, str]:
        """
        Check if player can start prompt round.

        Returns:
            (can_start, error_code)
        """
        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        # Check wallet (spendable balance)
        if player.wallet < settings.prompt_cost:
            return False, "insufficient_balance"

        # Check active round
        if player.active_round_id is not None:
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

    async def can_start_copy_round(self, player: QFPlayer) -> tuple[bool, str]:
        """Check if player can start copy round."""
        from backend.services.qf.queue_service import QueueService

        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        # Check wallet (spendable balance) against current copy cost
        copy_cost = QueueService.get_copy_cost()
        if player.wallet < copy_cost:
            return False, "insufficient_balance"

        # Check active round
        if player.active_round_id is not None:
            return False, "already_in_round"

        # Check prompts available
        if not QueueService.has_prompt_rounds_available():
            return False, "no_prompts_available"

        return True, ""

    async def can_start_second_copy_round(self, player: QFPlayer) -> tuple[bool, str]:
        """Check if player can start a second copy round (2x cost, no queue check)."""
        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        if player.active_round_id is not None:
            return False, "already_in_round"

        # Second copy costs 2x the normal cost
        second_copy_cost = settings.copy_cost_normal * 2
        if player.wallet < second_copy_cost:
            return False, "insufficient_balance"

        return True, ""

    async def can_start_vote_round(
        self,
        player: QFPlayer,
        vote_service=None,
        available_count: int | None = None,
    ) -> tuple[bool, str]:
        """Check if player can start vote round."""
        from backend.services.qf.queue_service import QueueService
        from datetime import datetime, UTC

        # Check if guest is locked out from voting
        if player.is_guest and player.vote_lockout_until:
            if datetime.now(UTC) < player.vote_lockout_until:
                return False, "vote_lockout_active"

        if player.locked_until and player.locked_until > datetime.now(UTC):
            return False, "player_locked"

        # Check wallet (spendable balance)
        if player.wallet < settings.vote_cost:
            return False, "insufficient_balance"

        # Check active round
        if player.active_round_id is not None:
            return False, "already_in_round"

        # Check phrasesets available
        if vote_service:
            if available_count is None:
                available_count = await vote_service.count_available_phrasesets_for_player(player.player_id)
            if available_count == 0:
                return False, "no_phrasesets_available"
        else:
            if not QueueService.has_phrasesets_available():
                return False, "no_phrasesets_available"

        return True, ""

