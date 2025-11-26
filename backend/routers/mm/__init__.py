"""Meme Mint (MM) API routers."""

from fastapi import APIRouter

from backend.routers.mm import player, rounds, images
from backend.routers import health, auth

router = APIRouter(prefix="/mm", tags=["mm"])

# Shared routers
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])

# MM-specific routers
router.include_router(player.router, prefix="/player", tags=["mm-player"])
router.include_router(rounds.router, prefix="/rounds", tags=["mm-rounds"])
router.include_router(images.router, tags=["mm-images"])
