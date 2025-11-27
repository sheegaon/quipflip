"""Rounds API router for Meme Mint - vote and caption rounds."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.mm.player import MMPlayer
from backend.schemas.mm_round import (
    StartVoteRoundResponse,
    SubmitVoteRequest,
    SubmitVoteResponse,
    SubmitCaptionRequest,
    SubmitCaptionResponse,
    RoundDetails,
    RoundAvailability,
)
from backend.services import TransactionService, GameType
from backend.services.mm import (
    MMGameService,
    MMVoteService,
    MMCaptionService,
    MMSystemConfigService,
    MMPlayerDailyStateService,
)
from backend.utils import ensure_utc
from backend.utils.exceptions import (
    InsufficientBalanceError,
    NoContentAvailableError,
    RoundExpiredError,
    RoundNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Use Meme Mint authentication
async def get_mm_player(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        db: AsyncSession = Depends(get_db),
):
    # Wrapper keeps dependency async so FastAPI awaits it (partial would not)
    return await get_current_player(request=request, game_type=GameType.MM, authorization=authorization, db=db)


@router.post("/vote", response_model=StartVoteRoundResponse)
async def start_vote_round(
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Start a vote round.

    Selects an image with at least 5 unseen captions and presents them
    for voting. Charges entry cost (default 5 FC).
    """
    transaction_service = TransactionService(db, GameType.MM)
    game_service = MMGameService(db)

    try:
        round_obj = await game_service.start_vote_round(player, transaction_service)

        # Load image relationship
        await db.refresh(round_obj, ['image'])

        # Load caption details
        from sqlalchemy import select
        from backend.models.mm.caption import MMCaption

        caption_ids = [UUID(str(cid)) for cid in round_obj.caption_ids_shown]

        stmt = select(MMCaption).where(
            MMCaption.caption_id.in_(caption_ids)
        )
        result = await db.execute(stmt)
        captions_map = {c.caption_id: c for c in result.scalars().all()}

        # Preserve order from caption_ids_shown
        captions = [
            {
                'caption_id': str(cid),
                'text': captions_map[cid].text,
            }
            for cid in caption_ids
            if cid in captions_map
        ]

        return StartVoteRoundResponse(
            round_id=round_obj.round_id,
            image_id=round_obj.image_id,
            image_url=round_obj.image.source_url,
            thumbnail_url=round_obj.image.thumbnail_url,
            attribution_text=round_obj.image.attribution_text,
            captions=captions,
            expires_at=ensure_utc(round_obj.created_at),
            cost=round_obj.entry_cost,
        )

    except NoContentAvailableError as e:
        raise HTTPException(
            status_code=400,
            detail="No images available with enough unseen captions. Try submitting captions!"
        )
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting vote round: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start vote round")


@router.post("/vote/{round_id}/submit", response_model=SubmitVoteResponse)
async def submit_vote(
        round_id: UUID = Path(...),
        request: SubmitVoteRequest = ...,
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Submit a vote for a caption in a vote round.

    Awards payouts to caption author(s) and updates statistics.
    """
    transaction_service = TransactionService(db, GameType.MM)
    game_service = MMGameService(db)
    vote_service = MMVoteService(db)

    # Get round
    round_obj = await game_service.get_round(round_id, player.player_id)
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")

    # Check if already submitted
    if round_obj.chosen_caption_id:
        raise HTTPException(status_code=400, detail="Vote already submitted for this round")

    # Expiration check removed - rounds never expire

    try:
        result = await vote_service.submit_vote(
            round_obj,
            request.caption_id,
            player,
            transaction_service
        )

        return SubmitVoteResponse(
            success=result['success'],
            chosen_caption_id=result['caption_id'],
            payout=result['payout_wallet'],
            correct=True,  # For MVP, all votes are "correct" (just means they voted)
            new_wallet=result['new_wallet'],
            new_vault=result['new_vault'],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting vote: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit vote")


@router.post("/caption", response_model=SubmitCaptionResponse)
async def submit_caption(
        request: SubmitCaptionRequest = ...,
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Submit a caption for an image.

    The backend automatically determines if the caption is a riff or original
    based on cosine similarity analysis against the 5 captions shown in the round.
    First caption per day is free, subsequent captions cost 10 FC (default).
    """
    from sqlalchemy import select
    from backend.models.mm.caption import MMCaption

    transaction_service = TransactionService(db, GameType.MM)
    caption_service = MMCaptionService(db)
    game_service = MMGameService(db)

    # Get the round to determine which image to caption and get the shown captions
    round_obj = await game_service.get_round(request.round_id, player.player_id)
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")

    # Get the image from the round
    image_id = round_obj.image_id

    # Load the captions that were shown in this round for riff detection
    caption_ids = [UUID(str(cid)) for cid in round_obj.caption_ids_shown]
    stmt = select(MMCaption).where(MMCaption.caption_id.in_(caption_ids))
    result = await db.execute(stmt)
    shown_captions = result.scalars().all()

    try:
        result = await caption_service.submit_caption(
            player,
            image_id,
            request.caption_text,
            shown_captions,  # Pass captions for algorithmic riff detection
            transaction_service
        )

        return SubmitCaptionResponse(
            success=result['success'],
            caption_id=result['caption_id'],
            cost=result['cost'],
            used_free_slot=result['used_free_slot'],
            new_wallet=result['new_wallet'],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientBalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting caption: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit caption")


@router.get("/available", response_model=RoundAvailability)
async def get_round_availability(
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Get current round availability and game constants."""
    config_service = MMSystemConfigService(db)
    daily_state_service = MMPlayerDailyStateService(db, config_service)

    # Get config values
    round_entry_cost = await config_service.get_config_value("mm_round_entry_cost", default=5)
    caption_submission_cost = await config_service.get_config_value(
        "mm_caption_submission_cost", default=10
    )
    free_captions_remaining = await daily_state_service.get_remaining_free_captions(
        player.player_id
    )

    # Check daily bonus availability
    from backend.services.mm import MMDailyBonusService
    daily_bonus_service = MMDailyBonusService(db, config_service)
    daily_bonus_available = await daily_bonus_service.is_bonus_available(player.player_id)

    # Simple checks for now
    can_vote = player.wallet >= round_entry_cost
    can_submit_caption = (
            free_captions_remaining > 0 or player.wallet >= caption_submission_cost
    )

    return RoundAvailability(
        can_vote=can_vote,
        can_submit_caption=can_submit_caption,
        current_round_id=None,  # TODO: Track active round if needed
        round_entry_cost=round_entry_cost,
        caption_submission_cost=caption_submission_cost,
        free_captions_remaining=free_captions_remaining,
        daily_bonus_available=daily_bonus_available,
    )


@router.get("/{round_id}", response_model=RoundDetails)
async def get_round_details(
        round_id: UUID = Path(...),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Get details for a specific round."""
    game_service = MMGameService(db)

    round_obj = await game_service.get_round_with_relations(round_id)
    if not round_obj or round_obj.player_id != player.player_id:
        raise HTTPException(status_code=404, detail="Round not found")

    # Load captions
    from sqlalchemy import select
    from backend.models.mm.caption import MMCaption

    caption_ids = [UUID(str(cid)) for cid in round_obj.caption_ids_shown]

    stmt = select(MMCaption).where(
        MMCaption.caption_id.in_(caption_ids)
    )
    result = await db.execute(stmt)
    captions_map = {c.caption_id: c for c in result.scalars().all()}

    captions = [
        {
            'caption_id': str(cid),
            'text': captions_map[cid].text,
        }
        for cid in caption_ids
        if cid in captions_map
    ]

    return RoundDetails(
        round_id=round_obj.round_id,
        type="vote",
        status="completed" if round_obj.chosen_caption_id else "active",
        expires_at=ensure_utc(round_obj.created_at),
        image_id=round_obj.image_id,
        image_url=round_obj.image.source_url,
        cost=round_obj.entry_cost,
        captions=captions,
        chosen_caption_id=round_obj.chosen_caption_id,
    )
