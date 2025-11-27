"""Player API router for QuipFlip."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, UTC, timedelta
from typing import Optional
import logging

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.qf.player import QFPlayer
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.round import Round
from backend.schemas.player import (
    PlayerBalance,
    CurrentRoundResponse,
    PendingResultsResponse,
    PendingResult,
    PlayerStatistics,
    TutorialStatus,
    UpdateTutorialProgressRequest,
    UpdateTutorialProgressResponse,
    DashboardDataResponse,
    WeeklyLeaderboardEntry,
    LeaderboardResponse,
    RoleLeaderboard,
    GrossEarningsLeaderboardEntry,
    GrossEarningsLeaderboard,
)
from backend.schemas.phraseset import (
    PhrasesetListResponse,
    PhrasesetDashboardSummary,
    UnclaimedResultsResponse,
)
from backend.schemas.round import RoundAvailability
from backend.services import TransactionService, GameType
from backend.services.tutorial_service import TutorialService
from backend.utils import ensure_utc
from backend.config import get_settings
from backend.routers.player_router_base import PlayerRouterBase
from backend.services.qf.player_service import QFPlayerService
from backend.services.qf.round_service import QFRoundService
from backend.services.qf.phraseset_service import PhrasesetService
from backend.services.qf.statistics_service import QFStatisticsService
from backend.services.qf.scoring_service import QFScoringService, LEADERBOARD_ROLES
from backend.services.qf.vote_service import QFVoteService
from backend.services.qf.cleanup_service import QFCleanupService
from backend.services.qf.queue_service import QFQueueService

logger = logging.getLogger(__name__)
settings = get_settings()


class QFPlayerRouter(PlayerRouterBase):
    """Quipflip player router with game-specific endpoints."""

    def __init__(self):
        """Initialize the QF player router."""
        super().__init__(GameType.QF)
        self._add_qf_specific_routes()

    @property
    def player_service_class(self):
        """Return the QF player service class."""
        return QFPlayerService

    @property
    def cleanup_service_class(self):
        """Return the QF cleanup service class."""
        return QFCleanupService

    async def get_balance(self, player: QFPlayer, db: AsyncSession) -> PlayerBalance:
        """Get player balance and status."""
        return await _get_player_balance(player, db)

    def _add_qf_specific_routes(self):
        """Add QuipFlip-specific routes to the router."""
        
        player_dependency = self._current_player_dependency()

        @self.router.get("/current-round", response_model=CurrentRoundResponse)
        async def get_current_round(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get player's current active round if any."""
            return await _get_current_round(player, db)

        @self.router.get("/pending-results", response_model=PendingResultsResponse)
        async def get_pending_results(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get list of finalized phrasesets where player was contributor."""
            return await _get_pending_results_internal(player, db, None)

        @self.router.get(
            "/phrasesets",
            response_model=PhrasesetListResponse,
        )
        async def list_player_phrasesets(
            role: str = Query("all", pattern="^(all|prompt|copy|vote)$"),
            status: str = Query("all"),
            limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0),
            player: QFPlayer = Depends(player_dependency),
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

        @self.router.get(
            "/phrasesets/summary",
            response_model=PhrasesetDashboardSummary,
        )
        async def get_phraseset_summary(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Return dashboard summary of phrasesets for the player."""
            return await _get_phraseset_summary_internal(player, db, None)

        @self.router.get(
            "/unclaimed-results",
            response_model=UnclaimedResultsResponse,
        )
        async def get_unclaimed_results(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Return finalized phrasesets with unclaimed payouts."""
            return await _get_unclaimed_results_internal(player, db, None)

        @self.router.get("/dashboard", response_model=DashboardDataResponse)
        async def get_dashboard_data(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get all dashboard data in a single batched request for optimal performance."""
            return await _get_dashboard_data(player, db)

        @self.router.get("/statistics", response_model=PlayerStatistics)
        async def get_player_statistics(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get comprehensive player statistics including win rates and earnings."""
            stats_service = QFStatisticsService(db)
            stats = await stats_service.get_player_statistics(player.player_id)
            return stats

        @self.router.get("/statistics/weekly-leaderboard", response_model=LeaderboardResponse)
        async def get_weekly_leaderboard(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Return weekly leaderboards for all three roles plus gross earnings highlighting the current player."""
            return await _get_leaderboard_data(player, db, "weekly")

        @self.router.get("/statistics/alltime-leaderboard", response_model=LeaderboardResponse)
        async def get_alltime_leaderboard(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Return all-time leaderboards for all three roles plus gross earnings highlighting the current player."""
            return await _get_leaderboard_data(player, db, "alltime")

        @self.router.get("/tutorial/status", response_model=TutorialStatus)
        async def get_tutorial_status(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get tutorial status for the current player."""
            tutorial_service = TutorialService(db)
            return await tutorial_service.get_tutorial_status(player.player_id)

        @self.router.post("/tutorial/progress", response_model=UpdateTutorialProgressResponse)
        async def update_tutorial_progress(
            request: UpdateTutorialProgressRequest,
            player: QFPlayer = Depends(player_dependency),
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

        @self.router.post("/tutorial/reset", response_model=TutorialStatus)
        async def reset_tutorial(
            player: QFPlayer = Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Reset tutorial progress for the current player."""
            tutorial_service = TutorialService(db)
            return await tutorial_service.reset_tutorial(player.player_id)


# Helper functions for QF-specific endpoints
async def _get_player_balance(player: QFPlayer, db: AsyncSession) -> PlayerBalance:
    """Get player balance and status - shared helper function."""
    player_service = QFPlayerService(db)

    # Get daily bonus status
    bonus_available = await player_service.is_daily_bonus_available(player)

    # Get outstanding prompts count
    outstanding = await player_service.get_outstanding_prompts_count(player.player_id)

    return PlayerBalance(
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        starting_balance=settings.qf_starting_wallet,
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


async def _get_current_round(player: QFPlayer, db: AsyncSession) -> CurrentRoundResponse:
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

    # Ensure expires_at is not None
    if not round.expires_at:
        return CurrentRoundResponse(
            round_id=None,
            round_type=None,
            state=None,
            expires_at=None,
        )

    expires_at_utc = ensure_utc(round.expires_at)
    grace_cutoff = expires_at_utc + timedelta(seconds=settings.grace_period_seconds)

    if datetime.now(UTC) > grace_cutoff:
        round_service = QFRoundService(db)
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


async def _get_pending_results_internal(
    player: QFPlayer,
    db: AsyncSession,
    phraseset_service: Optional[PhrasesetService],
):
    """Internal implementation that accepts optional service for reuse."""
    if phraseset_service is None:
        phraseset_service = PhrasesetService(db)

    # Fetch all finalized phrasesets by using a very high limit
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
        # Skip vote contributions - results page only shows prompt/copy rounds
        if entry["your_role"] == "vote":
            continue
        pending.append(
            PendingResult(
                phraseset_id=entry["phraseset_id"],
                prompt_text=entry["prompt_text"],
                completed_at=ensure_utc(finalized_at),
                role=entry["your_role"],
                result_viewed=entry.get("result_viewed", False),
                prompt_round_id=entry.get("prompt_round_id"),
                copy_round_id=entry.get("copy_round_id"),
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


async def _get_phraseset_summary_internal(
    player: QFPlayer,
    db: AsyncSession,
    phraseset_service: Optional[PhrasesetService],
):
    """Internal implementation that accepts optional service for reuse."""
    if phraseset_service is None:
        phraseset_service = PhrasesetService(db)
    summary = await phraseset_service.get_phraseset_summary(player.player_id)
    return PhrasesetDashboardSummary(**summary)


async def _get_unclaimed_results_internal(
    player: QFPlayer,
    db: AsyncSession,
    phraseset_service: Optional[PhrasesetService],
):
    """Internal implementation that accepts optional service for reuse."""
    if phraseset_service is None:
        phraseset_service = PhrasesetService(db)
    payload = await phraseset_service.get_unclaimed_results(player.player_id)
    return UnclaimedResultsResponse(**payload)


async def _get_dashboard_data(player: QFPlayer, db: AsyncSession) -> DashboardDataResponse:
    """Get all dashboard data in a single batched request for optimal performance."""
    from backend.utils.cache import dashboard_cache

    try:
        # Check cache first
        cache_key = f"dashboard:{player.player_id}"
        cached_data = dashboard_cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached dashboard data for player {player.player_id}")
            return cached_data

        logger.info(f"Generating fresh dashboard data for player {player.player_id}")

        # Create a single PhrasesetService instance to share across calls
        phraseset_service = PhrasesetService(db)

        try:
            # Reuse existing endpoint logic by calling the internal functions
            player_balance = await _get_player_balance(player, db)
            current_round = await _get_current_round(player, db)
            pending_results_response = await _get_pending_results_internal(player, db, phraseset_service)
            phraseset_summary = await _get_phraseset_summary_internal(player, db, phraseset_service)
            unclaimed_results_response = await _get_unclaimed_results_internal(player, db, phraseset_service)
        except Exception as e:
            logger.error(f"Failed to fetch player results data for {player.player_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load player results")

        # Round availability needs services
        try:
            player_service = QFPlayerService(db)
            round_service = QFRoundService(db)
            vote_service = QFVoteService(db)

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
                copy_discount_active=QFQueueService.is_copy_discount_active(),
                copy_cost=QFQueueService.get_copy_cost(),
                current_round_id=player.active_round_id,
                # Game constants from config
                prompt_cost=settings.prompt_cost,
                vote_cost=settings.vote_cost,
                vote_payout_correct=settings.vote_payout_correct,
                abandoned_penalty=settings.abandoned_penalty,
            )
        except Exception as e:
            logger.error(f"Failed to determine round availability for {player.player_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to load round availability")

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
    except HTTPException:
        # Re-raise HTTPException to pass through
        raise
    except Exception as e:
        logger.error(f"Unexpected error in dashboard endpoint for {player.player_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load dashboard")


async def _get_leaderboard_data(player: QFPlayer, db: AsyncSession, period: str) -> LeaderboardResponse:
    """Get leaderboard data for the specified period."""
    scoring_service = QFScoringService(db)
    
    if period == "weekly":
        role_data, generated_at = await scoring_service.get_weekly_leaderboard_for_player(
            player.player_id,
            player.username,
        )
    else:  # alltime
        role_data, generated_at = await scoring_service.get_alltime_leaderboard_for_player(
            player.player_id,
            player.username,
        )

    # Build leaderboard for each role using dictionary comprehension
    leader_lists = {
        role: [WeeklyLeaderboardEntry(**entry) for entry in role_data.get(role, [])]
        for role in LEADERBOARD_ROLES
    }

    # Build gross earnings leaderboard
    gross_earnings_leaders = [
        GrossEarningsLeaderboardEntry(**entry)
        for entry in role_data.get("gross_earnings", [])
    ]

    return LeaderboardResponse(
        prompt_leaderboard=RoleLeaderboard(role="prompt", leaders=leader_lists["prompt"]),
        copy_leaderboard=RoleLeaderboard(role="copy", leaders=leader_lists["copy"]),
        voter_leaderboard=RoleLeaderboard(role="voter", leaders=leader_lists["voter"]),
        gross_earnings_leaderboard=GrossEarningsLeaderboard(leaders=gross_earnings_leaders),
        generated_at=generated_at or datetime.now(UTC),
    )


# Create and expose the router instance
qf_player_router = QFPlayerRouter()
router = qf_player_router.router
