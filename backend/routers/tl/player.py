"""ThinkLink (TL) player API router."""
import logging
from typing import Type, Any

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.models.tl.player_data import TLPlayerData
from backend.schemas.base import BaseSchema
from backend.services import GameType, TLPlayerService, TLCleanupService
from backend.config import get_settings
from backend.routers.player_router_base import PlayerRouterBase
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

logger = logging.getLogger(__name__)
settings = get_settings()


class TLPlayerRouter(PlayerRouterBase):
    """ThinkLink player router with game-specific endpoints."""

    def __init__(self):
        """Initialize the TL player router."""
        super().__init__(GameType.TL)
        self._add_tl_specific_routes()

    @property
    def player_service_class(self) -> Type[Any]:
        """Return the TL player service class."""
        return TLPlayerService

    @property
    def cleanup_service_class(self) -> Type[Any]:
        """Return the TL cleanup service class."""
        return TLCleanupService

    async def get_balance(self, player: Player, db: AsyncSession) -> "PlayerBalance":
        """Get player balance (wallet + vault)."""
        from backend.schemas.player import PlayerBalance
        from backend.services.player_service import PlayerService

        # Ensure player has TL-specific data, creating it if needed
        player_service = PlayerService(db)
        player_data = await player_service.ensure_player_data(player, GameType.TL)

        tl_wallet = player_data.wallet if player_data else 0
        tl_vault = player_data.vault if player_data else 0

        return PlayerBalance(
            player_id=player.player_id,
            username=player.username,
            email=player.email,
            wallet=tl_wallet,
            vault=tl_vault,
            starting_balance=settings.tl_starting_balance,
            daily_bonus_available=False,  # TODO: Implement daily bonuses for TL
            daily_bonus_amount=0,
            last_login_date=player.last_login_date,
            created_at=player.created_at,
            outstanding_prompts=0,
            is_guest=player.is_guest,
            is_admin=player.is_admin,
            locked_until=player.locked_until,
            flag_dismissal_streak=0,
        )

    def _add_tl_specific_routes(self):
        """Add ThinkLink-specific routes beyond the common auth routes."""

        async def get_tl_player(
            request: Request,
            authorization: str | None = Header(default=None, alias="Authorization"),
            db: AsyncSession = Depends(get_db),
        ) -> Player:
            """Get current player authenticated for ThinkLink."""
            return await get_current_player(
                request=request,
                game_type=GameType.TL,
                authorization=authorization,
                db=db,
            )

        class DashboardResponse(BaseSchema):
            """ThinkLink dashboard response with player state."""
            player_id: UUID
            username: str
            tl_wallet: int
            tl_vault: int
            tl_tutorial_completed: bool
            tl_tutorial_progress: str
            created_at: datetime
            is_guest: bool

        class BalanceResponse(BaseSchema):
            """Player balance response."""
            tl_wallet: int
            tl_vault: int
            total_balance: int  # wallet + vault

        class TutorialStatusResponse(BaseSchema):
            """Tutorial status response."""
            tutorial_completed: bool
            tutorial_progress: str

        class TutorialProgressRequest(BaseSchema):
            """Tutorial progress update request."""
            progress: str

        @self.router.get("/dashboard", response_model=DashboardResponse)
        async def get_dashboard(
            player: Player = Depends(get_tl_player),
            db: AsyncSession = Depends(get_db),
        ):
            """Get player dashboard with current balance and progress."""
            from backend.services.player_service import PlayerService

            # Ensure player has TL-specific data, creating it if needed
            player_service = PlayerService(db)
            player_data = await player_service.ensure_player_data(player, GameType.TL)

            tl_wallet = player_data.wallet if player_data else 0
            tl_vault = player_data.vault if player_data else 0
            tl_tutorial_completed = player_data.tutorial_completed if player_data else False
            tl_tutorial_progress = player_data.tutorial_progress if player_data else 'not_started'
            return DashboardResponse(
                player_id=player.player_id,
                username=player.username,
                tl_wallet=tl_wallet,
                tl_vault=tl_vault,
                tl_tutorial_completed=tl_tutorial_completed,
                tl_tutorial_progress=tl_tutorial_progress,
                created_at=player.created_at,
                is_guest=player.is_guest,
            )

        @self.router.get("/tutorial/status", response_model=TutorialStatusResponse)
        async def get_tutorial_status(
            player: Player = Depends(get_tl_player),
        ):
            """Get player tutorial status."""
            tl_tutorial_completed = player.tl_player_data.tutorial_completed if player.tl_player_data else False
            tl_tutorial_progress = player.tl_player_data.tutorial_progress if player.tl_player_data else 'not_started'
            return TutorialStatusResponse(
                tutorial_completed=tl_tutorial_completed,
                tutorial_progress=tl_tutorial_progress,
            )

        @self.router.post("/tutorial/progress", response_model=TutorialStatusResponse)
        async def update_tutorial_progress(
            request_body: TutorialProgressRequest,
            player: Player = Depends(get_tl_player),
            db: AsyncSession = Depends(get_db),
        ):
            """Update player tutorial progress."""
            from backend.services.player_service import PlayerService

            player_service = PlayerService(db)
            await player_service.ensure_player_data(player, GameType.TL)

            stmt = (
                update(TLPlayerData)
                .where(TLPlayerData.player_id == player.player_id)
                .values(
                    tutorial_progress=request_body.progress,
                    tutorial_completed=(request_body.progress == 'completed'),
                )
            )
            await db.execute(stmt)
            await db.commit()

            return TutorialStatusResponse(
                tutorial_completed=(request_body.progress == 'completed'),
                tutorial_progress=request_body.progress,
            )

        @self.router.post("/tutorial/reset", response_model=TutorialStatusResponse)
        async def reset_tutorial(
            player: Player = Depends(get_tl_player),
            db: AsyncSession = Depends(get_db),
        ):
            """Reset tutorial progress to allow replaying."""
            from backend.services.player_service import PlayerService

            player_service = PlayerService(db)
            await player_service.ensure_player_data(player, GameType.TL)

            stmt = (
                update(TLPlayerData)
                .where(TLPlayerData.player_id == player.player_id)
                .values(
                    tutorial_progress='not_started',
                    tutorial_completed=False,
                )
            )
            await db.execute(stmt)
            await db.commit()

            return TutorialStatusResponse(
                tutorial_completed=False,
                tutorial_progress='not_started',
            )


# Create and export the router
tl_player_router = TLPlayerRouter()
router = tl_player_router.router
