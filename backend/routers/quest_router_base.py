"""Base quest router with common quest management endpoints."""
import logging
from abc import ABC, abstractmethod
from typing import Type, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.schemas.quest import QuestResponse, QuestListResponse, ClaimQuestRewardResponse
from backend.services import TransactionService
from backend.utils.model_registry import GameType
from backend.models.quest_base import QuestBase

logger = logging.getLogger(__name__)


class QuestRouterBase(ABC):
    """Base class for quest routers with common CRUD endpoints."""

    def __init__(self, game_type: GameType):
        """Initialize the base quest router.
        
        Args:
            game_type: The game type this router serves
        """
        self.game_type = game_type
        self.router = APIRouter()
        self._setup_common_routes()

    @property
    @abstractmethod
    def quest_service_class(self) -> Type[Any]:
        """Return the quest service class for this game."""
        pass

    @property
    @abstractmethod
    def quest_configs(self) -> dict:
        """Return the quest configuration mapping for this game."""
        pass

    def _setup_common_routes(self):
        """Set up all common quest management routes."""
        
        @self.router.get("", response_model=QuestListResponse)
        async def get_player_quests(player=Depends(get_current_player), db: AsyncSession = Depends(get_db)):
            """Get all quests for the current player."""
            return await self._get_player_quests(player, db)

        @self.router.get("/active", response_model=List[QuestResponse])
        async def get_active_quests(
            player=Depends(get_current_player),
            db: AsyncSession = Depends(get_db),
        ):
            """Get only active quests for the current player."""
            return await self._get_active_quests(player, db)

        @self.router.get("/claimable", response_model=List[QuestResponse])
        async def get_claimable_quests(
            player=Depends(get_current_player),
            db: AsyncSession = Depends(get_db),
        ):
            """Get completed but unclaimed quests for the current player."""
            return await self._get_claimable_quests(player, db)

        @self.router.get("/{quest_id}", response_model=QuestResponse)
        async def get_quest(
            quest_id: UUID,
            player=Depends(get_current_player),
            db: AsyncSession = Depends(get_db),
        ):
            """Get a single quest by ID."""
            return await self._get_quest(quest_id, player, db)

        @self.router.post("/{quest_id}/claim", response_model=ClaimQuestRewardResponse)
        async def claim_quest_reward(
            quest_id: UUID,
            player=Depends(get_current_player),
            db: AsyncSession = Depends(get_db),
        ):
            """Claim a completed quest reward."""
            return await self._claim_quest_reward(quest_id, player, db)

    async def _get_player_quests(self, player: Any, db: AsyncSession) -> QuestListResponse:
        """Get all quests for the current player."""
        quest_service = self.quest_service_class(db)
        
        quests = await quest_service.get_player_quests(player.player_id)

        # Map to responses
        quest_responses = [self._map_quest_to_response(q) for q in quests]

        # Count by status
        active_count = sum(1 for q in quests if q.status == "active")
        completed_count = sum(1 for q in quests if q.status == "completed")
        claimed_count = sum(1 for q in quests if q.status == "claimed")

        return QuestListResponse(
            quests=quest_responses,
            total_count=len(quests),
            active_count=active_count,
            completed_count=completed_count,
            claimed_count=claimed_count,
            claimable_count=completed_count,  # Completed but not claimed
        )

    async def _get_active_quests(self, player: Any, db: AsyncSession) -> List[QuestResponse]:
        """Get only active quests for the current player."""
        quest_service = self.quest_service_class(db)
        
        quests = await quest_service.get_player_quests(player.player_id, status="active")
        
        return [self._map_quest_to_response(q) for q in quests]

    async def _get_claimable_quests(self, player: Any, db: AsyncSession) -> List[QuestResponse]:
        """Get completed but unclaimed quests for the current player."""
        quest_service = self.quest_service_class(db)
        
        quests = await quest_service.get_player_quests(player.player_id, status="completed")
        
        return [self._map_quest_to_response(q) for q in quests]

    async def _get_quest(self, quest_id: UUID, player: Any, db: AsyncSession) -> QuestResponse:
        """Get a single quest by ID."""
        quest_service = self.quest_service_class(db)
        
        quest = await quest_service.get_quest_by_id(quest_id)

        if not quest:
            raise HTTPException(status_code=404, detail="Quest not found")

        if quest.player_id != player.player_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this quest")

        return self._map_quest_to_response(quest)

    async def _claim_quest_reward(self, quest_id: UUID, player: Any, db: AsyncSession) -> ClaimQuestRewardResponse:
        """Claim a completed quest reward."""
        quest_service = self.quest_service_class(db)
        transaction_service = TransactionService(db)

        try:
            result = await quest_service.claim_quest_reward(
                quest_id=quest_id,
                player_id=player.player_id,
                transaction_service=transaction_service,
            )
            return result
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail=str(e))
            elif "not completed" in error_msg.lower():
                raise HTTPException(status_code=400, detail=str(e))
            elif "already claimed" in error_msg.lower():
                raise HTTPException(status_code=409, detail=str(e))
            else:
                raise HTTPException(status_code=400, detail=str(e))

    def _map_quest_to_response(self, quest: QuestBase) -> QuestResponse:
        """Map a Quest model to QuestResponse schema."""
        # Convert string quest_type from database to enum for lookup
        try:
            quest_type_enum = self._string_to_quest_type(quest.quest_type)
            config = self.quest_configs.get(quest_type_enum)
        except (ValueError, KeyError):
            # Handle unknown quest types
            config = None

        if not config:
            # Fallback for unknown quest types
            config = {
                "name": quest.quest_type,
                "description": "",
                "category": "milestone",
                "target": quest.progress.get("target", 0),
            }

        # Extract progress values
        progress = quest.progress
        target = progress.get("target", config.get("target", 0))

        # Calculate current progress based on quest type
        if "current_streak" in progress:
            current = progress.get("current_streak", 0)
        elif "rounds_completed" in progress:
            current = progress.get("rounds_completed", 0)
        elif "consecutive_days" in progress:
            current = progress.get("consecutive_days", 0)
        elif "current" in progress:
            current = progress.get("current", 0)
        # Handle balanced_player quest with dict target
        elif "votes" in progress and isinstance(target, dict):
            # For balanced_player, use votes as the primary progress indicator
            current = progress.get("votes", 0)
            target = target.get("votes", 10)
        else:
            current = 0

        # Ensure target is an integer (handle dict edge cases)
        if isinstance(target, dict):
            # Fallback: use the "votes" target or first value if dict
            target = target.get("votes", list(target.values())[0] if target else 0)

        # Calculate percentage
        percentage = (current / target * 100) if target > 0 else 0

        # Get category value - handle both enum and string
        category_value = config.get("category", "milestone")
        if hasattr(category_value, "value"):
            category_value = category_value.value

        return QuestResponse(
            quest_id=quest.quest_id,
            quest_type=quest.quest_type,
            name=config.get("name", quest.quest_type),
            description=config.get("description", ""),
            status=quest.status,
            progress=progress,
            reward_amount=quest.reward_amount,
            category=category_value,
            created_at=quest.created_at,
            completed_at=quest.completed_at,
            claimed_at=quest.claimed_at,
            progress_percentage=min(percentage, 100),
            progress_current=current,
            progress_target=target,
        )

    @abstractmethod
    def _string_to_quest_type(self, quest_type_str: str) -> Any:
        """Convert a quest type string back to the appropriate enum for config lookup."""
        pass
