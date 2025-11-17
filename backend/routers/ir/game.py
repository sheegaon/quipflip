"""Game/backronym endpoints for Initial Reaction (IR)."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db
from backend.models.ir.enums import IRSetStatus
from backend.models.ir.ir_player import IRPlayer
from backend.routers.ir.dependencies import get_ir_current_player
from backend.routers.ir.schemas import (
    BackronymSet,
    ResultsResponse,
    SetStatusResponse,
    StartGameRequest,
    StartGameResponse,
    SubmitBackronymRequest,
    SubmitBackronymResponse,
    SubmitVoteRequest,
    SubmitVoteResponse,
)
from backend.services.ir.ir_backronym_set_service import IRBackronymSetService
from backend.services.ir.ir_result_view_service import IRResultViewService
from backend.services.ir.ir_scoring_service import IRScoringService
from backend.services.ir.transaction_service import IRTransactionError, IRTransactionService
from backend.services.ir.ir_vote_service import IRVoteError, IRVoteService

router = APIRouter()
settings = get_settings()


@router.post("/start", response_model=StartGameResponse)
async def start_game(
    _: StartGameRequest | None = None,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> StartGameResponse:
    """Start a new backronym battle or join an existing one."""
    logger = logging.getLogger(__name__)

    try:
        if player.wallet < settings.ir_backronym_entry_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance (need {settings.ir_backronym_entry_cost} IC)",
            )

        set_service = IRBackronymSetService(db)
        txn_service = IRTransactionService(db)

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
    except IRTransactionError as exc:
        logger.error(f"IR transaction error in start_game: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        logger.error(f"Unexpected error in start_game: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sets/{set_id}/submit", response_model=SubmitBackronymResponse)
async def submit_backronym(
    set_id: str,
    request: SubmitBackronymRequest,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SubmitBackronymResponse:
    """Submit a backronym entry to a set."""
    logger = logging.getLogger(__name__)

    try:
        logger.debug(f"submit_backronym called with set_id={set_id}, words={request.words}")

        set_service = IRBackronymSetService(db)

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


@router.get("/sets/{set_id}/status", response_model=SetStatusResponse)
async def get_set_status(
    set_id: str,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SetStatusResponse:
    """Get current status of a backronym set."""

    try:
        set_service = IRBackronymSetService(db)
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
                created_at=set_obj.created_at.isoformat() if set_obj.created_at else "",
                transitions_to_voting_at=set_obj.transitions_to_voting_at.isoformat() if set_obj.transitions_to_voting_at else None,
                voting_finalized_at=set_obj.voting_finalized_at.isoformat() if set_obj.voting_finalized_at else None,
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
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> SubmitVoteResponse:
    """Submit a vote on a backronym entry."""

    try:
        vote_service = IRVoteService(db)
        txn_service = IRTransactionService(db)

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

    except (IRTransactionError, IRVoteError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sets/{set_id}/results", response_model=ResultsResponse)
async def get_results(
    set_id: str,
    player: IRPlayer = Depends(get_ir_current_player),
    db: AsyncSession = Depends(get_db),
) -> ResultsResponse:
    """Get finalized results for a set with full details."""

    try:
        set_service = IRBackronymSetService(db)
        result_service = IRResultViewService(db)
        scoring_service = IRScoringService(db)
        vote_service = IRVoteService(db)

        set_obj = await set_service.get_set_by_id(set_id)
        if not set_obj:
            raise HTTPException(status_code=404, detail="Set not found")

        if set_obj.status != IRSetStatus.FINALIZED:
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
                created_at=set_obj.created_at.isoformat() if set_obj.created_at else "",
                transitions_to_voting_at=set_obj.transitions_to_voting_at.isoformat() if set_obj.transitions_to_voting_at else None,
                voting_finalized_at=set_obj.voting_finalized_at.isoformat() if set_obj.voting_finalized_at else None,
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
