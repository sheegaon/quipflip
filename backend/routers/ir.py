"""Initial Reaction (IR) game API endpoints."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Response, Header, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.config import get_settings
from backend.database import get_db
from backend.models.ir.ir_player import IRPlayer
from backend.models.ir.enums import IRSetStatus
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
    status: str
    entry_count: int


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
    set_id: str
    word: str
    status: str
    entry_count: int
    vote_count: int


class SubmitVoteRequest(BaseModel):
    """Request to submit a vote."""
    entry_id: str


class SubmitVoteResponse(BaseModel):
    """Response after submitting vote."""
    vote_id: str
    set_id: str


class ResultsResponse(BaseModel):
    """Response with finalized results."""
    set_id: str
    word: str
    winning_entry_id: str
    payout_amount: int
    total_pool: int


@router.post("/start", response_model=StartGameResponse)
async def start_game(
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> StartGameResponse:
    """Start a new backronym battle or join an existing one."""
    from backend.services.ir.ir_backronym_set_service import IRBackronymSetService
    from backend.services.ir.player_service import IRPlayerService
    from backend.services.ir.transaction_service import IRTransactionService

    try:
        # Check balance
        if player.wallet < settings.ir_backronym_entry_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance (need {settings.ir_backronym_entry_cost} IC)"
            )

        set_service = IRBackronymSetService(db)
        player_service = IRPlayerService(db)
        txn_service = IRTransactionService(db)

        # Get or create open set
        available_set = await set_service.get_available_set_for_entry(
            exclude_player_id=str(player.player_id)
        )

        if not available_set:
            set_obj = await set_service.create_set()
        else:
            set_obj = available_set

        # Debit wallet
        await player_service.update_wallet(str(player.player_id), -settings.ir_backronym_entry_cost)

        # Record transaction
        await txn_service.record_transaction(
            player_id=str(player.player_id),
            transaction_type=txn_service.ENTRY_CREATION,
            amount=-settings.ir_backronym_entry_cost,
            wallet_type="wallet",
            reference_id=str(set_obj.set_id),
        )

        return StartGameResponse(
            set_id=str(set_obj.set_id),
            word=set_obj.word,
            status=set_obj.status,
            entry_count=set_obj.entry_count,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sets/{set_id}/submit", response_model=SubmitBackronymResponse)
async def submit_backronym(
    set_id: str,
    request: SubmitBackronymRequest,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SubmitBackronymResponse:
    """Submit a backronym entry to a set."""
    from backend.services.ir.ir_backronym_set_service import IRBackronymSetService

    try:
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

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sets/{set_id}/status", response_model=SetStatusResponse)
async def get_set_status(
    set_id: str,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SetStatusResponse:
    """Get current status of a backronym set."""
    from backend.services.ir.ir_backronym_set_service import IRBackronymSetService

    try:
        set_service = IRBackronymSetService(db)
        set_obj = await set_service.get_set_by_id(set_id)

        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        return SetStatusResponse(
            set_id=set_id,
            word=set_obj.word,
            status=set_obj.status,
            entry_count=set_obj.entry_count,
            vote_count=set_obj.vote_count,
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
    from backend.services.ir.ir_vote_service import IRVoteService
    from backend.services.ir.player_service import IRPlayerService
    from backend.services.ir.transaction_service import IRTransactionService

    try:
        vote_service = IRVoteService(db)
        player_service = IRPlayerService(db)
        txn_service = IRTransactionService(db)

        # Check eligibility
        is_eligible, error, is_participant = await vote_service.check_vote_eligibility(
            str(player.player_id), set_id
        )

        if not is_eligible:
            raise HTTPException(status_code=400, detail=error)

        # Debit vote cost for non-participants
        if not is_participant:
            await player_service.update_wallet(str(player.player_id), -settings.ir_vote_cost)
            await txn_service.record_transaction(
                player_id=str(player.player_id),
                transaction_type="ir_vote_entry",
                amount=-settings.ir_vote_cost,
                wallet_type="wallet",
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

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sets/{set_id}/results", response_model=ResultsResponse)
async def get_results(
    set_id: str,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> ResultsResponse:
    """Get finalized results for a set."""
    from backend.services.ir.ir_backronym_set_service import IRBackronymSetService
    from backend.services.ir.ir_result_view_service import IRResultViewService
    from backend.services.ir.ir_scoring_service import IRScoringService

    try:
        set_service = IRBackronymSetService(db)
        result_service = IRResultViewService(db)
        scoring_service = IRScoringService(db)

        # Get set
        set_obj = await set_service.get_set_by_id(set_id)
        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        if set_obj.status != IRSetStatus.FINALIZED:
            raise HTTPException(status_code=400, detail="Set not finalized yet")

        # Claim result
        result = await result_service.claim_result(str(player.player_id), set_id)

        # Get summary
        summary = await scoring_service.get_payout_summary(set_id)

        return ResultsResponse(
            set_id=set_id,
            word=set_obj.word,
            winning_entry_id=summary.get("winner_entry_id", ""),
            payout_amount=result.get("payout_amount", 0),
            total_pool=summary.get("total_pool", 0),
        )

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
