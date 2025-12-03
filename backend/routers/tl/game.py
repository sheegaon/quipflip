"""ThinkLink (TL) game API router - prompts and game state."""
import logging
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.schemas.base import BaseSchema
from backend.services import GameType
from backend.services.tl.prompt_service import PromptService
from backend.services.tl.matching_service import MatchingService
from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_tl_player(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> Player:
    """Get current player authenticated for ThinkLink."""
    return await get_current_player(
        request=request,
        game_type=GameType.TL,
        authorization=authorization,
        db=db,
    )


class PromptPreviewResponse(BaseSchema):
    """Preview a random prompt (for browsing/curiosity)."""
    prompt_text: str
    hint: str = "What answers would you guess?"


@router.get("/prompts/preview", response_model=PromptPreviewResponse)
async def preview_prompt(
    db: AsyncSession = Depends(get_db),
):
    """Get a random prompt preview without starting a round.

    Useful for players to browse prompts without committing coins.
    """
    try:
        # Initialize services
        matching_service = MatchingService()
        prompt_service = PromptService(matching_service)

        # Get random prompt
        prompt = await prompt_service.get_random_active_prompt(db)
        if not prompt:
            return PromptPreviewResponse(prompt_text="No prompts available")

        return PromptPreviewResponse(
            prompt_text=prompt.text,
            hint="What answers would you guess?",
        )

    except Exception as e:
        logger.error(f"❌ Error fetching prompt preview: {e}")
        return PromptPreviewResponse(prompt_text="Error loading prompt")
