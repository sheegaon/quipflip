"""ThinkLink (TL) player API router."""
import logging
from fastapi import APIRouter, Depends, Header, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.schemas.base import BaseSchema
from backend.services import GameType
from backend.config import get_settings
from datetime import datetime, UTC
from uuid import UUID
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


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


class BalanceResponse(BaseSchema):
    """Player balance response."""
    tl_wallet: int
    tl_vault: int
    total_balance: int  # wallet + vault


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
):
    """Get player dashboard with current balance and progress."""
    return DashboardResponse(
        player_id=player.player_id,
        username=player.username,
        tl_wallet=player.tl_wallet,
        tl_vault=player.tl_vault,
        tl_tutorial_completed=player.tl_tutorial_completed,
        tl_tutorial_progress=player.tl_tutorial_progress,
        created_at=player.created_at,
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
):
    """Get player balance (wallet + vault)."""
    return BalanceResponse(
        tl_wallet=player.tl_wallet,
        tl_vault=player.tl_vault,
        total_balance=player.tl_wallet + player.tl_vault,
    )


# ========================================================================
# Tutorial Endpoints
# ========================================================================

class TutorialStatusResponse(BaseSchema):
    """Tutorial status response."""
    tutorial_completed: bool
    tutorial_progress: str


class TutorialProgressRequest(BaseSchema):
    """Tutorial progress update request."""
    progress: str


@router.get("/tutorial/status", response_model=TutorialStatusResponse)
async def get_tutorial_status(
    player: Player = Depends(get_tl_player),
):
    """Get player tutorial status."""
    return TutorialStatusResponse(
        tutorial_completed=player.tl_tutorial_completed,
        tutorial_progress=player.tl_tutorial_progress,
    )


@router.post("/tutorial/progress", response_model=TutorialStatusResponse)
async def update_tutorial_progress(
    request_body: TutorialProgressRequest = Body(...),
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
):
    """Update player tutorial progress."""
    # Update player tutorial progress
    stmt = (
        update(Player)
        .where(Player.player_id == player.player_id)
        .values(
            tl_tutorial_progress=request_body.progress,
            tl_tutorial_completed=(request_body.progress == 'completed'),
        )
    )
    await db.execute(stmt)
    await db.commit()

    return TutorialStatusResponse(
        tutorial_completed=(request_body.progress == 'completed'),
        tutorial_progress=request_body.progress,
    )


@router.post("/tutorial/reset", response_model=TutorialStatusResponse)
async def reset_tutorial(
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
):
    """Reset tutorial progress to allow replaying."""
    stmt = (
        update(Player)
        .where(Player.player_id == player.player_id)
        .values(
            tl_tutorial_progress='not_started',
            tl_tutorial_completed=False,
        )
    )
    await db.execute(stmt)
    await db.commit()

    return TutorialStatusResponse(
        tutorial_completed=False,
        tutorial_progress='not_started',
    )
