"""Authentication endpoints."""
from datetime import UTC, datetime

import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.dependencies import get_current_player
from backend.schemas.auth import (
    AuthSessionResponse,
    AuthTokenResponse,
    MagicLinkConsumeRequest,
    MagicLinkRequest,
    MagicLinkRequestResponse,
    MagicLinkResolveRequest,
    MagicLinkStatusResponse,
    GamePlayerSnapshot,
    GlobalPlayerInfo,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SuggestUsernameResponse,
    UsernameLoginRequest,
)
from backend.services import AuthError, UsernameService
from backend.services.account_service import AccountService, MagicLinkError
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
logger = logging.getLogger(__name__)


def _resolve_host_game_type(request: Request, game_type: GameType | None) -> GameType | None:
    """Prefer the validated host scope over any caller-supplied game hint."""

    host_scope = getattr(request.state, "host_scope", None)
    host_game_type = getattr(host_scope, "game", None)

    if host_game_type is not None:
        if game_type is not None and game_type != host_game_type:
            raise HTTPException(status_code=404, detail="host_game_mismatch")
        return host_game_type

    return game_type


def _build_global_player_info(player: PlayerBase) -> GlobalPlayerInfo:
    return GlobalPlayerInfo(
        player_id=player.player_id,
        username=player.username,
        account_id=getattr(player, "account_id", None),
        email=player.email,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
        created_at=player.created_at,
        last_login_date=player.last_login_date,
    )


async def _complete_login(
    player: PlayerBase,
    response: Response,
    db: AsyncSession,
    game_type: GameType | None,
) -> AuthTokenResponse:
    """Handle post-authentication logic: update last login, issue tokens, set cookies.

    This helper function encapsulates the common login success flow shared by
    email-based and username-based login endpoints.
    """
    # Update last_login_date for tracking purposes
    player.last_login_date = datetime.now(UTC)
    await db.commit()

    player_service = PlayerService(db)
    auth_service = AuthService(db, game_type=game_type, player_service=player_service)
    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return await _build_auth_response(
        player=player,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        game_type=game_type,
        db=db,
    )


async def _build_auth_response(
    *,
    player: PlayerBase,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    game_type: GameType | None,
    db: AsyncSession,
) -> AuthTokenResponse:
    player_service = PlayerService(db)
    game_snapshot = await player_service.snapshot_player_data(player, game_type)
    snapshot_model = GamePlayerSnapshot(**game_snapshot) if game_snapshot else None

    legacy_wallet = (
        snapshot_model.wallet
        if snapshot_model and settings.auth_emit_legacy_fields
        else None
    )
    legacy_vault = (
        snapshot_model.vault if snapshot_model and settings.auth_emit_legacy_fields else None
    )
    legacy_tutorial_completed = (
        snapshot_model.tutorial_completed
        if snapshot_model and settings.auth_emit_legacy_fields
        else None
    )

    player_payload = _build_global_player_info(player)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        player_id=player.player_id,
        username=player.username,
        player=player_payload,
        game_type=game_type,
        game_data=snapshot_model,
        legacy_wallet=legacy_wallet,
        legacy_vault=legacy_vault,
        legacy_tutorial_completed=legacy_tutorial_completed,
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    request: Request,
    login_request: LoginRequest,
    response: Response,
    game_type: GameType | None = None,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Authenticate a player via email/password and issue JWT tokens."""

    game_type = _resolve_host_game_type(request, game_type)
    auth_service = AuthService(db, game_type=game_type)
    try:
        player = await auth_service.authenticate_player(login_request.email, login_request.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return await _complete_login(player, response, db, game_type)


@router.get("/session", response_model=AuthSessionResponse)
async def get_session(
    request: Request,
    game_type: GameType | None = None,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    """Return global session information using cookies or Authorization header."""

    game_type = _resolve_host_game_type(request, game_type)
    player = await get_current_player(request, game_type, authorization, db)
    player_service = PlayerService(db)
    game_snapshot = await player_service.snapshot_player_data(player, game_type)
    snapshot_model = GamePlayerSnapshot(**game_snapshot) if game_snapshot else None

    legacy_wallet = (
        snapshot_model.wallet if snapshot_model and settings.auth_emit_legacy_fields else None
    )
    legacy_vault = (
        snapshot_model.vault if snapshot_model and settings.auth_emit_legacy_fields else None
    )
    legacy_tutorial_completed = (
        snapshot_model.tutorial_completed
        if snapshot_model and settings.auth_emit_legacy_fields
        else None
    )

    player_payload = _build_global_player_info(player)

    return AuthSessionResponse(
        player_id=player.player_id,
        username=player.username,
        player=player_payload,
        game_type=game_type,
        game_data=snapshot_model,
        legacy_wallet=legacy_wallet,
        legacy_vault=legacy_vault,
        legacy_tutorial_completed=legacy_tutorial_completed,
    )


@router.post("/login/username", response_model=AuthTokenResponse)
async def login_with_username(
    request: Request,
    login_request: UsernameLoginRequest,
    response: Response,
    game_type: GameType | None = None,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Authenticate a player via username/password and issue JWT tokens."""

    game_type = _resolve_host_game_type(request, game_type)
    auth_service = AuthService(db, game_type=game_type)
    try:
        player = await auth_service.authenticate_player_by_username(login_request.username, login_request.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return await _complete_login(player, response, db, game_type)


@router.get("/suggest-username", response_model=SuggestUsernameResponse)
async def suggest_username(
    request: Request,
    game_type: GameType | None = None,
    db: AsyncSession = Depends(get_db),
) -> SuggestUsernameResponse:
    """Generate a suggested username for registration."""
    from backend.services import UsernameService

    game_type = _resolve_host_game_type(request, game_type)
    username_service = UsernameService(db, game_type=game_type)
    display_name, _ = await username_service.generate_unique_username()

    return SuggestUsernameResponse(suggested_username=display_name)


@router.post("/magic-links", response_model=MagicLinkRequestResponse, status_code=202)
async def request_magic_link(
    request: Request,
    magic_link_request: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> MagicLinkRequestResponse:
    """Request a single-use magic link for saving or restoring an account."""

    account_service = AccountService(db)
    frontend_origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    try:
        result = await account_service.request_magic_link(
            email=magic_link_request.email,
            guest_player_id=magic_link_request.guest_player_id,
            redirect_path=magic_link_request.redirect_path,
            frontend_origin=frontend_origin,
        )
    except MagicLinkError as exc:
        message = str(exc)
        if message in {"invalid_email", "invalid_redirect_path"}:
            raise HTTPException(status_code=400, detail=message) from exc
        if message == "guest_player_not_found":
            raise HTTPException(status_code=404, detail=message) from exc
        if message == "invalid_frontend_origin":
            raise HTTPException(status_code=400, detail=message) from exc
        if message == "magic_link_email_failed":
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(status_code=500, detail=message) from exc

    return MagicLinkRequestResponse(
        email=result.email,
        expires_at=result.expires_at,
        message="Check your email for a sign-in link.",
    )


@router.post("/magic-links/consume", response_model=MagicLinkStatusResponse)
async def consume_magic_link(
    consume_request: MagicLinkConsumeRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MagicLinkStatusResponse:
    """Verify a magic link token and either authenticate or request merge confirmation."""

    account_service = AccountService(db)
    try:
        result = await account_service.consume_magic_link(consume_request.token)
    except MagicLinkError as exc:
        message = str(exc)
        if message in {"magic_link_invalid_or_expired", "magic_link_already_used"}:
            raise HTTPException(status_code=401, detail=message) from exc
        if message in {"magic_link_not_found", "account_not_found"}:
            raise HTTPException(status_code=404, detail=message) from exc
        if message == "magic_link_not_ready":
            raise HTTPException(status_code=400, detail=message) from exc
        raise HTTPException(status_code=500, detail=message) from exc

    if result.status == "merge_required":
        if not result.guest_player or not result.saved_player:
            raise HTTPException(status_code=500, detail="magic_link_merge_incomplete")
        return MagicLinkStatusResponse(
            status="merge_required",
            message="This email already has an account. Choose whether to add this device's history to it.",
            guest_player=_build_global_player_info(result.guest_player),
            saved_player=_build_global_player_info(result.saved_player),
        )

    if not result.player or not result.access_token or not result.refresh_token or result.expires_in is None:
        raise HTTPException(status_code=500, detail="magic_link_auth_incomplete")

    set_access_token_cookie(response, result.access_token)
    set_refresh_cookie(response, result.refresh_token, expires_days=settings.refresh_token_exp_days)

    auth_response = await _build_auth_response(
        player=result.player,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        game_type=None,
        db=db,
    )

    return MagicLinkStatusResponse(
        status="authenticated",
        message="Account saved.",
        auth=auth_response,
    )


@router.post("/magic-links/resolve", response_model=MagicLinkStatusResponse)
async def resolve_magic_link(
    resolve_request: MagicLinkResolveRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MagicLinkStatusResponse:
    """Finalize a verified magic link after the user picks merge or sign-in only."""

    account_service = AccountService(db)
    try:
        result = await account_service.resolve_magic_link(
            resolve_request.token,
            merge_guest=resolve_request.merge_guest,
        )
    except MagicLinkError as exc:
        message = str(exc)
        if message in {"magic_link_invalid_or_expired", "magic_link_already_used"}:
            raise HTTPException(status_code=401, detail=message) from exc
        if message in {"magic_link_not_found", "account_not_found"}:
            raise HTTPException(status_code=404, detail=message) from exc
        if message == "magic_link_not_ready":
            raise HTTPException(status_code=400, detail=message) from exc
        raise HTTPException(status_code=500, detail=message) from exc

    if not result.player or not result.access_token or not result.refresh_token or result.expires_in is None:
        raise HTTPException(status_code=500, detail="magic_link_auth_incomplete")

    set_access_token_cookie(response, result.access_token)
    set_refresh_cookie(response, result.refresh_token, expires_days=settings.refresh_token_exp_days)

    auth_response = await _build_auth_response(
        player=result.player,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        game_type=None,
        db=db,
    )

    return MagicLinkStatusResponse(
        status="authenticated",
        message="Account saved.",
        auth=auth_response,
    )


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_tokens(
    request: Request,
    refresh_request: RefreshRequest,
    response: Response,
    refresh_cookie: str | None = Cookie(default=None, alias=settings.refresh_token_cookie_name),
    game_type: GameType | None = None,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Exchange a refresh token for new JWT credentials."""

    game_type = _resolve_host_game_type(request, game_type)
    token = refresh_request.refresh_token or refresh_cookie
    if not token:
        raise HTTPException(status_code=401, detail="missing_refresh_token")

    auth_service = AuthService(db, game_type=game_type)
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
        game_type=game_type,
        db=db,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    logout_request: LogoutRequest,
    response: Response,
    refresh_cookie: str | None = Cookie(
        default=None, alias=settings.refresh_token_cookie_name
    ),
    game_type: GameType | None = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Invalidate the provided refresh token and clear auth cookies."""

    game_type = _resolve_host_game_type(request, game_type)
    token = logout_request.refresh_token or refresh_cookie
    auth_service = AuthService(db, game_type=game_type)

    if token:
        if game_type == GameType.QF:
            try:
                player = await auth_service.get_player_from_refresh_token(token)
                if player is not None:
                    from backend.services.qf import PartySessionService

                    party_service = PartySessionService(db)
                    await party_service.remove_player_from_all_sessions(player.player_id)
            except Exception as exc:  # pragma: no cover - logout should continue
                logger.warning("Failed to update QF party presence on logout: %s", exc)

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

    This endpoint uses HttpOnly cookies and returns a short-lived token
    (60 seconds) that can be used for WebSocket authentication on the
    same-origin backend.

    Token exchange pattern:
    1. Frontend calls this endpoint with an HttpOnly cookie
    2. Backend validates cookie and returns short-lived token
    3. Frontend uses token for the WebSocket connection
    4. Short lifetime limits security risk if token is exposed
    """
    logger.info(
        "[ws-token] incoming request | path=%s | auth_header=%s",
        request.url.path,
        bool(authorization),
    )

    try:
        detected_player = await get_current_player(
            request=request,
            game_type=None,
            authorization=authorization,
            db=db,
        )
        logger.info(
            "[ws-token] authenticated player | id=%s | username=%s",
            detected_player.player_id,
            detected_player.username,
        )
    except HTTPException as exc:
        logger.warning(
            "[ws-token] unauthorized request | path=%s | detail=%s",
            request.url.path,
            exc.detail,
        )
        raise HTTPException(status_code=401, detail="invalid_token") from exc

    auth_service = AuthService(db)

    # Generate a short-lived access token (60 seconds) for WebSocket auth
    ws_token, expires_in = auth_service.create_short_lived_token(
        player=detected_player,
        expires_seconds=60  # Short-lived: 60 seconds
    )

    logger.info(
        "[ws-token] issued token | player_id=%s | expires_in=%s",
        detected_player.player_id,
        expires_in,
    )

    return {"token": ws_token, "expires_in": expires_in, "token_type": "bearer"}
