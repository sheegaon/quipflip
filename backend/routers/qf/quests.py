"""Quest API router for QuipFlip."""
from fastapi import APIRouter
import logging
from typing import Type, Any

from backend.models.qf.quest import QuestType
from backend.routers.quest_router_base import QuestRouterBase
from backend.services.qf.quest_service import QuestService, QUEST_CONFIGS
from backend.utils.model_registry import GameType

logger = logging.getLogger(__name__)

router = APIRouter()


class QFQuestRouter(QuestRouterBase):
    """Quipflip quest router with game-specific functionality."""

    def __init__(self):
        """Initialize the QF quest router."""
        super().__init__(GameType.QF)

    @property
    def quest_service_class(self) -> Type[QuestService]:
        """Return the QF quest service class."""
        return QuestService

    @property
    def quest_configs(self) -> dict:
        """Return the quest configuration mapping for this game."""
        return QUEST_CONFIGS

    def _string_to_quest_type(self, quest_type_str: str) -> QuestType:
        """Convert a quest type string back to the QuestType enum."""
        return QuestType(quest_type_str)
