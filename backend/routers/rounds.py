"""Rounds API router."""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.models.round import Round
from backend.schemas.round import (
    StartPromptRoundResponse,
    StartCopyRoundResponse,
    StartVoteRoundResponse,
    SubmitWordRequest,
    SubmitWordResponse,
    RoundAvailability,
    RoundDetails,
)
from backend.services.player_service import PlayerService
from backend.services.transaction_service import TransactionService
from backend.services.round_service import RoundService
from backend.services.vote_service import VoteService
from backend.services.queue_service import QueueService
from backend.utils.exceptions import (
    InsufficientBalanceError,
    AlreadyInRoundError,
    InvalidWordError,
    DuplicateWordError,
    RoundExpiredError,
    RoundNotFoundError,
    NoWordsetsAvailableError,
)
from datetime import datetime, UTC
from uuid import UUID
import random
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone for proper JSON serialization."""
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@router.post("/prompt", response_model=StartPromptRoundResponse)
async def start_prompt_round(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a prompt round."""
    player_service = PlayerService(db)
    transaction_service = TransactionService(db)
    round_service = RoundService(db)

    # Check if can start
    can_start, error = await player_service.can_start_prompt_round(player)
    if not can_start:
        raise HTTPException(status_code=400, detail=error)

    try:
        round_object = await round_service.start_prompt_round(player, transaction_service)

        return StartPromptRoundResponse(
            round_id=round_object.round_id,
            prompt_text=round_object.prompt_text,
            expires_at=ensure_utc(round_object.expires_at),
            cost=round_object.cost,
        )
    except Exception as e:
        logger.error(f"Error starting prompt round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/copy", response_model=StartCopyRoundResponse)
async def start_copy_round(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a copy round."""
    player_service = PlayerService(db)
    transaction_service = TransactionService(db)
    round_service = RoundService(db)

    # Check if can start
    can_start, error = await player_service.can_start_copy_round(player)
    if not can_start:
        raise HTTPException(status_code=400, detail=error)

    try:
        round_object = await round_service.start_copy_round(player, transaction_service)

        return StartCopyRoundResponse(
            round_id=round_object.round_id,
            original_word=round_object.original_word,
            prompt_round_id=round_object.prompt_round_id,
            expires_at=ensure_utc(round_object.expires_at),
            cost=round_object.cost,
            discount_active=QueueService.is_copy_discount_active(),
        )
    except Exception as e:
        logger.error(f"Error starting copy round: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vote", response_model=StartVoteRoundResponse)
async def start_vote_round(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a vote round."""
    player_service = PlayerService(db)
    transaction_service = TransactionService(db)
    vote_service = VoteService(db)

    # Check if can start
    can_start, error = await player_service.can_start_vote_round(player, vote_service)
    if not can_start:
        raise HTTPException(status_code=400, detail=error)

    try:
        round_object, wordset = await vote_service.start_vote_round(player, transaction_service)

        # Randomize word order per-voter
        words = [wordset.original_word, wordset.copy_word_1, wordset.copy_word_2]
        random.shuffle(words)

        return StartVoteRoundResponse(
            round_id=round_object.round_id,
            wordset_id=wordset.wordset_id,
            prompt_text=wordset.prompt_text,
            words=words,
            expires_at=ensure_utc(round_object.expires_at),
        )
    except NoWordsetsAvailableError as e:
        raise HTTPException(status_code=400, detail="no_wordsets_available")
    except Exception as e:
        logger.error(f"Error starting vote round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{round_id}/submit", response_model=SubmitWordResponse)
async def submit_word(
    round_id: UUID = Path(...),
    request: SubmitWordRequest = ...,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Submit word for prompt or copy round."""
    transaction_service = TransactionService(db)
    round_service = RoundService(db)

    # Get round
    round_object = await db.get(Round, round_id)
    if not round_object or round_object.player_id != player.player_id:
        raise HTTPException(status_code=404, detail="Round not found")

    try:
        if round_object.round_type == "prompt":
            round_object = await round_service.submit_prompt_word(
                round_id, request.word, player, transaction_service
            )
        elif round_object.round_type == "copy":
            round_object = await round_service.submit_copy_word(
                round_id, request.word, player, transaction_service
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid round type for word submission")

        return SubmitWordResponse(
            success=True,
            word=request.word.upper(),
        )
    except InvalidWordError as e:
        raise HTTPException(status_code=400, detail={"error": "invalid_word", "message": str(e)})
    except DuplicateWordError as e:
        raise HTTPException(status_code=400, detail={"error": "duplicate", "message": str(e)})
    except RoundExpiredError as e:
        raise HTTPException(status_code=400, detail={"error": "expired", "message": str(e)})
    except Exception as e:
        logger.error(f"Error submitting word: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available", response_model=RoundAvailability)
async def get_rounds_available(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get which round types are currently available."""
    player_service = PlayerService(db)
    round_service = RoundService(db)
    vote_service = VoteService(db)

    # Get prompts waiting count excluding player's own prompts
    prompts_waiting = await round_service.get_available_prompts_count(player.player_id)
    wordsets_waiting = await vote_service.count_available_wordsets_for_player(player.player_id)

    can_prompt, _ = await player_service.can_start_prompt_round(player)
    can_copy, _ = await player_service.can_start_copy_round(player)
    can_vote, _ = await player_service.can_start_vote_round(
        player,
        vote_service,
        available_count=wordsets_waiting,
    )

    # Override can_copy if no prompts are waiting
    if prompts_waiting == 0:
        can_copy = False

    # Override can_vote if no wordsets are waiting
    if wordsets_waiting == 0:
        can_vote = False

    return RoundAvailability(
        can_prompt=can_prompt,
        can_copy=can_copy,
        can_vote=can_vote,
        prompts_waiting=prompts_waiting,
        wordsets_waiting=wordsets_waiting,
        copy_discount_active=QueueService.is_copy_discount_active(),
        copy_cost=QueueService.get_copy_cost(),
        current_round_id=player.active_round_id,
    )


@router.get("/{round_id}", response_model=RoundDetails)
async def get_round_details(
    round_id: UUID = Path(...),
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get round details."""
    round_object = await db.get(Round, round_id)

    if not round_object or round_object.player_id != player.player_id:
        raise HTTPException(status_code=404, detail="Round not found")

    return RoundDetails(
        round_id=round_object.round_id,
        type=round_object.round_type,
        status=round_object.status,
        expires_at=ensure_utc(round_object.expires_at),
        prompt_text=round_object.prompt_text,
        original_word=round_object.original_word,
        submitted_word=round_object.submitted_word or round_object.copy_word,
        cost=round_object.cost,
    )
