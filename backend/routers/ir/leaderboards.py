"""Leaderboard endpoints for Initial Reaction (IR)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.ir.ir_player import IRPlayer
from backend.routers.ir.dependencies import get_ir_current_player
from backend.routers.ir.schemas import LeaderboardEntry
from backend.services.ir.ir_statistics_service import IRStatisticsService

router = APIRouter()


@router.get("/leaderboards/creators", response_model=list[LeaderboardEntry])
async def get_creator_leaderboard(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _: IRPlayer = Depends(get_ir_current_player),
) -> list[LeaderboardEntry]:
    """Get creator leaderboard ranked by vault contributions."""

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
