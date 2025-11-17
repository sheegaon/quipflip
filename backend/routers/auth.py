"""Authentication endpoints."""
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.dependencies import get_current_player
from backend.schemas.auth import (
    AuthTokenResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SuggestUsernameResponse,
    UsernameLoginRequest,
)
from backend.services import AuthService, AuthError
from backend.utils.cookies import (
    clear_auth_cookies,
    clear_refresh_cookie,
    set_access_token_cookie,
    set_refresh_cookie,
)

from backend.models.player_base import PlayerBase

router = APIRouter()
settings = get_settings()


async def _complete_login(
    player: PlayerBase,
    response: Response,
    db: AsyncSession,
) -> AuthTokenResponse:
    """Handle post-authentication logic: update last login, issue tokens, set cookies.

    This helper function encapsulates the common login success flow shared by
    email-based and username-based login endpoints.
    """
    # Update last_login_date for tracking purposes
    player.last_login_date = datetime.now(UTC)
    await db.commit()

    auth_service = AuthService(db)
    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        player_id=player.player_id,
        username=player.username,
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Authenticate a player via email/password and issue JWT tokens."""

    auth_service = AuthService(db)
    try:
        player = await auth_service.authenticate_player(request.email, request.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return await _complete_login(player, response, db)


@router.post("/login/username", response_model=AuthTokenResponse)
async def login_with_username(
    request: UsernameLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Authenticate a player via username/password and issue JWT tokens."""

    auth_service = AuthService(db)
    try:
        player = await auth_service.authenticate_player_by_username(request.username, request.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return await _complete_login(player, response, db)


@router.get("/suggest-username", response_model=SuggestUsernameResponse)
async def suggest_username(
    db: AsyncSession = Depends(get_db),
) -> SuggestUsernameResponse:
    """Generate a suggested username for registration."""
    from backend.services import UsernameService

    username_service = UsernameService(db)
    display_name, _ = await username_service.generate_unique_username()

    return SuggestUsernameResponse(suggested_username=display_name)


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_tokens(
    request: RefreshRequest,
    response: Response,
    refresh_cookie: str | None = Cookie(
        default=None, alias=settings.refresh_token_cookie_name
    ),
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Exchange a refresh token for new JWT credentials."""

    token = request.refresh_token or refresh_cookie
    if not token:
        raise HTTPException(status_code=401, detail="missing_refresh_token")

    auth_service = AuthService(db)
    try:
        player, access_token, new_refresh_token, expires_in = await auth_service.exchange_refresh_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, new_refresh_token, expires_days=settings.refresh_token_exp_days)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        player_id=player.player_id,
        username=player.username,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: LogoutRequest,
    response: Response,
    refresh_cookie: str | None = Cookie(
        default=None, alias=settings.refresh_token_cookie_name
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Invalidate the provided refresh token and clear cookies."""

    token = request.refresh_token or refresh_cookie
    if token:
        auth_service = AuthService(db)
        await auth_service.revoke_refresh_token(token)

    clear_auth_cookies(response)
    clear_refresh_cookie(response)
    response.status_code = 204
    return None


@router.get("/ws-token")
async def get_websocket_token(
    player: PlayerBase = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a short-lived token for WebSocket authentication.

    This endpoint is called via REST API (through Vercel proxy) using HttpOnly cookies.
    Returns a short-lived token (60 seconds) that can be used for WebSocket connections
    to the Heroku backend, which cannot be proxied through Vercel.

    Token exchange pattern:
    1. Frontend calls this endpoint with HttpOnly cookie (via Vercel /api proxy)
    2. Backend validates cookie and returns short-lived token
    3. Frontend uses token for direct WebSocket connection to Heroku
    4. Short lifetime limits security risk if token is exposed
    """
    auth_service = AuthService(db)

    # Generate a short-lived access token (60 seconds) for WebSocket auth
    ws_token, expires_in = auth_service.create_short_lived_token(
        player=player,
        expires_seconds=60  # Short-lived: 60 seconds
    )

    return {
        "token": ws_token,
        "expires_in": expires_in,
        "token_type": "bearer"
    }
