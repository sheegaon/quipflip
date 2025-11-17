"""Authentication endpoints for Initial Reaction (IR)."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.models.ir.ir_player import IRPlayer
from backend.routers.ir.dependencies import get_ir_current_player
from backend.routers.ir.schemas import (
    IRAuthResponse,
    IRLoginRequest,
    IRPlayerInfo,
    IRRefreshRequest,
    IRRegisterRequest,
    IRUpgradeGuestRequest,
)
from backend.services.ir.auth_service import IRAuthService, IRAuthError
from backend.services.ir.player_service import IRPlayerService
from backend.utils.cookies import set_access_token_cookie, set_refresh_cookie, clear_auth_cookies

router = APIRouter()
settings = get_settings()


@router.post("/auth/register", response_model=IRAuthResponse)
async def register(
    request: IRRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Register a new IR player account."""
    auth_service = IRAuthService(db)
    try:
        player, access_token = await auth_service.register(
            username=request.username,
            email=request.email,
            password=request.password,
        )
    except IRAuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    refresh_token = await auth_service.create_refresh_token(player.player_id)

    set_access_token_cookie(
        response,
        access_token,
        cookie_name=settings.ir_access_token_cookie_name,
    )
    set_refresh_cookie(
        response,
        refresh_token,
        expires_days=settings.ir_refresh_token_expire_days,
        cookie_name=settings.ir_refresh_token_cookie_name,
    )

    return IRAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        player=IRPlayerInfo(
            player_id=str(player.player_id),
            username=player.username,
            email=player.email,
            wallet=player.wallet,
            vault=player.vault,
            is_guest=player.is_guest,
            created_at=player.created_at,
            daily_bonus_available=True,  # TODO: fetch from service
            last_login_date=None,
        ),
    )


@router.post("/auth/login", response_model=IRAuthResponse)
async def login(
    request: IRLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Authenticate an IR player with username and password."""
    auth_service = IRAuthService(db)
    try:
        player, access_token = await auth_service.login(
            username=request.username,
            password=request.password,
        )
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    refresh_token = await auth_service.create_refresh_token(player.player_id)

    set_access_token_cookie(
        response,
        access_token,
        cookie_name=settings.ir_access_token_cookie_name,
    )
    set_refresh_cookie(
        response,
        refresh_token,
        expires_days=settings.ir_refresh_token_expire_days,
        cookie_name=settings.ir_refresh_token_cookie_name,
    )

    return IRAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        player=IRPlayerInfo(
            player_id=str(player.player_id),
            username=player.username,
            email=player.email,
            wallet=player.wallet,
            vault=player.vault,
            is_guest=player.is_guest,
            created_at=player.created_at,
            daily_bonus_available=True,  # TODO: fetch from service
            last_login_date=None,
        ),
    )


@router.post("/auth/guest", response_model=IRAuthResponse)
async def register_guest(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Create a guest account for IR."""
    auth_service = IRAuthService(db)
    try:
        player, access_token = await auth_service.register_guest()
    except IRAuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    refresh_token = await auth_service.create_refresh_token(player.player_id)

    set_access_token_cookie(
        response,
        access_token,
        cookie_name=settings.ir_access_token_cookie_name,
    )
    set_refresh_cookie(
        response,
        refresh_token,
        expires_days=settings.ir_refresh_token_expire_days,
        cookie_name=settings.ir_refresh_token_cookie_name,
    )

    return IRAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        player=IRPlayerInfo(
            player_id=str(player.player_id),
            username=player.username,
            email=player.email,
            wallet=player.wallet,
            vault=player.vault,
            is_guest=player.is_guest,
            created_at=player.created_at,
            daily_bonus_available=True,  # TODO: fetch from service
            last_login_date=None,
        ),
    )


@router.post("/auth/upgrade", response_model=IRAuthResponse)
async def upgrade_guest_account(
    request: IRUpgradeGuestRequest,
    response: Response,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Upgrade a guest account to a full account."""
    auth_service = IRAuthService(db)
    try:
        upgraded_player, access_token = await auth_service.upgrade_guest(
            player,
            request.email,
            request.password,
        )
    except IRAuthError as exc:
        message = str(exc)
        status = 400
        if message == "email_taken":
            status = 409
        elif message == "not_a_guest":
            status = 400
        elif message.startswith("weak_password"):
            status = 422
        raise HTTPException(status_code=status, detail=message) from exc

    refresh_token = await auth_service.create_refresh_token(upgraded_player.player_id)
    set_access_token_cookie(
        response,
        access_token,
        cookie_name=settings.ir_access_token_cookie_name,
    )
    set_refresh_cookie(
        response,
        refresh_token,
        expires_days=settings.ir_refresh_token_expire_days,
        cookie_name=settings.ir_refresh_token_cookie_name,
    )

    return IRAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        player=IRPlayerInfo(
            player_id=str(upgraded_player.player_id),
            username=upgraded_player.username,
            email=upgraded_player.email,
            wallet=upgraded_player.wallet,
            vault=upgraded_player.vault,
            is_guest=upgraded_player.is_guest,
            created_at=upgraded_player.created_at,
            daily_bonus_available=True,  # TODO: fetch from service
            last_login_date=None,
        ),
    )


@router.post("/auth/refresh", response_model=IRAuthResponse)
async def refresh_access_token(
    request: IRRefreshRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Refresh access token using refresh token."""
    auth_service = IRAuthService(db)
    try:
        access_token = await auth_service.refresh_access_token(request.refresh_token)
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    try:
        player_id = await auth_service.verify_access_token(access_token)
        player_service = IRPlayerService(db)
        player = await player_service.get_player_by_id(player_id)
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    refresh_token = await auth_service.create_refresh_token(player.player_id)

    set_access_token_cookie(
        response,
        access_token,
        cookie_name=settings.ir_access_token_cookie_name,
    )
    set_refresh_cookie(
        response,
        refresh_token,
        expires_days=settings.ir_refresh_token_expire_days,
        cookie_name=settings.ir_refresh_token_cookie_name,
    )

    return IRAuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        player=IRPlayerInfo(
            player_id=str(player.player_id),
            username=player.username,
            email=player.email,
            wallet=player.wallet,
            vault=player.vault,
            is_guest=player.is_guest,
            created_at=player.created_at,
            daily_bonus_available=True,  # TODO: fetch from service
            last_login_date=None,
        ),
    )


@router.post("/auth/logout")
async def logout(
    response: Response,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Logout current IR player."""
    auth_service = IRAuthService(db)
    await auth_service.revoke_tokens(str(player.player_id))

    clear_auth_cookies(response)

    return {"message": "logout_success", "player_id": str(player.player_id)}
