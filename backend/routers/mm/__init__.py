"""Meme Mint API routers."""

from fastapi import APIRouter

from backend.routers.mm import player, game

router = APIRouter(prefix="/mm", tags=["mm"])

router.include_router(player.router, prefix="/player", tags=["mm-player"])
router.include_router(game.router, prefix="/rounds", tags=["mm-game"])

