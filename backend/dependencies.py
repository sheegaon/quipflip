"""FastAPI dependencies."""
import logging

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from backend.config import get_settings
from backend.database import get_db
from backend.utils.rate_limiter import RateLimiter
from backend.services.auth_service import AuthService, AuthError, GameType
from backend.models.player_base import PlayerBase

logger = logging.getLogger(__name__)


settings = get_settings()
rate_limiter = RateLimiter(settings.redis_url or None)

GENERAL_RATE_LIMIT = 100
VOTE_RATE_LIMIT = 20
GUEST_GENERAL_RATE_LIMIT = 50  # Stricter limit for guests
GUEST_VOTE_RATE_LIMIT = 10  # Stricter limit for guest votes
GUEST_CREATION_RATE_LIMIT = 5  # Per IP limit for creating guest accounts
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

    if settings.environment != "production":
        return

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
        request: Request,
        game_type: GameType,
        authorization: str | None = Header(default=None, alias="Authorization"),
        db: AsyncSession = Depends(get_db),
) -> PlayerBase:
    """Resolve the current authenticated player via JWT access token.

    Checks for access token in the following order:
    1. HTTP-only cookie (preferred, secure)
    2. Authorization header (backward compatibility, API clients)
    """

    # Try to get token from cookie first (preferred method)
    token = request.cookies.get(settings.access_token_cookie_name)
    token_source = "cookie"

    # Fall back to Authorization header if no cookie
    if not token and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="invalid_authorization_header")
        token_source = "header"

    # If still no token found
    if not token:
        raise HTTPException(status_code=401, detail="missing_credentials")

    auth_service = AuthService(db, game_type=game_type)
    try:
        payload = auth_service.decode_access_token(token)
        player_id_str = payload.get("sub")
        if not player_id_str:
            raise AuthError("Invalid token")
        player_id = UUID(str(player_id_str))
    except (ValueError, AuthError) as exc:
        detail = "token_expired" if isinstance(exc, AuthError) and str(exc) == "token_expired" else "invalid_token"
        raise HTTPException(status_code=401, detail=detail) from exc

    # Instantiate the correct player service based on game type
    if game_type == GameType.QF:
        from backend.services.qf.player_service import QFPlayerService as PlayerService
    elif game_type == GameType.IR:
        from backend.services.ir.player_service import IRPlayerService as PlayerService
    elif game_type == GameType.MM:
        from backend.services.mm.player_service import MMPlayerService as PlayerService
    else:
        raise ValueError(f"Unsupported game type: {game_type}")
    player_service = PlayerService(db)

    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=401, detail="invalid_token")

    # Apply stricter rate limits for guest accounts
    limit = GUEST_GENERAL_RATE_LIMIT if player.is_guest else GENERAL_RATE_LIMIT
    await _enforce_rate_limit("general", str(player.player_id), limit)
    logger.debug(
        f"Authenticated player via JWT {token_source}: {player.player_id} (guest={player.is_guest})"
    )
    return player


async def get_optional_player(
        request: Request,
        game_type: GameType,
        authorization: str | None = Header(default=None, alias="Authorization"),
        db: AsyncSession = Depends(get_db),
) -> PlayerBase | None:
    """Return the current player if available, otherwise None for auth failures."""
    try:
        return await get_current_player(request, game_type, authorization, db)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise


async def enforce_vote_rate_limit(
    request: Request,
    game_type: GameType,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> PlayerBase:
    """Enforce tighter limits on vote submissions and return the authenticated player.

    This dependency authenticates the user and applies a stricter rate limit
    based on the player's ID. This approach:
    - Ensures consistent behavior with get_current_player
    - Uses player_id for rate limiting (stable across sessions)
    - Automatically handles authentication errors via get_current_player
    - Returns the player to avoid redundant get_current_player calls in endpoints
    """
    # Get authenticated player
    player = await get_current_player(request, game_type, authorization, db)

    # Apply stricter vote rate limits for guest accounts
    limit = GUEST_VOTE_RATE_LIMIT if player.is_guest else VOTE_RATE_LIMIT
    await _enforce_rate_limit("vote_submit", str(player.player_id), limit)
    return player


async def enforce_guest_creation_rate_limit(
    x_forwarded_for: str | None = Header(default=None, alias="X-Forwarded-For"),
    x_real_ip: str | None = Header(default=None, alias="X-Real-IP"),
) -> None:
    """Enforce rate limits on guest account creation per IP address.

    Uses X-Forwarded-For or X-Real-IP headers to identify the client IP.
    This prevents abuse by limiting how many guest accounts can be created
    from a single IP address.
    """
    # Extract client IP from headers (proxy-aware)
    client_ip = None
    if x_forwarded_for:
        # X-Forwarded-For can be a comma-separated list, take the first (client) IP
        client_ip = x_forwarded_for.split(",")[0].strip()
    elif x_real_ip:
        client_ip = x_real_ip.strip()

    if not client_ip:
        if settings.environment == "production":
            logger.error("Could not determine client IP for guest creation rate limit. Check proxy headers.")
            raise HTTPException(status_code=500, detail="Server configuration error.")
        # Allow for local development if no IP headers are present.
        return

    await _enforce_rate_limit("guest_creation", client_ip, GUEST_CREATION_RATE_LIMIT)


async def get_admin_player(
    player: PlayerBase = Depends(get_current_player),
) -> PlayerBase:
    """Verify that the current authenticated player is an admin.

    This dependency checks if the player's email is in the admin_emails
    configuration. Only users with admin emails can access admin endpoints.

    Args:
        player: Current authenticated player from get_current_player

    Returns:
        Player object if the user is an admin

    Raises:
        HTTPException: 403 if the user is not an admin
    """
    if not settings.is_admin_email(player.email):
        logger.warning(
            f"Access denied to admin endpoint for non-admin user: {player.username} ({player.email})"
        )
        raise HTTPException(
            status_code=403,
            detail="admin_access_required"
        )

    logger.debug(f"Admin access granted to: {player.username} ({player.email})")
    return player
