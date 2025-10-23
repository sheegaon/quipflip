"""Authentication endpoints."""
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.schemas.auth import AuthTokenResponse, LoginRequest, LogoutRequest, RefreshRequest, SuggestUsernameResponse
from backend.services.auth_service import AuthService, AuthError
from backend.utils.cookies import clear_refresh_cookie, set_refresh_cookie

router = APIRouter()
settings = get_settings()


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

    # Update last_login_date for tracking purposes
    player.last_login_date = datetime.now(UTC).date()
    await db.commit()

    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        player_id=player.player_id,
        username=player.username,
    )


@router.get("/suggest-username", response_model=SuggestUsernameResponse)
async def suggest_username(
    db: AsyncSession = Depends(get_db),
) -> SuggestUsernameResponse:
    """Generate a suggested username for registration."""
    from backend.services.username_service import UsernameService

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

    clear_refresh_cookie(response)
    response.status_code = 204
    return None
