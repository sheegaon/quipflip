"""Player API router."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.models.phraseset import PhraseSet
from backend.models.round import Round
from backend.schemas.player import (
    PlayerBalance,
    ClaimDailyBonusResponse,
    CurrentRoundResponse,
    PendingResultsResponse,
    PendingResult,
    CreatePlayerResponse,
    PlayerStatistics,
    TutorialStatus,
    UpdateTutorialProgressRequest,
    UpdateTutorialProgressResponse,
    DashboardDataResponse,
)
from backend.schemas.phraseset import (
    PhrasesetListResponse,
    PhrasesetDashboardSummary,
    UnclaimedResultsResponse,
    UnclaimedResult,
)
from backend.schemas.round import RoundAvailability
from backend.services.player_service import PlayerService
from backend.services.transaction_service import TransactionService
from backend.services.round_service import RoundService
from backend.services.phraseset_service import PhrasesetService
from backend.services.statistics_service import StatisticsService
from backend.services.tutorial_service import TutorialService
from backend.services.vote_service import VoteService
from backend.services.queue_service import QueueService
from backend.utils.exceptions import DailyBonusNotAvailableError
from backend.config import get_settings
from backend.schemas.auth import RegisterRequest
from backend.services.auth_service import AuthService, AuthError
from backend.utils.cookies import set_refresh_cookie
from datetime import datetime, UTC, timedelta
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


def ensure_utc(dt: datetime) -> datetime:
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
    """Create a new player account and return credentials."""

    auth_service = AuthService(db)
    try:
        player = await auth_service.register_player(
            username=request.username,
            email=request.email,
            password=request.password,
        )
    except AuthError as exc:
        message = str(exc)
        if message == "username_taken":
            raise HTTPException(status_code=409, detail="username_taken") from exc
        if message == "email_taken":
            raise HTTPException(status_code=409, detail="email_taken") from exc
        if message == "invalid_username":
            raise HTTPException(status_code=422, detail="invalid_username") from exc
        raise

    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return CreatePlayerResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type="bearer",
        player_id=player.player_id,
        username=player.username,
        balance=player.balance,
        message=(
            "Player created! Your account is ready to play. "
            "An access token and refresh token have been issued for authentication."
        ),
    )


@router.get("/balance", response_model=PlayerBalance)
async def get_balance(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get player balance and status."""
    player_service = PlayerService(db)

    # Get daily bonus status
    bonus_available = await player_service.is_daily_bonus_available(player)

    # Get outstanding prompts count
    outstanding = await player_service.get_outstanding_prompts_count(player.player_id)

    return PlayerBalance(
        username=player.username,
        balance=player.balance,
        starting_balance=settings.starting_balance,
        daily_bonus_available=bonus_available,
        daily_bonus_amount=settings.daily_bonus_amount,
        last_login_date=player.last_login_date,
        outstanding_prompts=outstanding,
    )


@router.post("/claim-daily-bonus", response_model=ClaimDailyBonusResponse)
async def claim_daily_bonus(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Claim daily login bonus."""
    player_service = PlayerService(db)
    transaction_service = TransactionService(db)

    try:
        amount = await player_service.claim_daily_bonus(player, transaction_service)

        # Refresh player to get updated balance
        await db.refresh(player)

        return ClaimDailyBonusResponse(
            success=True,
            amount=amount,
            new_balance=player.balance,
        )
    except DailyBonusNotAvailableError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current-round", response_model=CurrentRoundResponse)
async def get_current_round(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get player's current active round if any."""
    if not player.active_round_id:
        return CurrentRoundResponse(
            round_id=None,
            round_type=None,
            state=None,
            expires_at=None,
        )

    # Get round details
    round = await db.get(Round, player.active_round_id)
    if not round:
        return CurrentRoundResponse(
            round_id=None,
            round_type=None,
            state=None,
            expires_at=None,
        )

    # If round already resolved, clear pointer and return empty response
    if round.status != "active":
        if player.active_round_id == round.round_id:
            player.active_round_id = None
            await db.commit()
            await db.refresh(player)
        return CurrentRoundResponse(
            round_id=None,
            round_type=None,
            state=None,
            expires_at=None,
        )

    expires_at_utc = ensure_utc(round.expires_at)
    grace_cutoff = expires_at_utc + timedelta(seconds=settings.grace_period_seconds)

    if datetime.now(UTC) > grace_cutoff:
        round_service = RoundService(db)
        transaction_service = TransactionService(db)
        await round_service.handle_timeout(round.round_id, transaction_service)
        await db.refresh(player)
        return CurrentRoundResponse(
            round_id=None,
            round_type=None,
            state=None,
            expires_at=None,
        )

    # Build state based on round type
    state = {
        "round_id": str(round.round_id),
        "status": round.status,
        "expires_at": expires_at_utc.isoformat(),
        "cost": round.cost,
    }

    if round.round_type == "prompt":
        state.update({
            "prompt_text": round.prompt_text,
        })
    elif round.round_type == "copy":
        state.update({
            "original_phrase": round.original_phrase,
            "prompt_round_id": str(round.prompt_round_id),
        })
    elif round.round_type == "vote":
        # Get phraseset for voting
        phraseset = await db.get(PhraseSet, round.phraseset_id)
        if phraseset:
            # Randomize word order per-voter
            import random
            phrases = [phraseset.original_phrase, phraseset.copy_phrase_1, phraseset.copy_phrase_2]
            random.shuffle(phrases)
            state.update({
                "phraseset_id": str(phraseset.phraseset_id),
                "prompt_text": phraseset.prompt_text,
                "phrases": phrases,
            })

    return CurrentRoundResponse(
        round_id=round.round_id,
        round_type=round.round_type,
        state=state,
        expires_at=expires_at_utc,
    )


@router.get("/pending-results", response_model=PendingResultsResponse)
async def get_pending_results(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get list of finalized phrasesets where player was contributor.

    Fetches all finalized phrasesets (no limit) to ensure power users
    don't miss any results.
    """
    phraseset_service = PhrasesetService(db)

    # Fetch all finalized phrasesets by using a very high limit
    # This is acceptable because:
    # 1. Most players won't have >1000 finalized phrasesets
    # 2. This endpoint is only called during dashboard load (batched)
    # 3. The query is indexed and fast
    contributions, total = await phraseset_service.get_player_phrasesets(
        player.player_id,
        role="all",
        status="finalized",
        limit=10000,  # Practical limit for safety
        offset=0,
    )

    pending: list[PendingResult] = []
    for entry in contributions:
        finalized_at = entry.get("finalized_at")
        if not finalized_at:
            continue
        if not entry.get("phraseset_id"):
            continue
        pending.append(
            PendingResult(
                phraseset_id=entry["phraseset_id"],
                prompt_text=entry["prompt_text"],
                completed_at=ensure_utc(finalized_at),
                role=entry["your_role"],
                payout_claimed=entry.get("payout_claimed", False),
            )
        )

    pending.sort(key=lambda item: item.completed_at, reverse=True)

    # Log warning if hitting the limit (indicates we need real pagination)
    if total > 10000:
        logger.warning(
            f"Player {player.player_id} has {total} finalized phrasesets, "
            f"exceeding limit of 10000. Consider implementing cursor-based pagination."
        )

    return PendingResultsResponse(pending=pending)


@router.get(
    "/phrasesets",
    response_model=PhrasesetListResponse,
)
async def list_player_phrasesets(
    role: str = Query("all", regex="^(all|prompt|copy)$"),
    status: str = Query("all"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated list of phrasesets for the current player."""
    phraseset_service = PhrasesetService(db)
    phrasesets, total = await phraseset_service.get_player_phrasesets(
        player.player_id,
        role=role,
        status=status,
        limit=limit,
        offset=offset,
    )
    has_more = offset + len(phrasesets) < total
    return PhrasesetListResponse(
        phrasesets=phrasesets,
        total=total,
        has_more=has_more,
    )


@router.get(
    "/phrasesets/summary",
    response_model=PhrasesetDashboardSummary,
)
async def get_phraseset_summary(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Return dashboard summary of phrasesets for the player."""
    phraseset_service = PhrasesetService(db)
    summary = await phraseset_service.get_phraseset_summary(player.player_id)
    return PhrasesetDashboardSummary(**summary)


@router.get(
    "/unclaimed-results",
    response_model=UnclaimedResultsResponse,
)
async def get_unclaimed_results(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Return finalized phrasesets with unclaimed payouts."""
    phraseset_service = PhrasesetService(db)
    payload = await phraseset_service.get_unclaimed_results(player.player_id)
    return UnclaimedResultsResponse(**payload)


@router.get("/dashboard", response_model=DashboardDataResponse)
async def get_dashboard_data(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get all dashboard data in a single batched request for optimal performance.

    Reuses existing endpoint logic to avoid code duplication.
    Executes sequentially because AsyncSession is not concurrency-safe.
    Still much faster than 6 separate HTTP requests from the client.
    """
    # Reuse existing endpoint logic by calling the internal functions
    player_balance = await get_balance(player, db)
    current_round = await get_current_round(player, db)
    pending_results_response = await get_pending_results(player, db)
    phraseset_summary = await get_phraseset_summary(player, db)
    unclaimed_results_response = await get_unclaimed_results(player, db)

    # Round availability needs services
    player_service = PlayerService(db)
    round_service = RoundService(db)
    vote_service = VoteService(db)

    prompts_waiting = await round_service.get_available_prompts_count(player.player_id)
    phrasesets_waiting = await vote_service.count_available_wordsets_for_player(player.player_id)

    can_prompt, _ = await player_service.can_start_prompt_round(player)
    can_copy, _ = await player_service.can_start_copy_round(player)
    can_vote, _ = await player_service.can_start_vote_round(
        player,
        vote_service,
        available_count=phrasesets_waiting,
    )

    if prompts_waiting == 0:
        can_copy = False
    if phrasesets_waiting == 0:
        can_vote = False

    round_availability = RoundAvailability(
        can_prompt=can_prompt,
        can_copy=can_copy,
        can_vote=can_vote,
        prompts_waiting=prompts_waiting,
        phrasesets_waiting=phrasesets_waiting,
        copy_discount_active=QueueService.is_copy_discount_active(),
        copy_cost=QueueService.get_copy_cost(),
        current_round_id=player.active_round_id,
    )

    return DashboardDataResponse(
        player=player_balance,
        current_round=current_round,
        pending_results=pending_results_response.pending,
        phraseset_summary=phraseset_summary,
        unclaimed_results=unclaimed_results_response.unclaimed,
        round_availability=round_availability,
    )


@router.get("/statistics", response_model=PlayerStatistics)
async def get_player_statistics(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get comprehensive player statistics including win rates and earnings."""
    stats_service = StatisticsService(db)
    stats = await stats_service.get_player_statistics(player.player_id)
    return stats


@router.get("/tutorial/status", response_model=TutorialStatus)
async def get_tutorial_status(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get tutorial status for the current player."""
    tutorial_service = TutorialService(db)
    return await tutorial_service.get_tutorial_status(player.player_id)


@router.post("/tutorial/progress", response_model=UpdateTutorialProgressResponse)
async def update_tutorial_progress(
    request: UpdateTutorialProgressRequest,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Update tutorial progress for the current player."""
    tutorial_service = TutorialService(db)
    tutorial_status = await tutorial_service.update_tutorial_progress(
        player.player_id, request.progress
    )
    return UpdateTutorialProgressResponse(
        success=True,
        tutorial_status=tutorial_status,
    )


@router.post("/tutorial/reset", response_model=TutorialStatus)
async def reset_tutorial(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Reset tutorial progress for the current player."""
    tutorial_service = TutorialService(db)
    return await tutorial_service.reset_tutorial(player.player_id)
