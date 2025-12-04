"""Base player service with common functionality."""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import TYPE_CHECKING, Type, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.config import get_settings
from backend.services.ai.openai_api import OpenAIAPIError
from backend.utils.model_registry import GameType
from backend.utils.passwords import hash_password
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    normalize_username,
    is_username_input_valid,
    is_username_allowed,
)

if TYPE_CHECKING:
    from backend.models.player_base import PlayerBase
    from backend.models.player import Player

logger = logging.getLogger(__name__)


class PlayerServiceError(RuntimeError):
    """Base exception for player service errors."""


class PlayerError(PlayerServiceError):
    """Raised when player service fails."""


class PlayerServiceBase(ABC):
    """Base service for managing player accounts."""

    def __init__(self, db: AsyncSession):
        """Initialize player service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()

    @property
    @abstractmethod
    def player_model(self) -> Type[Any]:
        """Return the player model class for this service."""
        pass

    @property
    @abstractmethod
    def error_class(self) -> Type[Exception]:
        """Return the error class for this service."""
        pass

    @property
    @abstractmethod
    def game_type(self) -> GameType:
        """Return the game type for this service."""
        pass

    @property
    @abstractmethod
    def player_data_model(self) -> Type[Any]:
        """Return the game-specific player data model class for this service."""
        pass

    def apply_admin_status(self, player: "PlayerBase | None") -> "PlayerBase | None":
        """Ensure the player's admin flag reflects configuration."""
        if not player:
            return None
        player.is_admin = self._should_be_admin(player.email)
        return player

    async def get_player_by_id(self, player_id: str) -> "PlayerBase | None":
        """Get player by ID.

        Args:
            player_id: Player UUID

        Returns:
            Player or None if not found
        """
        stmt = select(self.player_model).where(self.player_model.player_id == player_id)
        result = await self.db.execute(stmt)
        player = result.scalars().first()
        return self.apply_admin_status(player)

    async def get_player_by_username(self, username: str) -> "PlayerBase | None":
        """Get player by username.

        Args:
            username: Username to search

        Returns:
            Player or None if not found
        """
        if not is_username_input_valid(username):
            return None
        
        username_canonical = canonicalize_username(username)
        stmt = select(self.player_model).where(self.player_model.username_canonical == username_canonical)
        result = await self.db.execute(stmt)
        player = result.scalars().first()
        return self.apply_admin_status(player)

    async def get_player_by_email(self, email: str) -> "PlayerBase | None":
        """Get player by email.

        Args:
            email: Email address

        Returns:
            Player or None if not found
        """
        normalized_email = email.strip().lower()
        if not normalized_email:
            return None

        stmt = select(self.player_model).where(self.player_model.email == normalized_email)
        result = await self.db.execute(stmt)
        player = result.scalars().first()
        return self.apply_admin_status(player)

    async def update_last_login(self, player_id: str) -> "PlayerBase":
        """Update player last login timestamp.

        Args:
            player_id: Player UUID

        Returns:
            Player: Updated player

        Raises:
            PlayerServiceError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise self.error_class("player_not_found")

        player.last_login_date = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def update_email(self, player: "PlayerBase", new_email: str) -> "PlayerBase":
        """Update a player's email address."""
        normalized_email = new_email.strip().lower()
        if not normalized_email:
            raise ValueError("invalid_email")

        player.email = normalized_email
        player.is_admin = self._should_be_admin(normalized_email)

        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self._handle_integrity_error(exc, "update")

        await self.db.refresh(player)
        return player

    async def update_password(self, player: "PlayerBase", new_password: str) -> None:
        """Update a player's password hash."""
        player.password_hash = hash_password(new_password)
        await self.db.commit()
        await self.db.refresh(player)

    async def update_username(self, player: "PlayerBase", new_username: str) -> "PlayerBase":
        """Update a player's username."""
        # Validate input
        if not is_username_input_valid(new_username):
            raise ValueError("Username contains invalid characters or does not meet requirements")

        # Check for moderation issues via OpenAI
        try:
            is_allowed = await is_username_allowed(new_username)
        except OpenAIAPIError as exc:
            logger.error(f"Username moderation failed: {exc}")
            raise ValueError("Username failed safety checks") from exc
        if not is_allowed:
            raise ValueError("Username failed safety checks")

        # Normalize and canonicalize
        normalized_username = normalize_username(new_username)
        canonical_username = canonicalize_username(normalized_username)

        # Update both display and canonical versions
        player.username = normalized_username
        player.username_canonical = canonical_username

        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            # Check constraint name from the exception if available
            constraint_name = None
            if hasattr(exc.orig, 'diag') and hasattr(exc.orig.diag, 'constraint_name'):
                constraint_name = exc.orig.diag.constraint_name

            # Fall back to string matching if constraint name not available
            if constraint_name in ('uq_players_username_canonical', 'uq_players_username'):
                raise ValueError("Username is already in use by another player") from exc

            error_message = str(exc).lower()
            if "uq_players_username" in error_message or "uq_players_username_canonical" in error_message:
                raise ValueError("Username is already in use by another player") from exc
            raise

        await self.db.refresh(player)
        return player

    async def refresh_vote_lockout_state(self, player: "PlayerBase") -> bool:
        """Clear expired vote lockouts for guest players."""
        if not player.is_guest:
            return False

        result = await self.db.execute(
            select(self.player_data_model).where(
                self.player_data_model.player_id == player.player_id
            )
        )
        player_data = result.scalar_one_or_none()

        if not player_data or not player_data.vote_lockout_until:
            return False

        current_time = datetime.now(UTC)
        if current_time < player_data.vote_lockout_until:
            return False

        player_data.vote_lockout_until = None
        player_data.consecutive_incorrect_votes = 0
        await self.db.commit()
        await self.db.refresh(player_data)

        logger.info(f"Cleared expired vote lockout for guest {player.player_id}")
        return True

    async def update_wallet(self, player_id: str, amount: int) -> "PlayerBase":
        """Update player wallet balance.

        Args:
            player_id: Player UUID
            amount: Amount to add (can be negative)

        Returns:
            Player: Updated player

        Raises:
            PlayerServiceError: If player not found or update fails
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise self.error_class("player_not_found")

        # Load game-specific player data for wallet update
        result = await self.db.execute(
            select(self.player_data_model).where(
                self.player_data_model.player_id == player_id
            )
        )
        player_data = result.scalar_one_or_none()

        if not player_data:
            raise self.error_class("player_data_not_found")

        # Update wallet in PlayerData
        player_data.wallet = max(0, player_data.wallet + amount)
        await self.db.commit()
        await self.db.refresh(player_data)
        return player

    async def update_vault(self, player_id: str, amount: int) -> "PlayerBase":
        """Update player vault balance.

        Args:
            player_id: Player UUID
            amount: Amount to add (can be negative)

        Returns:
            Player: Updated player

        Raises:
            PlayerServiceError: If player not found or update fails
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise self.error_class("player_not_found")

        # Load game-specific player data for vault update
        result = await self.db.execute(
            select(self.player_data_model).where(
                self.player_data_model.player_id == player_id
            )
        )
        player_data = result.scalar_one_or_none()

        if not player_data:
            raise self.error_class("player_data_not_found")

        # Update vault in PlayerData
        player_data.vault = max(0, player_data.vault + amount)
        await self.db.commit()
        await self.db.refresh(player_data)
        return player

    async def transfer_wallet_to_vault(self, player_id: str, amount: int) -> "PlayerBase":
        """Transfer amount from wallet to vault (rake operation).

        Args:
            player_id: Player UUID
            amount: Amount to transfer

        Returns:
            Player: Updated player

        Raises:
            PlayerServiceError: If insufficient wallet balance
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise self.error_class("player_not_found")

        # Load game-specific player data for wallet/vault transfer
        result = await self.db.execute(
            select(self.player_data_model).where(
                self.player_data_model.player_id == player_id
            )
        )
        player_data = result.scalar_one_or_none()

        if not player_data:
            raise self.error_class("player_data_not_found")

        if player_data.wallet < amount:
            raise self.error_class("insufficient_wallet_balance")

        # Transfer from wallet to vault in PlayerData
        player_data.wallet -= amount
        player_data.vault += amount
        await self.db.commit()
        await self.db.refresh(player_data)
        return player

    async def register_guest(self) -> tuple["PlayerBase", str]:
        """Create a guest account with auto-generated credentials.

        Returns:
            tuple[Player, str]: Created player and auto-generated password

        Raises:
            PlayerServiceError: If guest creation fails
        """
        import random

        # Generate random 4-digit number for email
        random_digits = str(random.randint(1000, 9999))
        guest_email = f"guest{random_digits}@{self.get_guest_domain()}"
        guest_password = self.get_guest_password()

        password_hash = hash_password(guest_password)

        # Generate unique username
        username_service = UsernameService(self.db, game_type=self.game_type)
        username_display, username_canonical = await username_service.generate_unique_username()

        # Try to create guest account, retry with new email if collision
        max_retries = 10
        initial_balance = self._get_initial_balance()

        for attempt in range(max_retries):
            try:
                player_id = str(uuid.uuid4())
                player = self.player_model(
                    player_id=player_id,
                    username=username_display,
                    username_canonical=username_canonical,
                    email=guest_email,
                    password_hash=password_hash,
                    created_at=datetime.now(UTC),
                    is_guest=True,
                    is_admin=False,
                )
                self.db.add(player)

                # Also create game-specific player data record
                player_data = self.player_data_model(
                    player_id=player_id,
                    wallet=initial_balance,
                    vault=0,
                )
                self.db.add(player_data)

                await self.db.commit()
                await self.db.refresh(player)

                logger.info(f"Created guest {player_id=} with email {guest_email}")
                return player, guest_password

            except Exception as e:
                if "email" in str(e).lower() and attempt < max_retries - 1:
                    # Generate new random number and retry
                    random_digits = str(random.randint(1000, 9999))
                    guest_email = f"guest{random_digits}@{self.get_guest_domain()}"
                    await self.db.rollback()
                    continue
                else:
                    await self.db.rollback()
                    raise self.error_class("guest_creation_failed") from e

        raise self.error_class("guest_creation_failed_max_retries")

    async def upgrade_guest_to_full(
        self, player: "PlayerBase", email: str, password_hash: str
    ) -> "PlayerBase":
        """Upgrade a guest player to a full account with email/password."""

        if not player.is_guest:
            raise self.error_class("not_a_guest")

        normalized_email = email.strip().lower()
        stmt = select(self.player_model).where(self.player_model.email == normalized_email)
        result = await self.db.execute(stmt)
        existing = result.scalars().first()
        if existing and existing.player_id != player.player_id:
            raise self.error_class("email_taken")

        player.email = normalized_email
        player.password_hash = password_hash
        player.is_guest = False
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def create_player(
        self,
        username: str,
        email: str,
        password_hash: str,
        is_guest: bool = False,
    ) -> "PlayerBase":
        """Create a new player account.

        Args:
            username: Display username
            email: Email address
            password_hash: Hashed password
            is_guest: Whether this is a guest account

        Returns:
            Player: Created player

        Raises:
            PlayerServiceError: If player creation fails
        """
        normalized_email = email.strip().lower()
        normalized_username = normalize_username(username)
        username_canonical = canonicalize_username(normalized_username)

        if not username_canonical:
            raise ValueError("invalid_username")

        try:
            # Check if email is taken
            stmt = select(self.player_model).where(self.player_model.email == normalized_email)
            result = await self.db.execute(stmt)
            if result.scalars().first():
                raise self.error_class("email_taken")

            # Check if username is taken
            stmt = select(self.player_model).where(self.player_model.username_canonical == username_canonical)
            result = await self.db.execute(stmt)
            if result.scalars().first():
                raise self.error_class("username_taken")

            # Create new player
            player_id = str(uuid.uuid4())
            initial_balance = self._get_initial_balance()

            player = self.player_model(
                player_id=player_id,
                username=normalized_username,
                username_canonical=username_canonical,
                email=normalized_email,
                password_hash=password_hash,
                created_at=datetime.now(UTC),
                is_guest=is_guest,
                is_admin=self._should_be_admin(normalized_email) if not is_guest else False,
            )
            self.db.add(player)

            # Also create game-specific player data record
            player_data = self.player_data_model(
                player_id=player_id,
                wallet=initial_balance,
                vault=0,
            )
            self.db.add(player_data)

            await self.db.commit()
            await self.db.refresh(player)

            logger.info(f"Created {player_id=} with username {normalized_username} (guest: {is_guest})")
            return player

        except (ValueError, self.error_class):
            await self.db.rollback()
            raise
        except IntegrityError as exc:
            await self._handle_integrity_error(exc, "create")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating player: {e}", exc_info=True)
            raise self.error_class(f"player_creation_failed: {str(e)}") from e

    async def is_daily_bonus_available(self, player: "PlayerBase") -> bool:
        """Check if daily bonus can be claimed.
        
        Base implementation returns False. Games with daily bonus systems
        should override this method.
        
        Args:
            player: Player to check
            
        Returns:
            bool: True if daily bonus is available
        """
        return False

    async def claim_daily_bonus(self, player: "PlayerBase", transaction_service=None) -> int:
        """Claim daily bonus for player.
        
        Base implementation raises NotImplementedError. Games with daily bonus
        systems should override this method.
        
        Args:
            player: Player claiming bonus
            transaction_service: Transaction service for recording the bonus
            
        Returns:
            int: Amount of bonus claimed
            
        Raises:
            NotImplementedError: If game doesn't implement daily bonuses
        """
        raise NotImplementedError("Daily bonus system not implemented for this game")

    async def get_outstanding_prompts_count(self, player_id: str) -> int:
        """Get count of outstanding prompts/tasks for player.
        
        Base implementation returns 0. Games with prompt/task systems
        should override this method.
        
        Args:
            player_id: Player UUID
            
        Returns:
            int: Number of outstanding prompts/tasks
        """
        return 0

    def _should_be_admin(self, email: str) -> bool:
        """Determine if the provided email belongs to an administrator.
        
        Default implementation returns False. Subclasses should override
        if they have admin logic.
        """
        return self.settings.is_admin_email(email)

    def get_guest_domain(self) -> str:
        """Get the domain for guest email addresses."""
        return "quipflip.xyz"

    def get_guest_password(self) -> str:
        """Get the default guest password."""
        return self.settings.guest_password

    def _get_initial_balance(self) -> int:
        """Get the initial balance for new players."""
        return 0

    async def _handle_integrity_error(self, exc: IntegrityError, operation: str = "operation"):
        """Handle common integrity errors with consistent error messages."""
        await self.db.rollback()
        error_message = str(exc).lower()
        
        if "username" in error_message:
            if operation == "create":
                raise ValueError("username_taken") from exc
            else:
                raise self.error_class("username_taken") from exc
        
        if "email" in error_message:
            if operation == "create":
                raise ValueError("email_taken") from exc
            else:
                raise self.error_class("email_taken") from exc
        
        raise
