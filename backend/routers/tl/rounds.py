"""ThinkLink (TL) rounds API router."""
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Header, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.schemas.tl_round import (
    StartRoundResponse,
    SubmitGuessRequest,
    SubmitGuessResponse,
    RoundDetails,
    RoundAvailability,
    AbandonRoundResponse,
)
from backend.services import GameType
from backend.services.tl.round_service import TLRoundService
from backend.services.tl.scoring_service import TLScoringService
from backend.services.tl.dependencies import (
    get_round_service,
    get_scoring_service,
)
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


@router.get("/available", response_model=RoundAvailability)
async def check_round_availability(
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
):
    """Check if player can start a new round and current balance."""
    settings = get_settings()

    # Check if player has sufficient balance
    can_start = player.tl_wallet >= settings.tl_entry_cost
    error_message = None if can_start else "insufficient_balance"

    return RoundAvailability(
        can_start_round=can_start,
        error_message=error_message,
        tl_wallet=player.tl_wallet,
        tl_vault=player.tl_vault,
        entry_cost=settings.tl_entry_cost,
        max_payout=settings.tl_max_payout,
        starting_balance=settings.tl_starting_balance,
    )


@router.post("/start", response_model=StartRoundResponse)
async def start_round(
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
    round_service: TLRoundService = Depends(get_round_service),
):
    """Start a new ThinkLink round.

    Steps:
    1. Verify player balance >= entry_cost
    2. Select random active prompt
    3. Build snapshot (up to 1000 active answers)
    4. Deduct entry cost
    5. Create round record
    """
    try:
        logger.debug(f"🎮 Starting TL round for player {player.player_id}...")

        settings = get_settings()

        # Start round
        round_obj, error = await round_service.start_round(
            db, str(player.player_id)
        )

        if error or not round_obj:
            logger.warning(f"⚠️  Failed to start round: {error}")
            if error == "insufficient_balance":
                raise HTTPException(
                    status_code=400, detail="insufficient_balance"
                )
            elif error == "no_prompts_available":
                raise HTTPException(status_code=400, detail="no_prompts_available")
            else:
                raise HTTPException(status_code=500, detail="round_start_failed")

        # Commit changes to database
        await db.commit()

        logger.debug(f"✅ Round started: {round_obj.round_id}")

        return StartRoundResponse(
            round_id=round_obj.round_id,
            prompt_text=round_obj.prompt.text if hasattr(round_obj, 'prompt') else "",
            snapshot_answer_count=len(round_obj.snapshot_answer_ids or []),
            snapshot_total_weight=round_obj.snapshot_total_weight,
            created_at=round_obj.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error starting round: {e}")
        raise HTTPException(status_code=500, detail="round_start_failed")


@router.post("/{round_id}/guess", response_model=SubmitGuessResponse)
async def submit_guess(
    round_id: UUID = Path(..., description="Round ID"),
    request_body: SubmitGuessRequest = Body(...),
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
    round_service: TLRoundService = Depends(get_round_service),
):
    """Submit a guess for an active round.

    Steps:
    1. Validate round exists and is active
    2. Generate embedding for guess
    3. Check on-topic
    4. Check self-similarity to prior guesses
    5. Find matches in snapshot answers
    6. Update matched_clusters if new match
    7. Add strike if no matches
    8. End round if 3 strikes
    9. Log guess
    """
    try:
        guess_text = request_body.guess_text

        logger.debug(f"💭 Player {player.player_id} submitting guess: '{guess_text}'")

        # Submit guess
        result, error = await round_service.submit_guess(
            db, str(round_id), str(player.player_id), guess_text
        )

        if error:
            logger.warning(f"⚠️  Guess rejected: {error}")
            if error == "round_not_found":
                raise HTTPException(status_code=404, detail="round_not_found")
            elif error == "unauthorized":
                raise HTTPException(status_code=403, detail="unauthorized")
            elif error == "round_not_active":
                raise HTTPException(status_code=400, detail="round_not_active")
            elif error == "round_already_ended":
                raise HTTPException(status_code=400, detail="round_already_ended")
            elif error == "off_topic":
                raise HTTPException(status_code=400, detail="off_topic")
            elif error == "too_similar":
                raise HTTPException(status_code=400, detail="too_similar")
            else:
                raise HTTPException(status_code=500, detail="submit_failed")

        # Commit changes to database
        await db.commit()

        logger.debug(
            f"✅ Guess processed: was_match={result['was_match']}, "
            f"coverage={result['current_coverage']:.2%}"
        )

        return SubmitGuessResponse(
            was_match=result["was_match"],
            matched_answer_count=result["matched_answer_count"],
            matched_cluster_ids=result["matched_cluster_ids"],
            new_strikes=result["new_strikes"],
            current_coverage=result["current_coverage"],
            round_status=result["round_status"],
            round_id=round_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error submitting guess: {e}")
        raise HTTPException(status_code=500, detail="submit_failed")


@router.post("/{round_id}/abandon", response_model=AbandonRoundResponse)
async def abandon_round(
    round_id: UUID = Path(..., description="Round ID"),
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
    round_service: TLRoundService = Depends(get_round_service),
):
    """Abandon an active round with partial refund.

    Refund: entry_cost - 5 penalty (95 coins default with 100 entry cost)
    """
    try:
        logger.debug(f"🚪 Player {player.player_id} abandoning round {round_id}...")

        # Abandon round
        result, error = await round_service.abandon_round(
            db, str(round_id), str(player.player_id)
        )

        if error:
            logger.warning(f"⚠️  Abandon failed: {error}")
            if error == "round_not_found":
                raise HTTPException(status_code=404, detail="round_not_found")
            elif error == "unauthorized":
                raise HTTPException(status_code=403, detail="unauthorized")
            elif error == "round_not_active":
                raise HTTPException(status_code=400, detail="round_not_active")
            else:
                raise HTTPException(status_code=500, detail="abandon_failed")

        # Commit changes to database
        await db.commit()

        logger.debug(
            f"✅ Round abandoned: refund={result['refund_amount']} coins"
        )

        return AbandonRoundResponse(
            round_id=UUID(result["round_id"]),
            status=result["status"],
            refund_amount=result["refund_amount"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error abandoning round: {e}")
        raise HTTPException(status_code=500, detail="abandon_failed")


@router.get("/{round_id}", response_model=RoundDetails)
async def get_round(
    round_id: UUID = Path(..., description="Round ID"),
    player: Player = Depends(get_tl_player),
    db: AsyncSession = Depends(get_db),
    scoring_service: TLScoringService = Depends(get_scoring_service),
):
    """Get details of a specific round."""
    try:
        from sqlalchemy import select
        from backend.models.tl import TLRound

        # Fetch round
        result = await db.execute(
            select(TLRound).where(TLRound.round_id == round_id)
        )
        round_obj = result.scalars().first()

        if not round_obj:
            raise HTTPException(status_code=404, detail="round_not_found")

        if round_obj.player_id != player.player_id:
            raise HTTPException(status_code=403, detail="unauthorized")

        wallet_award = None
        vault_award = None
        gross_payout = round_obj.gross_payout

        if round_obj.final_coverage is not None:
            wallet_award, vault_award, payout_total = scoring_service.calculate_payout(
                round_obj.final_coverage
            )
            if gross_payout is None:
                gross_payout = payout_total

        return RoundDetails(
            round_id=round_obj.round_id,
            prompt_id=round_obj.prompt_id,
            prompt_text=round_obj.prompt.text if hasattr(round_obj, 'prompt') else "",
            snapshot_answer_count=len(round_obj.snapshot_answer_ids or []),
            snapshot_total_weight=round_obj.snapshot_total_weight,
            matched_clusters=round_obj.matched_clusters or [],
            strikes=round_obj.strikes,
            status=round_obj.status,
            final_coverage=round_obj.final_coverage,
            gross_payout=gross_payout,
            wallet_award=wallet_award,
            vault_award=vault_award,
            created_at=round_obj.created_at,
            ended_at=round_obj.ended_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching round: {e}")
        raise HTTPException(status_code=500, detail="fetch_failed")
