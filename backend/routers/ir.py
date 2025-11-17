"""Initial Reaction (IR) game API endpoints."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Response, Header, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.config import get_settings
from backend.database import get_db
from backend.models.ir.ir_player import IRPlayer
from backend.models.ir.enums import IRSetStatus
from backend.models.ir.ir_backronym_set import IRBackronymSet
from backend.models.ir.ir_backronym_entry import IRBackronymEntry
from backend.services.ir.auth_service import IRAuthService, IRAuthError
from backend.services.ir.player_service import IRPlayerService, IRPlayerError
from backend.services.ir.transaction_service import IRTransactionService, IRTransactionError
from backend.services.ir.ir_backronym_set_service import IRBackronymSetService
from backend.services.ir.ir_vote_service import IRVoteService, IRVoteError
from backend.services.ir.ir_result_view_service import IRResultViewService
from backend.services.ir.ir_scoring_service import IRScoringService
from backend.services.ir.ir_daily_bonus_service import (
    IRDailyBonusService,
    IRDailyBonusError,
)
from backend.utils.cookies import set_access_token_cookie, set_refresh_cookie, clear_auth_cookies

router = APIRouter(tags=["ir"])
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


class IRPlayerInfo(BaseModel):
    """IR player info for auth response."""

    player_id: str
    username: str
    email: str | None = None
    wallet: int
    vault: int
    is_guest: bool
    created_at: datetime | None = None
    daily_bonus_available: bool = True
    last_login_date: str | None = None


class IRAuthResponse(BaseModel):
    """IR authentication response."""

    access_token: str
    refresh_token: str | None = None
    player: IRPlayerInfo


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


class IRUpgradeGuestRequest(BaseModel):
    """Upgrade guest account request."""

    email: str
    password: str


class IRPlayerBalanceResponse(BaseModel):
    """Balance response payload."""

    wallet: int
    vault: int
    daily_bonus_available: bool


class IRDashboardPlayerSummary(BaseModel):
    player_id: str
    username: str
    wallet: int
    vault: int
    daily_bonus_available: bool
    created_at: datetime


class IRDashboardActiveSession(BaseModel):
    set_id: str
    word: str
    status: str
    has_submitted_entry: bool
    has_voted: bool


class IRPendingResult(BaseModel):
    set_id: str
    word: str
    payout_amount: int
    finalized_at: str | None = None


class IRDashboardResponse(BaseModel):
    player: IRDashboardPlayerSummary
    active_session: IRDashboardActiveSession | None
    pending_results: list[IRPendingResult]
    wallet: int
    vault: int
    daily_bonus_available: bool


class IRClaimDailyBonusResponse(BaseModel):
    bonus_amount: int
    new_balance: int
    next_claim_available_at: str


# ================================================================
# Game/Set Related Schemas
# ================================================================

class BackronymSet(BaseModel):
    """Backronym set details."""
    set_id: str
    word: str
    mode: str  # 'standard' or 'rapid'
    status: str  # 'open', 'voting', 'finalized'
    entry_count: int
    vote_count: int
    non_participant_vote_count: int = 0
    total_pool: int = 0
    creator_final_pool: int = 0
    created_at: str
    transitions_to_voting_at: str | None = None
    voting_finalized_at: str | None = None


class BackronymEntry(BaseModel):
    """Backronym entry details."""
    entry_id: str
    set_id: str
    player_id: str
    backronym_text: list[str]  # Array of words
    is_ai: bool = False
    submitted_at: str
    vote_share_pct: float | None = None
    received_votes: int = 0
    forfeited_to_vault: int = 0


class BackronymVote(BaseModel):
    """Backronym vote details."""
    vote_id: str
    set_id: str
    player_id: str
    chosen_entry_id: str
    is_participant_voter: bool = True
    is_ai: bool = False
    is_correct_popular: bool | None = None
    created_at: str


class PayoutBreakdown(BaseModel):
    """Payout breakdown for a result."""
    entry_cost: int = 0
    vote_cost: int = 0
    gross_payout: int = 0
    vault_rake: int = 0
    net_payout: int = 0
    vote_reward: int = 0


# ================================================================
# Authentication Dependencies
# ================================================================

async def get_ir_current_player(
    authorization: str | None = Header(None, alias="Authorization"),
    ir_access_token: str | None = Cookie(None),
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
        player_id=str(player.player_id),
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        created_at=player.created_at,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
    )


@router.get("/player/balance", response_model=IRPlayerBalanceResponse)
async def get_player_balance(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> IRPlayerBalanceResponse:
    """Return wallet/vault balances and bonus availability."""

    player_service = IRPlayerService(db)
    fresh_player = await player_service.get_player_by_id(str(player.player_id))
    if not fresh_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    bonus_service = IRDailyBonusService(db)
    bonus_available = await bonus_service.is_bonus_available(str(player.player_id))

    return IRPlayerBalanceResponse(
        wallet=fresh_player.wallet,
        vault=fresh_player.vault,
        daily_bonus_available=bonus_available,
    )


@router.get("/player/dashboard", response_model=IRDashboardResponse)
async def get_player_dashboard(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> IRDashboardResponse:
    """Return dashboard summary for the signed-in player."""

    player_service = IRPlayerService(db)
    fresh_player = await player_service.get_player_by_id(str(player.player_id))
    if not fresh_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    bonus_service = IRDailyBonusService(db)
    bonus_available = await bonus_service.is_bonus_available(str(player.player_id))

    active_stmt = (
        select(IRBackronymSet)
        .join(IRBackronymEntry, IRBackronymEntry.set_id == IRBackronymSet.set_id)
        .where(IRBackronymEntry.player_id == str(player.player_id))
        .where(
            IRBackronymSet.status.in_([IRSetStatus.OPEN, IRSetStatus.VOTING])
        )
        .order_by(IRBackronymSet.created_at.desc())
        .limit(1)
    )
    active_result = await db.execute(active_stmt)
    active_set = active_result.scalars().first()

    result_service = IRResultViewService(db)
    pending = await result_service.get_pending_results(str(player.player_id))
    pending_models = [IRPendingResult(**item) for item in pending]

    # Determine boolean flags for active session
    active_session = None
    if active_set:
        set_service = IRBackronymSetService(db)
        set_details = await set_service.get_set_details(str(active_set.set_id))

        has_submitted_entry = False
        if set_details.get("entries"):
            for entry in set_details["entries"]:
                if entry.get("player_id") == str(player.player_id):
                    has_submitted_entry = True
                    break

        has_voted = False
        if set_details.get("votes"):
            for vote in set_details["votes"]:
                if vote.get("player_id") == str(player.player_id):
                    has_voted = True
                    break

        active_session = IRDashboardActiveSession(
            set_id=str(active_set.set_id),
            word=active_set.word,
            status=str(active_set.status),
            has_submitted_entry=has_submitted_entry,
            has_voted=has_voted,
        )

    return IRDashboardResponse(
        player=IRDashboardPlayerSummary(
            player_id=str(fresh_player.player_id),
            username=fresh_player.username,
            wallet=fresh_player.wallet,
            vault=fresh_player.vault,
            daily_bonus_available=bonus_available,
            created_at=fresh_player.created_at,
        ),
        active_session=active_session,
        pending_results=pending_models,
        wallet=fresh_player.wallet,
        vault=fresh_player.vault,
        daily_bonus_available=bonus_available,
    )


@router.post("/player/claim-daily-bonus", response_model=IRClaimDailyBonusResponse)
async def claim_daily_bonus(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> IRClaimDailyBonusResponse:
    """Claim the daily InitCoin bonus."""

    bonus_service = IRDailyBonusService(db)
    player_service = IRPlayerService(db)

    try:
        bonus = await bonus_service.claim_bonus(str(player.player_id))
    except IRDailyBonusError as exc:
        status = 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc

    refreshed_player = await player_service.get_player_by_id(str(player.player_id))
    if not refreshed_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    # Calculate next claim time (24 hours from now)
    from datetime import timedelta
    claimed_at = bonus["claimed_at"]
    if isinstance(claimed_at, str):
        # Parse ISO format string to datetime
        from datetime import datetime
        claimed_at = datetime.fromisoformat(claimed_at.replace('Z', '+00:00'))
    next_claim = claimed_at + timedelta(hours=24)

    return IRClaimDailyBonusResponse(
        bonus_amount=bonus["amount"],
        new_balance=refreshed_player.wallet,
        next_claim_available_at=next_claim.isoformat(),
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
        player_id=str(player.player_id),
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        created_at=player.created_at,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
    )


# ================================================================
# Game Endpoints
# ================================================================

class StartGameRequest(BaseModel):
    """Request to start a backronym battle."""
    pass


class StartGameResponse(BaseModel):
    """Response when starting a game."""
    set_id: str
    word: str
    mode: str
    status: str


class SubmitBackronymRequest(BaseModel):
    """Request to submit a backronym entry."""
    words: list[str]


class SubmitBackronymResponse(BaseModel):
    """Response after submitting backronym."""
    entry_id: str
    set_id: str
    status: str


class SetStatusResponse(BaseModel):
    """Response with current set status."""
    set: BackronymSet
    player_has_submitted: bool
    player_has_voted: bool


class SubmitVoteRequest(BaseModel):
    """Request to submit a vote."""
    entry_id: str


class SubmitVoteResponse(BaseModel):
    """Response after submitting vote."""
    vote_id: str
    set_id: str


class ResultsResponse(BaseModel):
    """Response with finalized results."""
    set: BackronymSet
    entries: list[BackronymEntry]
    votes: list[BackronymVote]
    player_entry: BackronymEntry | None = None
    player_vote: BackronymVote | None = None
    payout_breakdown: PayoutBreakdown | None = None


@router.post("/start", response_model=StartGameResponse)
async def start_game(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> StartGameResponse:
    """Start a new backronym battle or join an existing one."""
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Check balance
        if player.wallet < settings.ir_backronym_entry_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance (need {settings.ir_backronym_entry_cost} IC)"
            )

        set_service = IRBackronymSetService(db)
        txn_service = IRTransactionService(db)

        # Get or create open set
        available_set = await set_service.get_available_set_for_entry(
            exclude_player_id=str(player.player_id)
        )

        if not available_set:
            set_obj = await set_service.create_set()
        else:
            set_obj = available_set

        await txn_service.debit_wallet(
            player_id=str(player.player_id),
            amount=settings.ir_backronym_entry_cost,
            transaction_type=txn_service.ENTRY_CREATION,
            reference_id=str(set_obj.set_id),
        )

        return StartGameResponse(
            set_id=str(set_obj.set_id),
            word=set_obj.word,
            mode=set_obj.mode,
            status=str(set_obj.status),
        )

    except HTTPException:
        raise
    except IRTransactionError as exc:
        logger.error(f"IR transaction error in start_game: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        logger.error(f"Unexpected error in start_game: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sets/{set_id}/submit", response_model=SubmitBackronymResponse)
async def submit_backronym(
    set_id: str,
    request: SubmitBackronymRequest,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SubmitBackronymResponse:
    """Submit a backronym entry to a set.

    Expected request body:
    {
        "words": ["word1", "word2", "word3", ...]
    }
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.debug(f"submit_backronym called with set_id={set_id}, words={request.words}")

        set_service = IRBackronymSetService(db)

        # Get set
        set_obj = await set_service.get_set_by_id(set_id)
        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        # Add entry
        entry = await set_service.add_entry(
            set_id=set_id,
            player_id=str(player.player_id),
            backronym_text=request.words,
            is_ai=False,
        )

        # Get updated set
        set_obj = await set_service.get_set_by_id(set_id)

        return SubmitBackronymResponse(
            entry_id=str(entry.entry_id),
            set_id=set_id,
            status=set_obj.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in submit_backronym: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sets/{set_id}/status", response_model=SetStatusResponse)
async def get_set_status(
    set_id: str,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SetStatusResponse:
    """Get current status of a backronym set."""

    try:
        set_service = IRBackronymSetService(db)
        set_obj = await set_service.get_set_by_id(set_id)

        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        # Get complete set details with entries and votes
        set_details = await set_service.get_set_details(set_id)

        # Check if player has submitted an entry
        player_has_submitted = False
        if set_details.get("entries"):
            for entry in set_details["entries"]:
                if entry.get("player_id") == str(player.player_id):
                    player_has_submitted = True
                    break

        # Check if player has voted
        player_has_voted = False
        if set_details.get("votes"):
            for vote in set_details["votes"]:
                if vote.get("player_id") == str(player.player_id):
                    player_has_voted = True
                    break

        return SetStatusResponse(
            set=BackronymSet(
                set_id=set_id,
                word=set_obj.word,
                mode=set_obj.mode,
                status=str(set_obj.status),
                entry_count=len(set_details.get("entries", [])),
                vote_count=len(set_details.get("votes", [])),
                non_participant_vote_count=0,  # TODO: calculate if needed
                total_pool=0,  # TODO: fetch from scoring service if needed
                creator_final_pool=0,  # TODO: calculate if needed
                created_at=set_obj.created_at.isoformat() if set_obj.created_at else "",
                transitions_to_voting_at=None,  # TODO: set if available
                voting_finalized_at=None,  # TODO: set if available
            ),
            player_has_submitted=player_has_submitted,
            player_has_voted=player_has_voted,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sets/{set_id}/vote", response_model=SubmitVoteResponse)
async def submit_vote(
    set_id: str,
    request: SubmitVoteRequest,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SubmitVoteResponse:
    """Submit a vote on a backronym entry."""

    try:
        vote_service = IRVoteService(db)
        txn_service = IRTransactionService(db)

        # Check eligibility
        is_eligible, error, is_participant = await vote_service.check_vote_eligibility(
            str(player.player_id), set_id
        )

        if not is_eligible:
            raise HTTPException(status_code=400, detail=error)

        # Debit vote cost for non-participants
        if not is_participant:
            await txn_service.debit_wallet(
                player_id=str(player.player_id),
                amount=settings.ir_vote_cost,
                transaction_type=txn_service.VOTE_ENTRY,
                reference_id=set_id,
            )

        # Submit vote
        vote_result = await vote_service.submit_vote(
            set_id=set_id,
            player_id=str(player.player_id),
            chosen_entry_id=request.entry_id,
            is_participant=is_participant,
        )

        return SubmitVoteResponse(
            vote_id=vote_result["vote_id"],
            set_id=vote_result["set_id"],
        )

    except (IRTransactionError, IRVoteError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sets/{set_id}/results", response_model=ResultsResponse)
async def get_results(
    set_id: str,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> ResultsResponse:
    """Get finalized results for a set with full details."""

    try:
        set_service = IRBackronymSetService(db)
        result_service = IRResultViewService(db)
        scoring_service = IRScoringService(db)
        vote_service = IRVoteService(db)

        # Get set
        set_obj = await set_service.get_set_by_id(set_id)
        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        if set_obj.status != IRSetStatus.FINALIZED:
            raise HTTPException(status_code=400, detail="Set not finalized yet")

        # Claim result
        result = await result_service.claim_result(str(player.player_id), set_id)

        # Get complete set details with entries and votes
        set_details = await set_service.get_set_details(set_id)

        # Get player's entry and vote
        player_entry = None
        if set_details.get("entries"):
            for entry in set_details["entries"]:
                if entry.get("player_id") == str(player.player_id):
                    player_entry = entry
                    break

        player_vote = None
        if set_details.get("votes"):
            for vote in set_details["votes"]:
                if vote.get("player_id") == str(player.player_id):
                    player_vote = vote
                    break

        # Get payout summary
        summary = await scoring_service.get_payout_summary(set_id)

        # Build payout breakdown
        payout_breakdown = None
        if result:
            payout_breakdown = {
                "entry_cost": result.get("entry_cost", 100),
                "vote_cost": result.get("vote_cost", 0),
                "gross_payout": result.get("gross_payout", 0),
                "vault_rake": result.get("vault_rake", 0),
                "net_payout": result.get("net_payout", 0),
                "vote_reward": result.get("vote_reward", 0),
            }

        return ResultsResponse(
            set=BackronymSet(
                set_id=set_id,
                word=set_obj.word,
                mode=set_obj.mode,
                status=str(set_obj.status),
                entry_count=len(set_details.get("entries", [])),
                vote_count=len(set_details.get("votes", [])),
                non_participant_vote_count=0,  # TODO: calculate
                total_pool=summary.get("total_pool", 0),
                creator_final_pool=0,  # TODO: calculate
                created_at=set_obj.created_at.isoformat() if set_obj.created_at else "",
                transitions_to_voting_at=None,  # TODO
                voting_finalized_at=None,  # TODO
            ),
            entries=set_details.get("entries", []),
            votes=set_details.get("votes", []),
            player_entry=player_entry,
            player_vote=player_vote,
            payout_breakdown=payout_breakdown,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ================================================================
# Statistics Endpoints
# ================================================================

class PlayerStatsResponse(BaseModel):
    """Player statistics response."""
    player_id: str
    username: str
    wallet: int
    vault: int
    entries_submitted: int
    votes_cast: int
    net_earnings: int


class LeaderboardEntry(BaseModel):
    """Leaderboard entry."""
    rank: int
    player_id: str
    username: str
    vault: int
    value: int


@router.get("/player/statistics", response_model=PlayerStatsResponse)
async def get_player_stats(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerStatsResponse:
    """Get player statistics."""
    from backend.services.ir.ir_statistics_service import IRStatisticsService

    try:
        stats_service = IRStatisticsService(db)
        stats = await stats_service.get_player_stats(str(player.player_id))

        return PlayerStatsResponse(
            player_id=stats.get("player_id", ""),
            username=stats.get("username", ""),
            wallet=stats.get("wallet", 0),
            vault=stats.get("vault", 0),
            entries_submitted=stats.get("stats", {}).get("entries_submitted", 0),
            votes_cast=stats.get("stats", {}).get("votes_cast", 0),
            net_earnings=stats.get("stats", {}).get("net_earnings", 0),
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/leaderboards/creators", response_model=list[LeaderboardEntry])
async def get_creator_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _: IRPlayer = Depends(get_ir_current_player),
) -> list[LeaderboardEntry]:
    """Get creator leaderboard ranked by vault contributions."""
    from backend.services.ir.ir_statistics_service import IRStatisticsService

    try:
        stats_service = IRStatisticsService(db)
        leaderboard = await stats_service.get_creator_leaderboard(limit=limit)

        return [
            LeaderboardEntry(
                rank=entry.get("rank", 0),
                player_id=entry.get("player_id", ""),
                username=entry.get("username", ""),
                vault=entry.get("vault", 0),
                value=entry.get("entries_created", 0),
            )
            for entry in leaderboard
        ]

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/leaderboards/voters", response_model=list[LeaderboardEntry])
async def get_voter_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _: IRPlayer = Depends(get_ir_current_player),
) -> list[LeaderboardEntry]:
    """Get voter leaderboard."""
    from backend.services.ir.ir_statistics_service import IRStatisticsService

    try:
        stats_service = IRStatisticsService(db)
        leaderboard = await stats_service.get_voter_leaderboard(limit=limit)

        return [
            LeaderboardEntry(
                rank=entry.get("rank", 0),
                player_id=entry.get("player_id", ""),
                username=entry.get("username", ""),
                vault=entry.get("vault", 0),
                value=entry.get("votes_cast", 0),
            )
            for entry in leaderboard
        ]

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
