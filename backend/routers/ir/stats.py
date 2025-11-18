"""Statistics endpoints for Initial Reaction (IR)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.ir.player import IRPlayer
from backend.routers.ir.dependencies import get_current_player
from backend.routers.ir.schemas import PlayerStatsResponse
from backend.services.ir.statistics_service import IRStatisticsService

router = APIRouter()


@router.get("/player/statistics", response_model=PlayerStatsResponse)
async def get_player_stats(
    player: IRPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> PlayerStatsResponse:
    """Get player statistics."""

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
