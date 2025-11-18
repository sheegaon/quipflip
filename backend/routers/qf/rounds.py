"""Rounds API router."""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.schemas.round import (
    StartPromptRoundResponse,
    StartCopyRoundResponse,
    StartVoteRoundResponse,
    SubmitPhraseRequest,
    SubmitPhraseResponse,
    RoundAvailability,
    RoundDetails,
    FlagCopyRoundResponse,
    AbandonRoundResponse,
)
from backend.schemas.hint import HintResponse
from backend.services import TransactionService
from backend.services.qf import PlayerService, RoundService, VoteService, QueueService
from backend.services.ai.ai_service import AICopyError
from backend.config import get_settings
from backend.utils import ensure_utc
from backend.utils.exceptions import (
    InsufficientBalanceError,
    AlreadyInRoundError,
    InvalidPhraseError,
    DuplicatePhraseError,
    RoundExpiredError,
    RoundNotFoundError,
    NoPhrasesetsAvailableError,
    NoPromptsAvailableError,
)
from datetime import datetime, UTC
from uuid import UUID
import random
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


async def _player_can_view_prompt_round(
    db: AsyncSession,
    player: QFPlayer,
    prompt_round: Round,
) -> bool:
    """Check if a player has a submitted copy for the given prompt round."""

    if prompt_round.round_type != "prompt":
        return False

    result = await db.execute(
        select(Round.round_id).where(
            Round.round_type == "copy",
            Round.player_id == player.player_id,
            Round.prompt_round_id == prompt_round.round_id,
            Round.status == "submitted",
        ).limit(1)  # Add limit to prevent multiple results error
    )

    return result.scalar() is not None  # Use scalar() instead of scalar_one_or_none()


@router.post("/prompt", response_model=StartPromptRoundResponse)
async def start_prompt_round(
    player: QFPlayer = Depends(get_current_player),
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
    except NoPromptsAvailableError:
        message = (
            "There are no new prompts available for you right now. Please check back later "
            "as we add more prompts, and keep enjoying copy and vote rounds in the meantime!"
        )
        raise HTTPException(status_code=400, detail=message)
    except Exception as e:
        logger.error(f"Error starting prompt round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/copy", response_model=StartCopyRoundResponse)
async def start_copy_round(
    prompt_round_id: UUID | None = None,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a copy round. If prompt_round_id is provided, start a second copy for that prompt."""
    logger.info(f"[API /rounds/copy] Request from player {player.player_id}, second_copy={prompt_round_id is not None}")

    player_service = PlayerService(db)
    transaction_service = TransactionService(db)
    round_service = RoundService(db)

    # Ensure prompt queue is populated from database before checking availability (for first copy)
    if not prompt_round_id:
        await round_service.ensure_prompt_queue_populated()

    # Check if can start (skip queue check for second copy since it uses explicit prompt_round_id)
    if prompt_round_id:
        # Second copy: check basic eligibility (balance for 2x cost, no active round, not locked)
        can_start, error = await player_service.can_start_second_copy_round(player)
        if not can_start:
            logger.warning(f"[API /rounds/copy] Player {player.player_id} cannot start second copy round: {error}")
            raise HTTPException(status_code=400, detail=error)
    else:
        # First copy: full eligibility check including queue availability
        can_start, error = await player_service.can_start_copy_round(player)
        if not can_start:
            logger.warning(f"[API /rounds/copy] Player {player.player_id} cannot start copy round: {error}")
            raise HTTPException(status_code=400, detail=error)

    try:
        round_object, is_second_copy = await round_service.start_copy_round(
            player, transaction_service, prompt_round_id
        )

        logger.info(f"[API /rounds/copy] Successfully started copy round {round_object.round_id} for player {player.player_id}")
        return StartCopyRoundResponse(
            round_id=round_object.round_id,
            original_phrase=round_object.original_phrase,
            prompt_round_id=round_object.prompt_round_id,
            expires_at=ensure_utc(round_object.expires_at),
            cost=round_object.cost,
            discount_active=QueueService.is_copy_discount_active() if not is_second_copy else False,
            is_second_copy=is_second_copy,
        )
    except NoPromptsAvailableError as e:
        logger.error(f"[API /rounds/copy] No prompts available for player {player.player_id}: {str(e)}")
        raise HTTPException(status_code=400, detail="no_prompts_available")
    except Exception as e:
        logger.error(f"[API /rounds/copy] Error starting copy round for player {player.player_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/vote", response_model=StartVoteRoundResponse)
async def start_vote_round(
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a vote round."""
    player_service = PlayerService(db)
    transaction_service = TransactionService(db)
    vote_service = VoteService(db)

    # Check if can start
    await player_service.refresh_vote_lockout_state(player)
    can_start, error = await player_service.can_start_vote_round(player, vote_service)
    if not can_start:
        raise HTTPException(status_code=400, detail=error)

    try:
        round_object, phraseset = await vote_service.start_vote_round(player, transaction_service)

        # Randomize word order per-voter
        phrases = [phraseset.original_phrase, phraseset.copy_phrase_1, phraseset.copy_phrase_2]
        random.shuffle(phrases)

        return StartVoteRoundResponse(
            round_id=round_object.round_id,
            phraseset_id=phraseset.phraseset_id,
            prompt_text=phraseset.prompt_text,
            phrases=phrases,
            expires_at=ensure_utc(round_object.expires_at),
        )
    except NoPhrasesetsAvailableError as e:
        raise HTTPException(status_code=400, detail="no_phrasesets_available")
    except Exception as e:
        logger.error(f"Error starting vote round: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{round_id}/submit", response_model=SubmitPhraseResponse)
async def submit_phrase(
    round_id: UUID = Path(...),
    request: SubmitPhraseRequest = ...,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Submit phrase for prompt or copy round."""
    transaction_service = TransactionService(db)
    round_service = RoundService(db)

    # Get round
    round_object = await db.get(Round, round_id)
    if not round_object or round_object.player_id != player.player_id:
        raise HTTPException(status_code=404, detail="Round not found")

    try:
        second_copy_info = {}
        if round_object.round_type == "prompt":
            round_object = await round_service.submit_prompt_phrase(
                round_id, request.phrase, player, transaction_service
            )
        elif round_object.round_type == "copy":
            round_object, second_copy_info = await round_service.submit_copy_phrase(
                round_id, request.phrase, player, transaction_service
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid round type for phrase submission")

        return SubmitPhraseResponse(
            success=True,
            phrase=request.phrase.upper(),
            eligible_for_second_copy=second_copy_info.get("eligible_for_second_copy", False),
            second_copy_cost=second_copy_info.get("second_copy_cost"),
            prompt_round_id=second_copy_info.get("prompt_round_id"),
            original_phrase=second_copy_info.get("original_phrase"),
        )
    except InvalidPhraseError as e:
        raise HTTPException(status_code=400, detail={"error": "invalid_phrase", "message": str(e)})
    except DuplicatePhraseError as e:
        raise HTTPException(status_code=400, detail={"error": "duplicate_phrase", "message": str(e)})
    except RoundExpiredError as e:
        raise HTTPException(status_code=400, detail={"error": "expired", "message": str(e)})
    except Exception as e:
        logger.error(f"Error submitting phrase: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{round_id}/flag", response_model=FlagCopyRoundResponse)
async def flag_copy_round(
    round_id: UUID = Path(...),
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Flag an active copy round and trigger administrative review."""

    transaction_service = TransactionService(db)
    round_service = RoundService(db)

    try:
        flag = await round_service.flag_copy_round(round_id, player, transaction_service)
    except RoundNotFoundError:
        raise HTTPException(status_code=404, detail="round_not_found")
    except ValueError as exc:
        detail = str(exc)
        if detail == "Round is not active":
            raise HTTPException(status_code=400, detail="round_not_active") from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:  # pragma: no cover - unexpected errors logged
        logger.error(f"Error flagging copy round: {exc}")
        raise HTTPException(status_code=500, detail="flag_failed") from exc

    return FlagCopyRoundResponse(
        flag_id=flag.flag_id,
        refund_amount=flag.partial_refund_amount,
        penalty_kept=flag.penalty_kept,
        status=flag.status,
        message="Copy round flagged",
    )


@router.post("/{round_id}/abandon", response_model=AbandonRoundResponse)
async def abandon_round(
    round_id: UUID = Path(...),
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Abandon an active prompt, copy, or vote round."""

    transaction_service = TransactionService(db)
    round_service = RoundService(db)

    try:
        round_object, refund_amount, penalty_kept = await round_service.abandon_round(
            round_id, player, transaction_service
        )
    except RoundNotFoundError:
        raise HTTPException(status_code=404, detail="round_not_found")
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
    except Exception as exc:  # pragma: no cover - unexpected errors logged
        logger.error(f"Error abandoning round {round_id}: {exc}")
        raise HTTPException(status_code=500, detail="abandon_failed") from exc

    return AbandonRoundResponse(
        round_id=round_object.round_id,
        round_type=round_object.round_type,
        status=round_object.status,
        refund_amount=refund_amount,
        penalty_kept=penalty_kept,
        message="Round abandoned",
    )


@router.get("/available", response_model=RoundAvailability)
async def get_rounds_available(
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get which round types are currently available."""
    player_service = PlayerService(db)
    round_service = RoundService(db)
    vote_service = VoteService(db)

    # Get prompts waiting count excluding player's own prompts
    prompts_waiting = await round_service.get_available_prompts_count(player.player_id)
    phrasesets_waiting = await vote_service.count_available_phrasesets_for_player(player.player_id)

    # Rehydrate prompt queue if necessary so availability reflects database state.
    await round_service.ensure_prompt_queue_populated()

    can_prompt, _ = await player_service.can_start_prompt_round(player)
    can_copy, _ = await player_service.can_start_copy_round(player)
    can_vote, _ = await player_service.can_start_vote_round(
        player,
        vote_service,
        available_count=phrasesets_waiting,
    )

    # Override can_copy if no prompts are waiting
    if prompts_waiting == 0:
        can_copy = False

    # Override can_vote if no phrasesets are waiting
    if phrasesets_waiting == 0:
        can_vote = False

    return RoundAvailability(
        can_prompt=can_prompt,
        can_copy=can_copy,
        can_vote=can_vote,
        prompts_waiting=prompts_waiting,
        phrasesets_waiting=phrasesets_waiting,
        copy_discount_active=QueueService.is_copy_discount_active(),
        copy_cost=QueueService.get_copy_cost(),
        current_round_id=player.active_round_id,
        # Game constants from config
        prompt_cost=settings.prompt_cost,
        vote_cost=settings.vote_cost,
        vote_payout_correct=settings.vote_payout_correct,
        abandoned_penalty=settings.abandoned_penalty,
    )


@router.get("/{round_id}/hints", response_model=HintResponse)
async def get_copy_round_hints(
    round_id: UUID = Path(...),
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Return AI-generated hints for an active copy round.

    Charges hint_cost coins for generating new hints. Cached hints are free.
    """
    round_object = await db.get(Round, round_id)

    if not round_object or round_object.player_id != player.player_id:
        raise HTTPException(status_code=404, detail="Round not found")

    if round_object.round_type != "copy":
        raise HTTPException(status_code=400, detail="Hints are only available for copy rounds")

    if round_object.status != "active":
        raise HTTPException(status_code=400, detail="Hints are only available for active copy rounds")

    round_service = RoundService(db)
    transaction_service = TransactionService(db)

    try:
        hints = await round_service.get_or_generate_hints(round_id, player, transaction_service)
        logger.info(
            "[API /rounds/%s/hints] Returned %s hints for player %s",
            round_id,
            len(hints),
            player.player_id,
        )
        return HintResponse(hints=hints)
    except InsufficientBalanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RoundNotFoundError:
        raise HTTPException(status_code=404, detail="Round not found")
    except RoundExpiredError:
        raise HTTPException(status_code=400, detail="Round expired")
    except InvalidPhraseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AICopyError as exc:
        logger.error(
            "Failed to generate hints for round %s (player %s): %s",
            round_id,
            player.player_id,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to generate hints") from exc
    except Exception as exc:  # noqa: BLE001 - capture unexpected failures
        logger.exception(
            "Unexpected error retrieving hints for round %s (player %s)",
            round_id,
            player.player_id,
        )
        raise HTTPException(status_code=500, detail="Unexpected error retrieving hints") from exc


@router.get("/{round_id}", response_model=RoundDetails)
async def get_round_details(
    round_id: UUID = Path(...),
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get round details."""
    round_object = await db.get(Round, round_id)

    if not round_object:
        raise HTTPException(status_code=404, detail="Round not found")

    if round_object.player_id != player.player_id:
        can_view_prompt = await _player_can_view_prompt_round(db, player, round_object)
        if not can_view_prompt:
            raise HTTPException(status_code=404, detail="Round not found")

    return RoundDetails(
        round_id=round_object.round_id,
        type=round_object.round_type,
        status=round_object.status,
        expires_at=ensure_utc(round_object.expires_at),
        prompt_text=round_object.prompt_text,
        original_phrase=round_object.original_phrase,
        submitted_phrase=round_object.submitted_phrase or round_object.copy_phrase,
        cost=round_object.cost,
    )
