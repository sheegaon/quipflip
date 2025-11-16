"""IR Authentication Service - JWT and credential management for Initial Reaction."""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.ir.ir_player import IRPlayer
from backend.models.ir.ir_refresh_token import IRRefreshToken
from backend.utils.simple_jwt import encode_jwt, decode_jwt, ExpiredSignatureError, InvalidTokenError
from backend.utils.passwords import hash_password, verify_password, validate_password_strength, PasswordValidationError
from backend.services.ir.player_service import IRPlayerService, IRPlayerError

logger = logging.getLogger(__name__)


class IRAuthError(RuntimeError):
    """Raised when IR authentication fails."""


class IRAuthService:
    """Service for IR credential management and JWT issuance."""

    def __init__(self, db: AsyncSession):
        """Initialize IR auth service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        self.player_service = IRPlayerService(db)

    async def register(
        self,
        username: str,
        email: str,
        password: str,
    ) -> tuple[IRPlayer, str]:
        """Register a new IR player account.

        Args:
            username: Display username
            email: Email address
            password: Plain text password

        Returns:
            tuple[IRPlayer, str]: Created player and access token

        Raises:
            IRAuthError: If registration fails
        """
        try:
            # Validate password strength
            validate_password_strength(password)
        except PasswordValidationError as e:
            raise IRAuthError(f"weak_password: {str(e)}") from e

        password_hash = hash_password(password)

        try:
            player = await self.player_service.create_player(
                username=username,
                email=email,
                password_hash=password_hash,
            )
        except IRPlayerError as e:
            raise IRAuthError(str(e)) from e

        # Generate access token
        access_token = self._generate_access_token(player)

        logger.info(f"IR player {player.player_id} registered successfully")
        return player, access_token

    async def register_guest(self) -> tuple[IRPlayer, str]:
        """Create a guest account with auto-generated credentials.

        Returns:
            tuple[IRPlayer, str]: Created player and access token

        Raises:
            IRAuthError: If guest registration fails
        """
        try:
            player, _ = await self.player_service.register_guest()
        except IRPlayerError as e:
            raise IRAuthError(str(e)) from e

        # Generate access token
        access_token = self._generate_access_token(player)

        logger.info(f"IR guest player {player.player_id} registered successfully")
        return player, access_token

    async def login(self, username: str, password: str) -> tuple[IRPlayer, str]:
        """Authenticate IR player with username and password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            tuple[IRPlayer, str]: Authenticated player and access token

        Raises:
            IRAuthError: If authentication fails
        """
        player = await self.player_service.get_player_by_username(username)
        if not player:
            raise IRAuthError("invalid_credentials")

        if not verify_password(password, player.password_hash):
            raise IRAuthError("invalid_credentials")

        # Check if player is locked
        if player.locked_until and player.locked_until > datetime.now(UTC):
            raise IRAuthError("account_locked")

        # Update last login
        await self.player_service.update_last_login(player.player_id)

        # Generate access token
        access_token = self._generate_access_token(player)

        logger.info(f"IR player {player.player_id} logged in successfully")
        return player, access_token

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token from valid refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            str: New access token

        Raises:
            IRAuthError: If refresh token is invalid
        """
        try:
            payload = decode_jwt(refresh_token, self.settings.ir_secret_key)
        except (ExpiredSignatureError, InvalidTokenError) as e:
            raise IRAuthError("invalid_refresh_token") from e

        player_id = payload.get("sub")
        if not player_id:
            raise IRAuthError("invalid_refresh_token")

        # Verify refresh token exists in database
        stmt = select(IRRefreshToken).where(IRRefreshToken.player_id == player_id)
        result = await self.db.execute(stmt)
        token_record = result.scalars().first()

        if not token_record:
            raise IRAuthError("refresh_token_not_found")

        # Verify token hash matches
        token_hash = self._hash_token(refresh_token)
        if token_record.token_hash != token_hash:
            raise IRAuthError("token_hash_mismatch")

        # Get player
        player = await self.player_service.get_player_by_id(player_id)
        if not player:
            raise IRAuthError("player_not_found")

        # Generate new access token
        access_token = self._generate_access_token(player)

        logger.info(f"IR player {player_id} refreshed access token")
        return access_token

    async def create_refresh_token(self, player_id: str) -> str:
        """Create a new refresh token for player.

        Args:
            player_id: Player UUID

        Returns:
            str: Refresh token

        Raises:
            IRAuthError: If player not found
        """
        player = await self.player_service.get_player_by_id(player_id)
        if not player:
            raise IRAuthError("player_not_found")

        # Generate refresh token
        token_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)

        expires_at = datetime.now(UTC) + timedelta(days=self.settings.ir_refresh_token_expire_days)

        refresh_token_record = IRRefreshToken(
            token_id=token_id,
            player_id=player_id,
            token_hash=token_hash,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        self.db.add(refresh_token_record)
        await self.db.commit()

        logger.debug(f"Created refresh token for IR player {player_id}")

        # Encode as JWT for transport
        payload = {
            "sub": str(player_id),
            "token_id": str(token_id),
            "exp": int(expires_at.timestamp()),
        }
        jwt_token = encode_jwt(payload, self.settings.ir_secret_key)
        return jwt_token

    async def logout(self, player_id: str) -> None:
        """Invalidate all refresh tokens for player (logout).

        Args:
            player_id: Player UUID
        """
        stmt = select(IRRefreshToken).where(IRRefreshToken.player_id == player_id)
        result = await self.db.execute(stmt)
        tokens = result.scalars().all()

        for token in tokens:
            await self.db.delete(token)

        await self.db.commit()
        logger.info(f"IR player {player_id} logged out - refresh tokens invalidated")

    async def verify_access_token(self, token: str) -> str:
        """Verify access token and return player ID.

        Args:
            token: Access token

        Returns:
            str: Player ID

        Raises:
            IRAuthError: If token is invalid
        """
        try:
            payload = decode_jwt(token, self.settings.ir_secret_key)
        except (ExpiredSignatureError, InvalidTokenError) as e:
            raise IRAuthError("invalid_access_token") from e

        player_id = payload.get("sub")
        if not player_id:
            raise IRAuthError("invalid_access_token")

        return player_id

    def _generate_access_token(self, player: IRPlayer) -> str:
        """Generate access token for player.

        Args:
            player: IRPlayer instance

        Returns:
            str: Access token
        """
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.ir_access_token_expire_minutes)
        payload = {
            "sub": str(player.player_id),
            "username": player.username,
            "exp": int(expires_at.timestamp()),
        }
        return encode_jwt(payload, self.settings.ir_secret_key)

    def _hash_token(self, token: str) -> str:
        """Hash token for secure storage.

        Args:
            token: Plain token

        Returns:
            str: Hashed token
        """
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()
