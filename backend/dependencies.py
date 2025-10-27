"""FastAPI dependencies."""
import logging

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from backend.config import get_settings
from backend.database import get_db
from backend.models.player import Player
from backend.services.player_service import PlayerService
from backend.utils.rate_limiter import RateLimiter
from backend.services.auth_service import AuthService, AuthError

logger = logging.getLogger(__name__)


settings = get_settings()
rate_limiter = RateLimiter(settings.redis_url or None)

GENERAL_RATE_LIMIT = 100
VOTE_RATE_LIMIT = 20
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_ERROR_MESSAGE = "Rate limit exceeded. Try again later."


def _mask_identifier(identifier: str) -> str:
    """Mask a sensitive identifier for logging (e.g., player_id, token)."""
    if not identifier:
        return "<missing>"
    if len(identifier) <= 8:
        return f"{identifier[:2]}...{identifier[-2:]}"
    return f"{identifier[:4]}...{identifier[-4:]}"


async def _enforce_rate_limit(scope: str, identifier: str | None, limit: int) -> None:
    """Apply a rate limit for the provided scope and identifier."""

    if not identifier:
        return

    key = f"{scope}:{identifier}"
    allowed, retry_after = await rate_limiter.check(
        key, limit, RATE_LIMIT_WINDOW_SECONDS
    )

    if allowed:
        return

    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)

    masked_identifier = _mask_identifier(identifier)
    logger.warning(f"Rate limit exceeded for {scope=} {masked_identifier=}")
    raise HTTPException(status_code=429, detail=RATE_LIMIT_ERROR_MESSAGE, headers=headers or None)


async def get_current_player(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> Player:
    """Resolve the current authenticated player via JWT access token."""

    if not authorization:
        raise HTTPException(status_code=401, detail="missing_credentials")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="invalid_authorization_header")

    auth_service = AuthService(db)
    try:
        payload = auth_service.decode_access_token(token)
        player_id_str = payload.get("sub")
        if not player_id_str:
            raise AuthError("Invalid token")
        player_id = UUID(str(player_id_str))
    except (ValueError, AuthError) as exc:
        detail = "token_expired" if isinstance(exc, AuthError) and str(exc) == "token_expired" else "invalid_token"
        raise HTTPException(status_code=401, detail=detail) from exc

    player_service = PlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=401, detail="invalid_token")

    await _enforce_rate_limit("general", str(player.player_id), GENERAL_RATE_LIMIT)
    logger.debug("Authenticated player via JWT: %s", player.player_id)
    return player


async def enforce_vote_rate_limit(
    player: Player = Depends(get_current_player),
) -> Player:
    """Enforce tighter limits on vote submissions and return the authenticated player.

    This dependency leverages get_current_player to authenticate the user and then
    applies a stricter rate limit based on the player's ID. This approach:
    - Eliminates duplication of authentication logic
    - Ensures consistent behavior with get_current_player
    - Uses player_id for rate limiting (stable across sessions)
    - Automatically handles authentication errors via get_current_player
    - Returns the player to avoid redundant get_current_player calls in endpoints
    """
    await _enforce_rate_limit("vote_submit", str(player.player_id), VOTE_RATE_LIMIT)
    return player
