"""Player API router."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.dependencies import get_current_player, enforce_guest_creation_rate_limit
from backend.models.player import Player
from backend.models.phraseset import Phraseset
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
    ChangePasswordRequest,
    ChangePasswordResponse,
    UpdateEmailRequest,
    UpdateEmailResponse,
    DeleteAccountRequest,
    CreateGuestResponse,
    UpgradeGuestRequest,
    UpgradeGuestResponse,
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
from backend.services.cleanup_service import CleanupService
from backend.utils.cookies import set_refresh_cookie, clear_refresh_cookie
from backend.utils.passwords import (
    verify_password,
    validate_password_strength,
    PasswordValidationError,
)
from datetime import datetime, UTC, timedelta
from typing import Optional
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
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


@router.post("/guest", response_model=CreateGuestResponse, status_code=201)
async def create_guest_player(
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(enforce_guest_creation_rate_limit),
):
    """Create a guest account with auto-generated credentials."""

    auth_service = AuthService(db)
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
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return CreateGuestResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type="bearer",
        player_id=player.player_id,
        username=player.username,
        balance=player.balance,
        email=player.email,
        password=guest_password,
        message=(
            f"Guest account created! Your temporary credentials are:\n"
            f"Email: {player.email}\n"
            f"Password: {guest_password}\n\n"
            f"You can upgrade to a full account anytime to choose your own email and password."
        ),
    )


@router.post("/upgrade", response_model=UpgradeGuestResponse)
async def upgrade_guest_account(
    request: UpgradeGuestRequest,
    response: Response,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade a guest account to a full account."""

    auth_service = AuthService(db)
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
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return UpgradeGuestResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        token_type="bearer",
        player_id=upgraded_player.player_id,
        username=upgraded_player.username,
        message="Account upgraded successfully! You can now log in with your new credentials.",
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
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        balance=player.balance,
        starting_balance=settings.starting_balance,
        daily_bonus_available=bonus_available,
        daily_bonus_amount=settings.daily_bonus_amount,
        last_login_date=ensure_utc(player.last_login_date),
        created_at=player.created_at,
        outstanding_prompts=outstanding,
        is_guest=player.is_guest,
        is_admin=player.is_admin,
        locked_until=ensure_utc(player.locked_until),
        flag_dismissal_streak=player.flag_dismissal_streak,
    )


@router.post("/claim-daily-bonus", response_model=ClaimDailyBonusResponse)
async def claim_daily_bonus(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Claim daily login bonus."""
    from backend.utils.cache import dashboard_cache
    
    player_service = PlayerService(db)
    transaction_service = TransactionService(db)

    try:
        amount = await player_service.claim_daily_bonus(player, transaction_service)

        # Refresh player to get updated balance
        await db.refresh(player)
        
        # Invalidate cached dashboard data since balance changed
        dashboard_cache.invalidate_player_data(player.player_id)

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
        phraseset = await db.get(Phraseset, round.phraseset_id)
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
    return await _get_pending_results_internal(player, db, None)


async def _get_pending_results_internal(
    player: Player,
    db: AsyncSession,
    phraseset_service: Optional[PhrasesetService],
):
    """Internal implementation that accepts optional service for reuse."""
    if phraseset_service is None:
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
                result_viewed=entry.get("result_viewed", False),
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
    return await _get_phraseset_summary_internal(player, db, None)


async def _get_phraseset_summary_internal(
    player: Player,
    db: AsyncSession,
    phraseset_service: Optional[PhrasesetService],
):
    """Internal implementation that accepts optional service for reuse."""
    if phraseset_service is None:
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
    return await _get_unclaimed_results_internal(player, db, None)


async def _get_unclaimed_results_internal(
    player: Player,
    db: AsyncSession,
    phraseset_service: Optional[PhrasesetService],
):
    """Internal implementation that accepts optional service for reuse."""
    if phraseset_service is None:
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
    
    Now includes caching to reduce database load from rapid-fire requests.
    """
    from backend.utils.cache import dashboard_cache
    
    # Check cache first
    cache_key = f"dashboard:{player.player_id}"
    cached_data = dashboard_cache.get(cache_key)
    if cached_data:
        logger.info(f"Returning cached dashboard data for player {player.player_id}")
        return cached_data
    
    logger.info(f"Generating fresh dashboard data for player {player.player_id}")

    # Create a single PhrasesetService instance to share across calls
    # This allows the contributions cache to work across all three endpoints,
    # reducing payout calculations from 3x to 1x per dashboard load
    phraseset_service = PhrasesetService(db)

    # Reuse existing endpoint logic by calling the internal functions
    player_balance = await get_balance(player, db)
    current_round = await get_current_round(player, db)
    pending_results_response = await _get_pending_results_internal(player, db, phraseset_service)
    phraseset_summary = await _get_phraseset_summary_internal(player, db, phraseset_service)
    unclaimed_results_response = await _get_unclaimed_results_internal(player, db, phraseset_service)

    # Round availability needs services
    player_service = PlayerService(db)
    round_service = RoundService(db)
    vote_service = VoteService(db)

    prompts_waiting = await round_service.get_available_prompts_count(player.player_id)
    phrasesets_waiting = await vote_service.count_available_phrasesets_for_player(player.player_id)

    # Make sure the prompt queue reflects database state before checking availability.
    await round_service.ensure_prompt_queue_populated()

    can_prompt, _ = await player_service.can_start_prompt_round(player)
    can_copy, _ = await player_service.can_start_copy_round(player)
    await player_service.refresh_vote_lockout_state(player)
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
        # Game constants from config
        prompt_cost=settings.prompt_cost,
        vote_cost=settings.vote_cost,
        vote_payout_correct=settings.vote_payout_correct,
        abandoned_penalty=settings.abandoned_penalty,
    )

    dashboard_data = DashboardDataResponse(
        player=player_balance,
        current_round=current_round,
        pending_results=pending_results_response.pending,
        phraseset_summary=phraseset_summary,
        unclaimed_results=unclaimed_results_response.unclaimed,
        round_availability=round_availability,
    )
    
    # Cache the response for 10 seconds (shorter TTL for dashboard since it changes frequently)
    dashboard_cache.set(cache_key, dashboard_data, ttl=10.0)
    
    return dashboard_data


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


@router.post("/password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    response: Response,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Allow the current player to change their password."""

    if not verify_password(request.current_password, player.password_hash):
        raise HTTPException(status_code=401, detail="invalid_current_password")

    if verify_password(request.new_password, player.password_hash):
        raise HTTPException(status_code=400, detail="password_unchanged")

    try:
        validate_password_strength(request.new_password)
    except PasswordValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    player_service = PlayerService(db)
    await player_service.update_password(player, request.new_password)

    auth_service = AuthService(db)
    access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
    set_refresh_cookie(response, refresh_token, expires_days=settings.refresh_token_exp_days)

    return ChangePasswordResponse(
        message="Password updated successfully.",
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.patch("/email", response_model=UpdateEmailResponse)
async def update_email(
    request: UpdateEmailRequest,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Allow the current player to update their email address."""

    if not verify_password(request.password, player.password_hash):
        raise HTTPException(status_code=401, detail="invalid_password")

    player_service = PlayerService(db)

    if player.email and player.email.lower() == request.new_email.strip().lower():
        return UpdateEmailResponse(email=player.email)

    try:
        updated = await player_service.update_email(player, request.new_email)
    except ValueError as exc:
        message = str(exc)
        if message == "email_taken":
            raise HTTPException(status_code=409, detail="email_taken") from exc
        if message == "invalid_email":
            raise HTTPException(status_code=422, detail="invalid_email") from exc
        raise

    return UpdateEmailResponse(email=updated.email)


@router.delete("/account", status_code=204)
async def delete_account(
    request: DeleteAccountRequest,
    response: Response,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Delete the current player's account and related data."""

    if not verify_password(request.password, player.password_hash):
        raise HTTPException(status_code=401, detail="invalid_password")

    cleanup_service = CleanupService(db)
    await cleanup_service.delete_player(player.player_id)

    clear_refresh_cookie(response)
    response.status_code = 204
    return None
