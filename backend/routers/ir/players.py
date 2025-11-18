"""Player-focused endpoints for Initial Reaction (IR)."""
import logging
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.dependencies import get_current_player, enforce_guest_creation_rate_limit
from backend.models.ir.player import IRPlayer
from backend.schemas.auth import RegisterRequest
from backend.schemas.player import (
    PlayerBalance,
    ClaimDailyBonusResponse,
    CreatePlayerResponse,
    CreateGuestResponse,
    UpgradeGuestRequest,
    UpgradeGuestResponse,
)
from backend.services import AuthService, AuthError
from backend.utils.model_registry import GameType
from backend.services.ir import PlayerService
from backend.utils.cookies import (
    clear_auth_cookies,
    set_access_token_cookie,
    set_refresh_cookie,
)
from backend.utils.passwords import (
    validate_password_strength,
    PasswordValidationError,
)

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime has UTC timezone for proper JSON serialization."""
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@router.post("", response_model=CreatePlayerResponse, status_code=201)
async def create_player(
    request: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create a new IR player account and return credentials."""

    auth_service = AuthService(db, GameType.IR)
    try:
        player = await auth_service.register_player(
            email=request.email,
            password=request.password,
        )
    except AuthError as exc:
        message = str(exc)
        # Check if this is a password validation error
        if any(keyword in message for keyword in [
            "Password must be at least",
            "Password must include both uppercase and lowercase",
            "Password must include at least one number"
        ]):
            raise HTTPException(status_code=422, detail=message) from exc
        if message == "username_generation_failed":
            raise HTTPException(status_code=500, detail="username_generation_failed") from exc
        if message == "email_taken":
            raise HTTPException(status_code=409, detail="email_taken") from exc
        if message == "invalid_username":
            raise HTTPException(status_code=422, detail="invalid_username") from exc
        raise

    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return CreatePlayerResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type="bearer",
        player_id=player.player_id,
        username=player.username,
        wallet=player.wallet,
        vault=player.vault,
        message=(
            "IR Player created! Your account is ready to play Initial Reaction. "
            "An access token and refresh token have been issued for authentication."
        ),
    )


@router.post("/guest", response_model=CreateGuestResponse, status_code=201)
async def create_guest_player(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(enforce_guest_creation_rate_limit),
):
    """Create an IR guest account with auto-generated credentials."""

    auth_service = AuthService(db, GameType.IR)
    try:
        player, guest_password = await auth_service.register_guest()
    except AuthError as exc:
        message = str(exc)
        if message == "username_generation_failed":
            raise HTTPException(status_code=500, detail="username_generation_failed") from exc
        if message == "guest_email_generation_failed":
            raise HTTPException(status_code=500, detail="guest_email_generation_failed") from exc
        raise

    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return CreateGuestResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type="bearer",
        player_id=player.player_id,
        username=player.username,
        wallet=player.wallet,
        vault=player.vault,
        email=player.email,
        password=guest_password,
        message=(
            f"IR Guest account created! Your temporary credentials are:\n"
            f"Email: {player.email}\n"
            f"Password: {guest_password}\n\n"
            f"You can upgrade to a full account anytime to choose your own email and password."
        ),
    )


@router.post("/upgrade", response_model=UpgradeGuestResponse)
async def upgrade_guest_account(
    request: UpgradeGuestRequest,
    response: Response,
    player: IRPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade an IR guest account to a full account."""

    auth_service = AuthService(db, GameType.IR)
    try:
        upgraded_player = await auth_service.upgrade_guest(player, request.email, request.password)
    except AuthError as exc:
        message = str(exc)
        if message == "not_a_guest":
            raise HTTPException(status_code=400, detail="not_a_guest") from exc
        if message == "email_taken":
            raise HTTPException(status_code=409, detail="email_taken") from exc
        # Check if this is a password validation error
        if any(keyword in message for keyword in [
            "Password must be at least",
            "Password must include both uppercase and lowercase",
            "Password must include at least one number"
        ]):
            raise HTTPException(status_code=422, detail=message) from exc
        if message == "upgrade_failed":
            raise HTTPException(status_code=500, detail="upgrade_failed") from exc
        raise

    # Issue fresh tokens after upgrade
    access_token, refresh_token, expires_in = await auth_service.issue_tokens(upgraded_player)
    set_access_token_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return UpgradeGuestResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type="bearer",
        player_id=upgraded_player.player_id,
        username=upgraded_player.username,
        message="IR Account upgraded successfully! You can now log in with your new credentials.",
    )


@router.get("/me", response_model=PlayerBalance)
async def get_current_player_info(
    player: IRPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerBalance:
    """Get current authenticated IR player information using shared schema."""
    player_service = PlayerService(db)
    
    # Check if daily bonus is available (IR may not have this feature, but keeping consistent)
    # For now, we'll assume IR doesn't have daily bonus - services can override this
    bonus_available = False
    try:
        # If IR implements daily bonus checking in the future, it would go here
        pass
    except Exception:
        pass

    return PlayerBalance(
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        starting_balance=settings.ir_initial_balance,
        daily_bonus_available=bonus_available,
        daily_bonus_amount=0,  # IR may not have daily bonus
        last_login_date=ensure_utc(player.last_login_date),
        created_at=player.created_at,
        outstanding_prompts=0,  # IR doesn't have outstanding prompts concept
        is_guest=player.is_guest,
        is_admin=player.is_admin,
        locked_until=ensure_utc(player.locked_until),
        flag_dismissal_streak=0,  # IR doesn't have flag dismissal
    )


@router.get("/balance", response_model=PlayerBalance)
async def get_player_balance(
    player: IRPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerBalance:
    """Return IR player wallet/vault balances using shared schema pattern."""
    # Reuse the same logic as get_current_player_info for consistency
    return await get_current_player_info(player, db)


@router.post("/claim-daily-bonus", response_model=ClaimDailyBonusResponse)
async def claim_daily_bonus(
    player: IRPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Claim the daily InitCoin bonus for IR players."""
    # IR may not have daily bonus system implemented yet
    # For consistency with QF API, we provide the endpoint but return appropriate error
    raise HTTPException(
        status_code=501, 
        detail="Daily bonus feature not implemented for Initial Reaction"
    )


@router.get("/players/{player_id}", response_model=PlayerBalance)
async def get_player(
    player_id: str,
    db: AsyncSession = Depends(get_db),
    _: IRPlayer = Depends(get_current_player),
) -> PlayerBalance:
    """Get IR player information by ID using shared schema."""

    player_service = PlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return PlayerBalance(
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        starting_balance=settings.ir_initial_balance,
        daily_bonus_available=False,
        daily_bonus_amount=0,
        last_login_date=ensure_utc(player.last_login_date),
        created_at=player.created_at,
        outstanding_prompts=0,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
        locked_until=ensure_utc(player.locked_until),
        flag_dismissal_streak=0,
    )
