"""Player API router for Meme Mint."""

import logging

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.routers.player_router_base import PlayerRouterBase
from backend.schemas.player import ClaimDailyBonusResponse, PlayerBalance
from backend.services import GameType
from backend.services.mm import (
    MMDailyBonusError,
    MMDailyBonusService,
    MMPlayerDailyStateService,
    MMPlayerService,
    MMSystemConfigService,
    MMCleanupService,
)
from backend.utils import ensure_utc
from backend.schemas.mm_player import MMDailyStateResponse, MMConfigResponse, MMDashboardDataResponse
from backend.schemas.mm_round import RoundAvailability

logger = logging.getLogger(__name__)
settings = get_settings()


async def _get_player_balance(player, db: AsyncSession) -> PlayerBalance:
    """Build a PlayerBalance response for Meme Mint."""

    config_service = MMSystemConfigService(db)
    daily_bonus_service = MMDailyBonusService(db, config_service)
    starting_balance = await config_service.get_config_value(
        "mm_starting_wallet_override", default=settings.mm_starting_wallet
    )
    daily_bonus_amount = await config_service.get_config_value(
        "mm_daily_bonus_amount", default=settings.daily_bonus_amount
    )
    daily_bonus_available = await daily_bonus_service.is_bonus_available(player.player_id)

    return PlayerBalance(
        player_id=player.player_id,
        username=player.username,
        email=player.email,
        wallet=player.wallet,
        vault=player.vault,
        starting_balance=starting_balance,
        daily_bonus_available=daily_bonus_available,
        daily_bonus_amount=daily_bonus_amount,
        last_login_date=ensure_utc(player.last_login_date),
        created_at=ensure_utc(player.created_at),
        outstanding_prompts=0,
        is_guest=player.is_guest,
        is_admin=getattr(player, "is_admin", False),
        locked_until=getattr(player, "locked_until", None),
        flag_dismissal_streak=getattr(player, "flag_dismissal_streak", 0),
    )


class MMPlayerRouter(PlayerRouterBase):
    """Meme Mint player router built on shared authentication base."""

    def __init__(self):
        super().__init__(GameType.MM)
        self._add_mm_routes()

    @property
    def player_service_class(self):
        return MMPlayerService

    @property
    def cleanup_service_class(self):
        return MMCleanupService

    async def get_balance(self, player, db: AsyncSession) -> PlayerBalance:
        return await _get_player_balance(player, db)

    async def _claim_daily_bonus(
        self, player, db: AsyncSession
    ) -> ClaimDailyBonusResponse:
        """Use Meme Mint's bonus service to claim and record the reward."""

        bonus_service = MMDailyBonusService(db)
        try:
            result = await bonus_service.claim_bonus(player.player_id)
            await db.refresh(player)
            return ClaimDailyBonusResponse(
                success=True,
                amount=result["amount"],
                new_wallet=player.wallet,
                new_vault=player.vault,
            )
        except MMDailyBonusError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _add_mm_routes(self):
        """Add Meme Mint specific routes such as free-caption quota and config."""

        player_dependency = self._current_player_dependency()

        @self.router.get("/daily-state", response_model=MMDailyStateResponse)
        async def get_daily_state(
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            config_service = MMSystemConfigService(db)
            daily_state_service = MMPlayerDailyStateService(db, config_service)
            free_captions_per_day = await config_service.get_config_value(
                "mm_free_captions_per_day", default=0
            )
            remaining = await daily_state_service.get_remaining_free_captions(
                player.player_id
            )
            return MMDailyStateResponse(
                free_captions_remaining=remaining,
                free_captions_per_day=free_captions_per_day,
            )

        @self.router.get("/config", response_model=MMConfigResponse)
        async def get_client_config(db: AsyncSession = Depends(get_db)):
            config_service = MMSystemConfigService(db)
            return MMConfigResponse(
                round_entry_cost=await config_service.get_config_value(
                    "mm_round_entry_cost", default=5
                ),
                captions_per_round=await config_service.get_config_value(
                    "mm_captions_per_round", default=5
                ),
                caption_submission_cost=await config_service.get_config_value(
                    "mm_caption_submission_cost", default=10
                ),
                free_captions_per_day=await config_service.get_config_value(
                    "mm_free_captions_per_day", default=0
                ),
                house_rake_vault_pct=await config_service.get_config_value(
                    "mm_house_rake_vault_pct", default=0.3
                ),
                daily_bonus_amount=await config_service.get_config_value(
                    "mm_daily_bonus_amount", default=settings.daily_bonus_amount
                ),
            )

        @self.router.get("/dashboard", response_model=MMDashboardDataResponse)
        async def get_dashboard_data(
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get all dashboard data in a single batched request for optimal performance."""
            return await _get_dashboard_data(player, db)


async def _get_dashboard_data(player, db: AsyncSession) -> MMDashboardDataResponse:
    """Get all dashboard data in a single batched request for optimal performance."""
    from backend.utils.cache import dashboard_cache

    try:
        # Check cache first
        cache_key = f"mm_dashboard:{player.player_id}"
        cached_data = dashboard_cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached MM dashboard data for player {player.player_id}")
            return cached_data

        logger.info(f"Generating fresh MM dashboard data for player {player.player_id}")

        # Get player balance
        player_balance = await _get_player_balance(player, db)

        # Get round availability
        from backend.services.mm import MMGameService

        game_service = MMGameService(db)
        config_service = MMSystemConfigService(db)
        daily_state_service = MMPlayerDailyStateService(db, config_service)
        daily_bonus_service = MMDailyBonusService(db, config_service)

        # Get round availability info
        round_entry_cost = await config_service.get_config_value("mm_round_entry_cost", default=5)
        caption_submission_cost = await config_service.get_config_value("mm_caption_submission_cost", default=10)
        free_captions_remaining = await daily_state_service.get_remaining_free_captions(player.player_id)
        daily_bonus_available = await daily_bonus_service.is_bonus_available(player.player_id)

        # Check if player can start rounds
        can_vote = player.wallet >= round_entry_cost
        can_submit_caption = (
            free_captions_remaining > 0 or player.wallet >= caption_submission_cost
        )

        round_availability = RoundAvailability(
            can_vote=can_vote,
            can_submit_caption=can_submit_caption,
            current_round_id=None,  # MM doesn't track active rounds on player
            round_entry_cost=round_entry_cost,
            caption_submission_cost=caption_submission_cost,
            free_captions_remaining=free_captions_remaining,
            daily_bonus_available=daily_bonus_available,
        )

        # Current rounds - MM doesn't track active rounds on player model like QF does
        # Players can start new rounds anytime if they have funds
        current_vote_round = None
        current_caption_round = None

        dashboard_data = MMDashboardDataResponse(
            player=player_balance,
            round_availability=round_availability,
            current_vote_round=current_vote_round,
            current_caption_round=current_caption_round,
        )

        # Cache the response for 10 seconds (shorter TTL for dashboard since it changes frequently)
        dashboard_cache.set(cache_key, dashboard_data, ttl=10.0)

        return dashboard_data
    except HTTPException:
        # Re-raise HTTPException to pass through
        raise
    except Exception as e:
        logger.error(f"Unexpected error in MM dashboard endpoint for {player.player_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load dashboard")


mm_player_router = MMPlayerRouter()
router = mm_player_router.router

