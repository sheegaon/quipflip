"""ThinkLink (TL) API routers."""
from fastapi import APIRouter
from backend.routers.tl import rounds, player, game, admin

router = APIRouter(prefix="/tl", tags=["tl"])

# TL-specific routers
router.include_router(player.router, prefix="/player", tags=["tl-player"])
router.include_router(rounds.router, prefix="/rounds", tags=["tl-rounds"])
router.include_router(game.router, prefix="/game", tags=["tl-game"])
router.include_router(admin.router, prefix="/admin", tags=["tl-admin"])
