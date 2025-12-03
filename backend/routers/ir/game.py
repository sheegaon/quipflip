"""Game/backronym endpoints for Initial Reaction (IR)."""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.dependencies import get_current_player, enforce_vote_rate_limit
from backend.models.ir.enums import SetStatus
from backend.models.ir.player import IRPlayer
from backend.schemas.backronym import (
    BackronymSet,
    ResultsResponse,
    SetStatusResponse,
    StartGameRequest,
    StartGameResponse,
    SubmitBackronymRequest,
    SubmitBackronymResponse,
    SubmitVoteRequest,
    SubmitVoteResponse,
    ValidateBackronymRequest,
    ValidateBackronymResponse,
)
from backend.services.auth_service import GameType
from backend.services.ir.backronym_set_service import BackronymSetService
from backend.services.ir.result_view_service import IRResultViewService
from backend.services.ir.scoring_service import IRScoringService
from backend.services.transaction_service import TransactionService
from backend.services.ir.vote_service import IRVoteError, IRVoteService
from backend.services.phrase_validator import PhraseValidator
from backend.utils.datetime_helpers import ensure_utc

router = APIRouter()
settings = get_settings()


# IR-specific wrapper for get_current_player
async def get_ir_player(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> IRPlayer:
    """Get current IR player."""
    return await get_current_player(
        request=request,
        game_type=GameType.IR,
        authorization=authorization,
        db=db
    )


# IR-specific wrapper for enforce_vote_rate_limit
async def enforce_ir_vote_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> IRPlayer:
    """Enforce vote rate limits for IR game."""
    return await enforce_vote_rate_limit(
        request=request,
        game_type=GameType.IR,
        authorization=authorization,
        db=db
    )


def _format_datetime(dt: datetime | None) -> str | None:
    """Ensure datetime responses include UTC timezone info."""

    aware_dt = ensure_utc(dt)
    return aware_dt.isoformat() if aware_dt else None


@router.post("/start", response_model=StartGameResponse)
async def start_game(
    _: StartGameRequest | None = None,
    player: IRPlayer = Depends(get_ir_player),
    db: AsyncSession = Depends(get_db),
) -> StartGameResponse:
    """Start a new backronym battle or join an existing one."""
    from sqlalchemy import select
    from backend.models.ir.player_data import IRPlayerData

    logger = logging.getLogger(__name__)

    try:
        # Load IR player data to check wallet
        result = await db.execute(
            select(IRPlayerData).where(IRPlayerData.player_id == player.player_id)
        )
        player_data = result.scalar_one_or_none()

        wallet = player_data.wallet if player_data else settings.ir_initial_balance

        if wallet < settings.ir_backronym_entry_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance (need {settings.ir_backronym_entry_cost} IC)",
            )

        set_service = BackronymSetService(db)
        txn_service = TransactionService(db)

        available_set = await set_service.get_available_set_for_entry(
            exclude_player_id=str(player.player_id)
        )

        if not available_set:
            set_obj = await set_service.create_set()
        else:
            set_obj = available_set

        await txn_service.debit_wallet(
            player_id=str(player.player_id),
            amount=settings.ir_backronym_entry_cost,
            transaction_type=txn_service.ENTRY_CREATION,
            reference_id=str(set_obj.set_id),
        )

        return StartGameResponse(
            set_id=str(set_obj.set_id),
            word=set_obj.word,
            mode=set_obj.mode,
            status=str(set_obj.status),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in start_game: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sets/{set_id}/submit", response_model=SubmitBackronymResponse)
async def submit_backronym(
    set_id: str,
    request: SubmitBackronymRequest,
    player: IRPlayer = Depends(get_ir_player),
    db: AsyncSession = Depends(get_db),
) -> SubmitBackronymResponse:
    """Submit a backronym entry to a set."""
    logger = logging.getLogger(__name__)

    try:
        logger.debug(f"submit_backronym called with set_id={set_id}, words={request.words}")

        set_service = BackronymSetService(db)

        set_obj = await set_service.get_set_by_id(set_id)
        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        entry = await set_service.add_entry(
            set_id=set_id,
            player_id=str(player.player_id),
            backronym_text=request.words,
            is_ai=False,
        )

        set_obj = await set_service.get_set_by_id(set_id)

        return SubmitBackronymResponse(
            entry_id=str(entry.entry_id),
            set_id=set_id,
            status=set_obj.status,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in submit_backronym: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sets/{set_id}/validate", response_model=ValidateBackronymResponse)
async def validate_backronym(
    set_id: str,
    request: ValidateBackronymRequest,
    _: IRPlayer = Depends(get_ir_player),
    db: AsyncSession = Depends(get_db),
) -> ValidateBackronymResponse:
    """Validate backronym words using the backend validator service."""
    logger = logging.getLogger(__name__)

    try:
        set_service = BackronymSetService(db)
        set_obj = await set_service.get_set_by_id(set_id)

        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        normalized_words = [word.strip().upper() for word in request.words]

        async with PhraseValidator() as validator:
            is_valid, error = await validator.validate_backronym_words(
                normalized_words,
                len(set_obj.word),
            )

        return ValidateBackronymResponse(
            is_valid=is_valid,
            error=error or None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating backronym words: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sets/{set_id}/status", response_model=SetStatusResponse)
async def get_set_status(
    set_id: str,
    player: IRPlayer = Depends(get_ir_player),
    db: AsyncSession = Depends(get_db),
) -> SetStatusResponse:
    """Get current status of a backronym set."""

    try:
        set_service = BackronymSetService(db)
        set_obj = await set_service.get_set_by_id(set_id)

        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        set_details = await set_service.get_set_details(set_id)

        player_has_submitted = False
        if set_details.get("entries"):
            for entry in set_details["entries"]:
                if entry.get("player_id") == str(player.player_id):
                    player_has_submitted = True
                    break

        player_has_voted = False
        if set_details.get("votes"):
            for vote in set_details["votes"]:
                if vote.get("player_id") == str(player.player_id):
                    player_has_voted = True
                    break

        return SetStatusResponse(
            set=BackronymSet(
                set_id=set_id,
                word=set_obj.word,
                mode=set_obj.mode,
                status=str(set_obj.status),
                entry_count=len(set_details.get("entries", [])),
                vote_count=len(set_details.get("votes", [])),
                non_participant_vote_count=0,
                total_pool=0,
                creator_final_pool=0,
                created_at=_format_datetime(set_obj.created_at) or "",
                transitions_to_voting_at=_format_datetime(set_obj.transitions_to_voting_at),
                voting_finalized_at=_format_datetime(set_obj.voting_finalized_at),
            ),
            player_has_submitted=player_has_submitted,
            player_has_voted=player_has_voted,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sets/{set_id}/vote", response_model=SubmitVoteResponse)
async def submit_vote(
    set_id: str,
    request: SubmitVoteRequest,
    player: IRPlayer = Depends(enforce_ir_vote_rate_limit),
    db: AsyncSession = Depends(get_db),
) -> SubmitVoteResponse:
    """Submit a vote on a backronym entry."""

    try:
        vote_service = IRVoteService(db)
        txn_service = TransactionService(db)

        is_eligible, error, is_participant = await vote_service.check_vote_eligibility(
            str(player.player_id), set_id
        )

        if not is_eligible:
            raise HTTPException(status_code=400, detail=error)

        if not is_participant:
            await txn_service.debit_wallet(
                player_id=str(player.player_id),
                amount=settings.ir_vote_cost,
                transaction_type=txn_service.VOTE_ENTRY,
                reference_id=set_id,
            )

        vote_result = await vote_service.submit_vote(
            set_id=set_id,
            player_id=str(player.player_id),
            chosen_entry_id=request.entry_id,
            is_participant=is_participant,
        )

        return SubmitVoteResponse(
            vote_id=vote_result["vote_id"],
            set_id=vote_result["set_id"],
        )

    except IRVoteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sets/{set_id}/results", response_model=ResultsResponse)
async def get_results(
    set_id: str,
    player: IRPlayer = Depends(get_ir_player),
    db: AsyncSession = Depends(get_db),
) -> ResultsResponse:
    """Get finalized results for a set with full details."""

    try:
        set_service = BackronymSetService(db)
        result_service = IRResultViewService(db)
        scoring_service = IRScoringService(db)
        vote_service = IRVoteService(db)

        set_obj = await set_service.get_set_by_id(set_id)
        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        if set_obj.status != SetStatus.FINALIZED:
            raise HTTPException(status_code=400, detail="Set not finalized yet")

        result = await result_service.claim_result(str(player.player_id), set_id)

        set_details = await set_service.get_set_details(set_id)

        player_entry = None
        if set_details.get("entries"):
            for entry in set_details["entries"]:
                if entry.get("player_id") == str(player.player_id):
                    player_entry = entry
                    break

        player_vote = None
        if set_details.get("votes"):
            for vote in set_details["votes"]:
                if vote.get("player_id") == str(player.player_id):
                    player_vote = vote
                    break

        summary = await scoring_service.get_payout_summary(set_id)

        payout_breakdown = None
        if result:
            payout_breakdown = {
                "entry_cost": result.get("entry_cost", 100),
                "vote_cost": result.get("vote_cost", 0),
                "gross_payout": result.get("gross_payout", 0),
                "vault_rake": result.get("vault_rake", 0),
                "net_payout": result.get("net_payout", 0),
                "vote_reward": result.get("vote_reward", 0),
            }

        return ResultsResponse(
            set=BackronymSet(
                set_id=set_id,
                word=set_obj.word,
                mode=set_obj.mode,
                status=str(set_obj.status),
                entry_count=len(set_details.get("entries", [])),
                vote_count=len(set_details.get("votes", [])),
                non_participant_vote_count=0,
                total_pool=summary.get("total_pool", 0),
                creator_final_pool=0,
                created_at=_format_datetime(set_obj.created_at) or "",
                transitions_to_voting_at=_format_datetime(set_obj.transitions_to_voting_at),
                voting_finalized_at=_format_datetime(set_obj.voting_finalized_at),
            ),
            entries=set_details.get("entries", []),
            votes=set_details.get("votes", []),
            player_entry=player_entry,
            player_vote=player_vote,
            payout_breakdown=payout_breakdown,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
