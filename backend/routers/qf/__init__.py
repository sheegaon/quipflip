"""Quipflip (QF) API routers."""
from fastapi import APIRouter

from backend.routers.qf import (
    admin,
    auth,
    feedback,
    health,
    notifications,
    online_users,
    phrasesets,
    player,
    prompt_feedback,
    quests,
    rounds,
)

router = APIRouter(prefix="/qf", tags=["qf"])

router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(player.router, prefix="/player", tags=["player"])
router.include_router(rounds.router, prefix="/rounds", tags=["rounds"])
router.include_router(prompt_feedback.router, prefix="/rounds", tags=["prompt_feedback"])
router.include_router(phrasesets.router, prefix="/phrasesets", tags=["phrasesets"])
router.include_router(quests.router, prefix="/quests", tags=["quests"])
router.include_router(admin.router, tags=["admin"])
router.include_router(feedback.router, tags=["feedback"])
router.include_router(online_users.router, prefix="/users", tags=["online_users"])
router.include_router(notifications.router, tags=["notifications"])
