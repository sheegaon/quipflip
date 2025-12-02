"""Quipflip (QF) API routers."""
from fastapi import APIRouter

from backend.routers.qf import (
    admin,
    feedback,
    party,
    phrasesets,
    player,
    prompt_feedback,
    quests,
    rounds,
)
from backend.routers import health, auth

router = APIRouter(prefix="/qf", tags=["qf"])

# Shared routers
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])

# QF-specific routers
router.include_router(player.router, prefix="/player", tags=["qf-player"])
router.include_router(rounds.router, prefix="/rounds", tags=["qf-rounds"])
router.include_router(prompt_feedback.router, prefix="/rounds", tags=["prompt_feedback"])
router.include_router(phrasesets.router, prefix="/phrasesets", tags=["phrasesets"])
router.include_router(quests.router, prefix="/quests", tags=["quests"])
router.include_router(admin.router, tags=["admin"])
router.include_router(feedback.router, tags=["feedback"])
router.include_router(party.router, prefix="/party", tags=["party"])
