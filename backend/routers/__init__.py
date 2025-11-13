"""API routers."""
from backend.routers import health, player, rounds, phrasesets, prompt_feedback, auth, quests, admin, feedback, online_users, notifications

__all__ = [
    "health",
    "player",
    "rounds",
    "phrasesets",
    "prompt_feedback",
    "auth",
    "quests",
    "admin",
    "feedback",
    "online_users",
    "notifications",
]
