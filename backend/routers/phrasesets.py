"""Phrasesets API router."""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.dependencies import get_current_player, enforce_vote_rate_limit
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.schemas.phraseset import (
    VoteRequest,
    VoteResponse,
    PhraseSetResults,
    PhrasesetDetails,
    ClaimPrizeResponse,
    PhrasesetHistory,
    CompletedPhrasesetsResponse,
)
from backend.services.transaction_service import TransactionService
from backend.services.vote_service import VoteService
from backend.services.phraseset_service import PhrasesetService
from backend.utils.exceptions import (
    RoundExpiredError,
    AlreadyVotedError,
)
from datetime import datetime, UTC
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime has UTC timezone for proper JSON serialization."""
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@router.post("/{phraseset_id}/vote", response_model=VoteResponse)
async def submit_vote(
    phraseset_id: UUID = Path(...),
    request: VoteRequest = ...,
    player: Player = Depends(enforce_vote_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Submit vote for a phraseset."""
    transaction_service = TransactionService(db)
    vote_service = VoteService(db)

    # Get player's active vote round
    if not player.active_round_id:
        raise HTTPException(status_code=400, detail="No active vote round")

    round = await db.get(Round, player.active_round_id)
    if not round or round.round_type != "vote":
        raise HTTPException(status_code=400, detail="Not in a vote round")

    if round.phraseset_id != phraseset_id:
        raise HTTPException(status_code=400, detail="Phraseset does not match active round")

    # Get phraseset
    phraseset = await db.get(Phraseset, phraseset_id)
    if not phraseset:
        raise HTTPException(status_code=404, detail="Phraseset not found")

    try:
        vote = await vote_service.submit_vote(
            round, phraseset, request.phrase, player, transaction_service
        )

        return VoteResponse(
            correct=vote.correct,
            payout=vote.payout,
            original_phrase=phraseset.original_phrase,
            your_choice=vote.voted_phrase,
        )
    except RoundExpiredError as e:
        raise HTTPException(status_code=400, detail={"error": "expired", "message": str(e)})
    except AlreadyVotedError as e:
        raise HTTPException(status_code=400, detail={"error": "already_voted", "message": str(e)})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting vote: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{phraseset_id}/details", response_model=PhrasesetDetails)
async def get_phraseset_details(
    phraseset_id: UUID = Path(...),
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Return full details for a phraseset contribution."""
    phraseset_service = PhrasesetService(db)
    try:
        details = await phraseset_service.get_phraseset_details(phraseset_id, player.player_id)
        return PhrasesetDetails(**details)
    except ValueError as exc:
        message = str(exc)
        if message == "Phraseset not found":
            raise HTTPException(status_code=404, detail=message)
        if message == "Not a contributor to this phraseset":
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=400, detail=message)


@router.get("/{phraseset_id}/results", response_model=PhraseSetResults)
async def get_phraseset_results(
    phraseset_id: UUID = Path(...),
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get voting results for a phraseset (triggers prize collection on first view)."""
    transaction_service = TransactionService(db)
    vote_service = VoteService(db)

    try:
        results = await vote_service.get_phraseset_results(
            phraseset_id, player.player_id, transaction_service
        )

        # Ensure finalized_at has UTC timezone
        if 'finalized_at' in results and results['finalized_at']:
            results['finalized_at'] = ensure_utc(results['finalized_at'])

        return PhraseSetResults(**results)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting phraseset results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{phraseset_id}/claim", response_model=ClaimPrizeResponse)
async def claim_phraseset_prize(
    phraseset_id: UUID = Path(...),
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly mark a phraseset prize as claimed."""
    phraseset_service = PhrasesetService(db)
    try:
        result = await phraseset_service.claim_prize(phraseset_id, player.player_id)
        return ClaimPrizeResponse(**result)
    except ValueError as exc:
        message = str(exc)
        if message == "Phraseset not found":
            raise HTTPException(status_code=404, detail=message)
        if message == "Not a contributor to this phraseset":
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except Exception as exc:
        logger.error(f"Error claiming prize: {exc}")
        raise HTTPException(status_code=500, detail="Failed to claim prize")


@router.get("/{phraseset_id}/history", response_model=PhrasesetHistory)
async def get_phraseset_history(
    phraseset_id: UUID = Path(...),
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get the complete event timeline for a phraseset.

    Returns all events from prompt submission through finalization,
    including usernames and timestamps for each event.

    Access restricted to:
    - Finalized phrasesets only (prevents viewing active rounds)
    - Participants only (contributors or voters)
    """
    phraseset_service = PhrasesetService(db)
    try:
        history = await phraseset_service.get_phraseset_history(phraseset_id, player.player_id)
        return PhrasesetHistory(**history)
    except ValueError as exc:
        message = str(exc)
        if message == "Phraseset not found":
            raise HTTPException(status_code=404, detail=message)
        if message == "Phraseset not finalized":
            raise HTTPException(status_code=403, detail=message)
        if message == "Not a participant in this phraseset":
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except Exception as exc:
        logger.error(f"Error getting phraseset history: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get phraseset history")


@router.get("/completed", response_model=CompletedPhrasesetsResponse)
async def get_completed_phrasesets(
    limit: int = 50,
    offset: int = 0,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get a paginated list of all completed phrasesets.

    Returns metadata including start time, finalization time, and vote count.
    """
    phraseset_service = PhrasesetService(db)
    try:
        result = await phraseset_service.get_completed_phrasesets(limit=limit, offset=offset)
        return CompletedPhrasesetsResponse(**result)
    except Exception as exc:
        logger.error(f"Error getting completed phrasesets: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get completed phrasesets")
