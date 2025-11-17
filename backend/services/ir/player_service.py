"""IR Player Service - Manages Initial Reaction player accounts and wallets."""

import logging
import random
import uuid
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.models.ir.ir_player import IRPlayer
from backend.utils.passwords import hash_password, verify_password, validate_password_strength, PasswordValidationError
from backend.services.username_service import canonicalize_username, normalize_username, UsernameService

logger = logging.getLogger(__name__)


class IRPlayerError(RuntimeError):
    """Raised when IR player service fails."""


class IRPlayerService:
    """Service for managing IR player accounts and wallets."""

    def __init__(self, db: AsyncSession):
        """Initialize IR player service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()

    async def create_player(
        self,
        username: str,
        email: str,
        password_hash: str,
    ) -> IRPlayer:
        """Create a new IR player account.

        Args:
            username: Display username
            email: Email address
            password_hash: Hashed password

        Returns:
            IRPlayer: Created player

        Raises:
            IRPlayerError: If player creation fails
        """
        normalized_email = email.strip().lower()

        try:
            # Check if email is taken (case-insensitive storage)
            stmt = select(IRPlayer).where(IRPlayer.email == normalized_email)
            result = await self.db.execute(stmt)
            if result.scalars().first():
                raise IRPlayerError("email_taken")

            # Normalize and check username
            username_canonical = canonicalize_username(username)
            stmt = select(IRPlayer).where(IRPlayer.username_canonical == username_canonical)
            result = await self.db.execute(stmt)
            if result.scalars().first():
                raise IRPlayerError("username_taken")

            # Create new player
            player_id = str(uuid.uuid4())
            player = IRPlayer(
                player_id=player_id,
                username=username,
                username_canonical=username_canonical,
                email=normalized_email,
                password_hash=password_hash,
                wallet=self.settings.ir_initial_balance,
                vault=0,
                created_at=datetime.now(UTC),
                is_guest=False,
                is_admin=False,
            )
            self.db.add(player)
            await self.db.commit()
            await self.db.refresh(player)

            logger.info(f"Created IR player {player_id} with username {username}")
            return player
        except IRPlayerError:
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating IR player: {e}", exc_info=True)
            raise IRPlayerError(f"player_creation_failed: {str(e)}") from e

    async def get_player_by_id(self, player_id: str) -> IRPlayer | None:
        """Get IR player by ID.

        Args:
            player_id: Player UUID

        Returns:
            IRPlayer or None if not found
        """
        stmt = select(IRPlayer).where(IRPlayer.player_id == player_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_player_by_username(self, username: str) -> IRPlayer | None:
        """Get IR player by username.

        Args:
            username: Username to search

        Returns:
            IRPlayer or None if not found
        """
        username_canonical = canonicalize_username(username)
        stmt = select(IRPlayer).where(IRPlayer.username_canonical == username_canonical)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_player_by_email(self, email: str) -> IRPlayer | None:
        """Get IR player by email.

        Args:
            email: Email address

        Returns:
            IRPlayer or None if not found
        """
        normalized_email = email.strip().lower()
        if not normalized_email:
            return None

        stmt = select(IRPlayer).where(IRPlayer.email == normalized_email)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def register_guest(self) -> tuple[IRPlayer, str]:
        """Create a guest account with auto-generated credentials.

        Returns:
            tuple[IRPlayer, str]: Created player and auto-generated password

        Raises:
            IRPlayerError: If guest creation fails
        """
        # Generate random 4-digit number for email
        random_digits = str(random.randint(1000, 9999))
        guest_email = f"ir_guest{random_digits}@initialreaction.xyz"
        guest_password = "IRGuest"

        password_hash = hash_password(guest_password)

        # Generate unique username
        username_service = UsernameService(self.db)
        username_display, username_canonical = await username_service.generate_unique_username()

        # Try to create guest account, retry with new email if collision
        max_retries = 10
        for attempt in range(max_retries):
            try:
                player_id = str(uuid.uuid4())
                player = IRPlayer(
                    player_id=player_id,
                    username=username_display,
                    username_canonical=username_canonical,
                    email=guest_email,
                    password_hash=password_hash,
                    wallet=self.settings.ir_initial_balance,
                    vault=0,
                    created_at=datetime.now(UTC),
                    is_guest=True,
                    is_admin=False,
                )
                self.db.add(player)
                await self.db.commit()
                await self.db.refresh(player)

                logger.info(f"Created IR guest player {player_id} with email {guest_email}")
                return player, guest_password

            except Exception as e:
                if "email" in str(e).lower() and attempt < max_retries - 1:
                    # Generate new random number and retry
                    random_digits = str(random.randint(1000, 9999))
                    guest_email = f"ir_guest{random_digits}@initialreaction.xyz"
                    await self.db.rollback()
                    continue
                else:
                    await self.db.rollback()
                    raise IRPlayerError("guest_creation_failed") from e

        raise IRPlayerError("guest_creation_failed_max_retries")

    async def upgrade_guest_to_full(
        self, player: IRPlayer, email: str, password_hash: str
    ) -> IRPlayer:
        """Upgrade a guest player to a full account with email/password."""

        if not player.is_guest:
            raise IRPlayerError("not_a_guest")

        normalized_email = email.strip().lower()
        stmt = select(IRPlayer).where(IRPlayer.email == normalized_email)
        result = await self.db.execute(stmt)
        existing = result.scalars().first()
        if existing and existing.player_id != player.player_id:
            raise IRPlayerError("email_taken")

        player.email = normalized_email
        player.password_hash = password_hash
        player.is_guest = False
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def update_wallet(self, player_id: str, amount: int) -> IRPlayer:
        """Update player wallet balance.

        Args:
            player_id: Player UUID
            amount: Amount to add (can be negative)

        Returns:
            IRPlayer: Updated player

        Raises:
            IRPlayerError: If player not found or update fails
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise IRPlayerError("player_not_found")

        player.wallet = max(0, player.wallet + amount)
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def update_vault(self, player_id: str, amount: int) -> IRPlayer:
        """Update player vault balance.

        Args:
            player_id: Player UUID
            amount: Amount to add (can be negative)

        Returns:
            IRPlayer: Updated player

        Raises:
            IRPlayerError: If player not found or update fails
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise IRPlayerError("player_not_found")

        player.vault = max(0, player.vault + amount)
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def transfer_wallet_to_vault(self, player_id: str, amount: int) -> IRPlayer:
        """Transfer amount from wallet to vault (rake operation).

        Args:
            player_id: Player UUID
            amount: Amount to transfer

        Returns:
            IRPlayer: Updated player

        Raises:
            IRPlayerError: If insufficient wallet balance
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise IRPlayerError("player_not_found")

        if player.wallet < amount:
            raise IRPlayerError("insufficient_wallet_balance")

        player.wallet -= amount
        player.vault += amount
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def update_last_login(self, player_id: str) -> IRPlayer:
        """Update player last login timestamp.

        Args:
            player_id: Player UUID

        Returns:
            IRPlayer: Updated player

        Raises:
            IRPlayerError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise IRPlayerError("player_not_found")

        player.last_login_date = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def set_vote_lockout(self, player_id: str, until: datetime) -> IRPlayer:
        """Set vote lockout for guest player (vote spam prevention).

        Args:
            player_id: Player UUID
            until: Lockout expiration time

        Returns:
            IRPlayer: Updated player

        Raises:
            IRPlayerError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise IRPlayerError("player_not_found")

        player.vote_lockout_until = until
        player.consecutive_incorrect_votes = 0
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def increment_incorrect_votes(self, player_id: str) -> IRPlayer:
        """Increment incorrect vote count for guest player.

        Args:
            player_id: Player UUID

        Returns:
            IRPlayer: Updated player

        Raises:
            IRPlayerError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise IRPlayerError("player_not_found")

        player.consecutive_incorrect_votes += 1
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def clear_incorrect_votes(self, player_id: str) -> IRPlayer:
        """Clear incorrect vote count for guest player.

        Args:
            player_id: Player UUID

        Returns:
            IRPlayer: Updated player

        Raises:
            IRPlayerError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise IRPlayerError("player_not_found")

        player.consecutive_incorrect_votes = 0
        await self.db.commit()
        await self.db.refresh(player)
        return player
