"""Meme Mint authentication endpoints."""
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.dependencies import get_current_player, get_optional_player
from backend.schemas.auth import (
    AuthTokenResponse,
    GamePlayerSnapshot,
    GlobalPlayerInfo,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SuggestUsernameResponse,
    UsernameLoginRequest,
)
from backend.services import AuthError
from backend.services.auth_service import AuthService, GameType
from backend.services.player_service import PlayerService
from backend.utils.cookies import (
    clear_auth_cookies,
    clear_refresh_cookie,
    set_access_token_cookie,
    set_refresh_cookie,
)

from backend.models.player_base import PlayerBase

router = APIRouter()
settings = get_settings()


async def _build_auth_response(
    *,
    player: PlayerBase,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    db: AsyncSession,
) -> AuthTokenResponse:
    player_service = PlayerService(db)
    game_snapshot = await player_service.snapshot_player_data(player, GameType.MM)
    snapshot_model = GamePlayerSnapshot(**game_snapshot) if game_snapshot else None

    legacy_wallet = (
        snapshot_model.wallet if snapshot_model and settings.auth_emit_legacy_fields else None
    )
    legacy_vault = snapshot_model.vault if snapshot_model and settings.auth_emit_legacy_fields else None
    legacy_tutorial_completed = (
        snapshot_model.tutorial_completed
        if snapshot_model and settings.auth_emit_legacy_fields
        else None
    )

    player_payload = GlobalPlayerInfo(
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
        created_at=player.created_at,
        last_login_date=player.last_login_date,
    )

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        player_id=player.player_id,
        username=player.username,
        player=player_payload,
        game_type=GameType.MM,
        game_data=snapshot_model,
        legacy_wallet=legacy_wallet,
        legacy_vault=legacy_vault,
        legacy_tutorial_completed=legacy_tutorial_completed,
    )


async def _complete_login(player: PlayerBase, response: Response, db: AsyncSession,) -> AuthTokenResponse:
    """Handle post-authentication logic: update last login, issue tokens, set cookies.

    This helper function encapsulates the common login success flow shared by
    email-based and username-based login endpoints.
    """
    # Update last_login_date for tracking purposes
    player.last_login_date = datetime.now(UTC)
    await db.commit()

    auth_service = AuthService(db, game_type=GameType.MM)
    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return await _build_auth_response(
        player=player,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        db=db,
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(request: LoginRequest, response: Response, db: AsyncSession = Depends(get_db),) -> AuthTokenResponse:
    """Authenticate a player via email/password and issue JWT tokens."""

    auth_service = AuthService(db, game_type=GameType.MM)
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

    auth_service = AuthService(db, game_type=GameType.MM)
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

    username_service = UsernameService(db, game_type=GameType.MM)
    display_name, _ = await username_service.generate_unique_username()

    return SuggestUsernameResponse(suggested_username=display_name)


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_tokens(request: RefreshRequest, response: Response,
                        refresh_cookie: str | None = Cookie(default=None, alias=settings.refresh_token_cookie_name),
                        db: AsyncSession = Depends(get_db)) -> AuthTokenResponse:
    """Exchange a refresh token for new JWT credentials."""

    token = request.refresh_token or refresh_cookie
    if not token:
        raise HTTPException(status_code=401, detail="missing_refresh_token")

    auth_service = AuthService(db, game_type=GameType.MM)
    try:
        player, access_token, new_refresh_token, expires_in = await auth_service.exchange_refresh_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, new_refresh_token, expires_days=settings.refresh_token_exp_days)

    return await _build_auth_response(
        player=player,
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=expires_in,
        db=db,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: LogoutRequest,
    response: Response,
    player: PlayerBase | None = Depends(get_optional_player),
    refresh_cookie: str | None = Cookie(
        default=None, alias=settings.refresh_token_cookie_name
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Invalidate the provided refresh token and clear cookies."""

    token = request.refresh_token or refresh_cookie
    auth_service = AuthService(db, game_type=GameType.MM)

    player_id = player.player_id if player else None
    if not player_id and token:
        linked_player = await auth_service.get_player_from_refresh_token(token)
        if linked_player:
            player_id = linked_player.player_id

    if token:
        await auth_service.revoke_refresh_token(token)

    clear_auth_cookies(response)
    clear_refresh_cookie(response)
    response.status_code = 204
    return None


@router.get("/ws-token")
async def get_websocket_token(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
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
    # Detect the authenticated player across all supported games
    detected_player: PlayerBase | None = None
    detected_game: GameType | None = None

    for game_type in (GameType.MM, GameType.QF, GameType.IR):
        try:
            detected_player = await get_current_player(
                request=request,
                game_type=game_type,
                authorization=authorization,
                db=db,
            )
            detected_game = game_type
            break
        except HTTPException:
            continue

    if not detected_player or not detected_game:
        raise HTTPException(status_code=401, detail="invalid_token")

    auth_service = AuthService(db, game_type=detected_game)

    # Generate a short-lived access token (60 seconds) for WebSocket auth
    ws_token, expires_in = auth_service.create_short_lived_token(
        player=detected_player,
        expires_seconds=60  # Short-lived: 60 seconds
    )

    return {"token": ws_token, "expires_in": expires_in, "token_type": "bearer"}
