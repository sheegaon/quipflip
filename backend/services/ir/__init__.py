"""Initial Reaction (IR) game services."""

from backend.services.ir.player_service import IRPlayerService, PlayerError

__all__ = [
    "IRPlayerService",
    "PlayerError",
]
