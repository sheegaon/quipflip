"""Initial Reaction (IR) API routers."""
from fastapi import APIRouter

from backend.routers.ir import auth, game, leaderboards, players, stats

router = APIRouter(prefix="/ir", tags=["ir"])

router.include_router(auth.router, tags=["ir-auth"])
router.include_router(players.router, tags=["ir-player"])
router.include_router(game.router, tags=["ir-game"])
router.include_router(stats.router, tags=["ir-stats"])
router.include_router(leaderboards.router, tags=["ir-leaderboard"])
