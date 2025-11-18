"""Initial Reaction (IR) API routers."""
from fastapi import APIRouter

from backend.routers.ir import game, leaderboards, players, stats

router = APIRouter(prefix="/ir", tags=["ir"])

router.include_router(players.router, prefix="/players", tags=["ir-player"])
router.include_router(game.router, prefix="/game", tags=["ir-game"])
router.include_router(stats.router, prefix="/stats", tags=["ir-stats"])
router.include_router(leaderboards.router, prefix="/leaderboard", tags=["ir-leaderboard"])
