"""Initial Reaction (IR) game API endpoints."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.config import get_settings
from backend.database import get_db
from backend.models.ir.ir_player import IRPlayer
from backend.services.ir.auth_service import IRAuthService, IRAuthError
from backend.services.ir.player_service import IRPlayerService, IRPlayerError
from backend.utils.cookies import set_access_token_cookie, set_refresh_cookie, clear_auth_cookies

router = APIRouter(prefix="/api/ir", tags=["ir"])
settings = get_settings()


# ================================================================
# Request/Response Schemas
# ================================================================

class IRLoginRequest(BaseModel):
    """IR login request."""

    username: str
    password: str


class IRRegisterRequest(BaseModel):
    """IR registration request."""

    username: str
    email: str
    password: str


class IRAuthResponse(BaseModel):
    """IR authentication response."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    player_id: str
    username: str
    wallet: int
    vault: int


class IRPlayerResponse(BaseModel):
    """IR player response."""

    player_id: str
    username: str
    email: str
    wallet: int
    vault: int
    created_at: datetime
    is_guest: bool
    is_admin: bool


class IRRefreshRequest(BaseModel):
    """IR token refresh request."""

    refresh_token: str


class IRLogoutRequest(BaseModel):
    """IR logout request."""

    player_id: str


# ================================================================
# Authentication Dependencies
# ================================================================

async def get_ir_current_player(
    authorization: str | None = None,
    ir_access_token: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> IRPlayer:
    """Get current authenticated IR player from token.

    Supports both Authorization header and cookie.

    Args:
        authorization: Authorization header with Bearer token
        ir_access_token: Access token from cookie
        db: Database session

    Returns:
        IRPlayer: Authenticated player

    Raises:
        HTTPException: If token is invalid or player not found
    """
    token = None

    # Try Authorization header first
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    # Fall back to cookie
    if not token and ir_access_token:
        token = ir_access_token

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    auth_service = IRAuthService(db)
    try:
        player_id = await auth_service.verify_access_token(token)
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    player_service = IRPlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=401, detail="Player not found")

    return player


# ================================================================
# Authentication Endpoints
# ================================================================

@router.post("/auth/register", response_model=IRAuthResponse)
async def register(
    request: IRRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Register a new IR player account.

    Args:
        request: Registration request with username, email, password
        response: Response object for setting cookies
        db: Database session

    Returns:
        IRAuthResponse: Authentication tokens and player info

    Raises:
        HTTPException: If registration fails
    """
    auth_service = IRAuthService(db)
    try:
        player, access_token = await auth_service.register(
            username=request.username,
            email=request.email,
            password=request.password,
        )
    except IRAuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Create refresh token
    refresh_token = await auth_service.create_refresh_token(player.player_id)

    # Set cookies
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
        expires_in=settings.ir_access_token_expire_minutes * 60,
        player_id=player.player_id,
        username=player.username,
        wallet=player.wallet,
        vault=player.vault,
    )


@router.post("/auth/login", response_model=IRAuthResponse)
async def login(
    request: IRLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Authenticate an IR player with username and password.

    Args:
        request: Login request with username and password
        response: Response object for setting cookies
        db: Database session

    Returns:
        IRAuthResponse: Authentication tokens and player info

    Raises:
        HTTPException: If authentication fails
    """
    auth_service = IRAuthService(db)
    try:
        player, access_token = await auth_service.login(
            username=request.username,
            password=request.password,
        )
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    # Create refresh token
    refresh_token = await auth_service.create_refresh_token(player.player_id)

    # Set cookies
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
        expires_in=settings.ir_access_token_expire_minutes * 60,
        player_id=player.player_id,
        username=player.username,
        wallet=player.wallet,
        vault=player.vault,
    )


@router.post("/auth/guest", response_model=IRAuthResponse)
async def register_guest(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Create a guest account for IR.

    Args:
        response: Response object for setting cookies
        db: Database session

    Returns:
        IRAuthResponse: Authentication tokens and player info

    Raises:
        HTTPException: If guest registration fails
    """
    auth_service = IRAuthService(db)
    try:
        player, access_token = await auth_service.register_guest()
    except IRAuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Create refresh token
    refresh_token = await auth_service.create_refresh_token(player.player_id)

    # Set cookies
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
        expires_in=settings.ir_access_token_expire_minutes * 60,
        player_id=player.player_id,
        username=player.username,
        wallet=player.wallet,
        vault=player.vault,
    )


@router.post("/auth/refresh", response_model=IRAuthResponse)
async def refresh_access_token(
    request: IRRefreshRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> IRAuthResponse:
    """Refresh access token using refresh token.

    Args:
        request: Refresh token request
        response: Response object for setting cookies
        db: Database session

    Returns:
        IRAuthResponse: New access token and player info

    Raises:
        HTTPException: If refresh fails
    """
    auth_service = IRAuthService(db)
    try:
        access_token = await auth_service.refresh_access_token(request.refresh_token)
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    # Get player info for response
    try:
        player_id = await auth_service.verify_access_token(access_token)
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    player_service = IRPlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=401, detail="Player not found")

    # Set new access token cookie
    set_access_token_cookie(
        response,
        access_token,
        cookie_name=settings.ir_access_token_cookie_name,
    )

    return IRAuthResponse(
        access_token=access_token,
        expires_in=settings.ir_access_token_expire_minutes * 60,
        player_id=player.player_id,
        username=player.username,
        wallet=player.wallet,
        vault=player.vault,
    )


@router.post("/auth/logout")
async def logout(
    response: Response,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Logout IR player (invalidate refresh tokens).

    Args:
        response: Response object
        player: Current authenticated player
        db: Database session

    Returns:
        dict: Success response

    Raises:
        HTTPException: If logout fails
    """
    auth_service = IRAuthService(db)
    try:
        await auth_service.logout(player.player_id)
    except IRAuthError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Clear auth cookies
    clear_auth_cookies(
        response,
        access_token_name=settings.ir_access_token_cookie_name,
        refresh_token_name=settings.ir_refresh_token_cookie_name,
    )

    return {"message": "Logout successful"}


# ================================================================
# Player Info Endpoints
# ================================================================

@router.get("/me", response_model=IRPlayerResponse)
async def get_current_player(
    player: IRPlayer = Depends(get_ir_current_player),
) -> IRPlayerResponse:
    """Get current authenticated player information.

    Args:
        player: Current authenticated player

    Returns:
        IRPlayerResponse: Player information

    Raises:
        HTTPException: If player not found
    """
    return IRPlayerResponse(
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        created_at=player.created_at,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
    )


@router.get("/players/{player_id}", response_model=IRPlayerResponse)
async def get_player(
    player_id: str,
    db: AsyncSession = Depends(get_db),
    _: IRPlayer = Depends(get_ir_current_player),
) -> IRPlayerResponse:
    """Get IR player information by ID.

    Args:
        player_id: Player UUID
        db: Database session
        _: Current authenticated player (for auth check)

    Returns:
        IRPlayerResponse: Player information

    Raises:
        HTTPException: If player not found
    """
    player_service = IRPlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return IRPlayerResponse(
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        created_at=player.created_at,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
    )
