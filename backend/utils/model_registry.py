"""Central registry for mapping GameType to concrete SQLAlchemy models.

This utility provides a centralized way to get the correct concrete model
for a given game type, ensuring abstract base models are never used directly
in database operations.
"""
from typing import Type, TypeVar
from enum import Enum

T = TypeVar('T')


class GameType(Enum):
    """Enum for different game types."""
    QF = "qf"
    IR = "ir"
    MM = "mm"


class AIPlayerType(Enum):
    """Enum for different AI player types."""
    QF_QUIP = "qf_quip"
    QF_IMPOSTOR = "qf_impostor"
    QF_VOTER = "qf_voter"
    QF_PARTY = "qf_party"
    IR_PLAYER = "ir_player"


def get_player_model(game_type: GameType) -> Type:
    """Get the concrete Player model for a game type."""
    if game_type == GameType.QF:
        from backend.models.qf.player import QFPlayer
        return QFPlayer
    elif game_type == GameType.IR:
        from backend.models.ir.player import IRPlayer
        return IRPlayer
    elif game_type == GameType.MM:
        from backend.models.mm.player import MMPlayer
        return MMPlayer
    else:
        raise ValueError(f"Unsupported game type: {game_type}")


def get_refresh_token_model(game_type: GameType) -> Type:
    """Get the concrete RefreshToken model for a game type."""
    if game_type == GameType.QF:
        from backend.models.qf.refresh_token import QFRefreshToken
        return QFRefreshToken
    elif game_type == GameType.IR:
        from backend.models.ir.refresh_token import IRRefreshToken
        return IRRefreshToken
    elif game_type == GameType.MM:
        from backend.models.mm.refresh_token import MMRefreshToken
        return MMRefreshToken
    else:
        raise ValueError(f"Unsupported game type: {game_type}")


def get_transaction_model(game_type: GameType) -> Type:
    """Get the concrete Transaction model for a game type."""
    if game_type == GameType.QF:
        from backend.models.qf.transaction import QFTransaction
        return QFTransaction
    elif game_type == GameType.IR:
        from backend.models.ir.transaction import IRTransaction
        return IRTransaction
    elif game_type == GameType.MM:
        from backend.models.mm.transaction import MMTransaction
        return MMTransaction
    else:
        raise ValueError(f"Unsupported game type: {game_type}")


def get_player_data_model(game_type: GameType) -> Type:
    """Get the concrete PlayerData model for a game type."""
    if game_type == GameType.QF:
        from backend.models.qf.player_data import QFPlayerData
        return QFPlayerData
    elif game_type == GameType.IR:
        from backend.models.ir.player_data import IRPlayerData
        return IRPlayerData
    elif game_type == GameType.MM:
        from backend.models.mm.player_data import MMPlayerData
        return MMPlayerData
    else:
        raise ValueError(f"Unsupported game type: {game_type}")


def get_user_activity_model(game_type: GameType) -> Type:
    """Get the concrete UserActivity model for a game type."""
    if game_type == GameType.QF:
        from backend.models.qf.user_activity import QFUserActivity
        return QFUserActivity
    elif game_type == GameType.IR:
        from backend.models.ir.user_activity import IRUserActivity
        return IRUserActivity
    else:
        raise ValueError(f"Unsupported game type: {game_type}")


def get_system_config_model(game_type: GameType) -> Type:
    """Get the concrete SystemConfig model for a game type."""
    if game_type == GameType.QF:
        from backend.models.qf.system_config import QFSystemConfig
        return QFSystemConfig
    elif game_type == GameType.IR:
        from backend.models.ir.system_config import IRSystemConfig
        return IRSystemConfig
    elif game_type == GameType.MM:
        from backend.models.mm.system_config import MMSystemConfig
        return MMSystemConfig
    else:
        raise ValueError(f"Unsupported game type: {game_type}")
