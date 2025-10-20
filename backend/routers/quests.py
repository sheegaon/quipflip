"""Quest API router."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.models.quest import Quest
from backend.schemas.quest import (
    QuestResponse,
    QuestListResponse,
    ClaimQuestRewardResponse,
)
from backend.services.quest_service import QuestService, QUEST_CONFIGS
from backend.services.transaction_service import TransactionService
from backend.models.quest import QuestType

logger = logging.getLogger(__name__)

router = APIRouter()


def _map_quest_to_response(quest: Quest) -> QuestResponse:
    """Map a Quest model to QuestResponse schema."""
    # Convert string quest_type from database to QuestType enum for lookup
    try:
        quest_type_enum = QuestType(quest.quest_type)
        config = QUEST_CONFIGS.get(quest_type_enum)
    except ValueError:
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
    target = progress.get("target", config["target"])

    # Calculate current progress based on quest type
    if "current_streak" in progress:
        current = progress.get("current_streak", 0)
    elif "rounds_completed" in progress:
        current = progress.get("rounds_completed", 0)
    elif "consecutive_days" in progress:
        current = progress.get("consecutive_days", 0)
    elif "current" in progress:
        current = progress.get("current", 0)
    else:
        current = 0

    # Calculate percentage
    percentage = (current / target * 100) if target > 0 else 0

    # Get category value - handle both enum and string
    category_value = config["category"].value if hasattr(config["category"], "value") else config["category"]

    return QuestResponse(
        quest_id=quest.quest_id,
        quest_type=quest.quest_type,
        name=config["name"],
        description=config["description"],
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


@router.get("", response_model=QuestListResponse)
async def get_player_quests(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get all quests for the current player."""
    quest_service = QuestService(db)

    quests = await quest_service.get_player_quests(player.player_id)

    # Map to responses
    quest_responses = [_map_quest_to_response(q) for q in quests]

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


@router.get("/active", response_model=list[QuestResponse])
async def get_active_quests(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get only active quests for the current player."""
    quest_service = QuestService(db)

    quests = await quest_service.get_player_quests(player.player_id, status="active")

    return [_map_quest_to_response(q) for q in quests]


@router.get("/claimable", response_model=list[QuestResponse])
async def get_claimable_quests(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get completed but unclaimed quests for the current player."""
    quest_service = QuestService(db)

    quests = await quest_service.get_player_quests(player.player_id, status="completed")

    return [_map_quest_to_response(q) for q in quests]


@router.get("/{quest_id}", response_model=QuestResponse)
async def get_quest(
    quest_id: UUID,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get a single quest by ID."""
    quest_service = QuestService(db)

    quest = await quest_service.get_quest_by_id(quest_id)

    if not quest:
        raise HTTPException(status_code=404, detail="Quest not found")

    if quest.player_id != player.player_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this quest")

    return _map_quest_to_response(quest)


@router.post("/{quest_id}/claim", response_model=ClaimQuestRewardResponse)
async def claim_quest_reward(
    quest_id: UUID,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Claim a completed quest reward."""
    quest_service = QuestService(db)
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
