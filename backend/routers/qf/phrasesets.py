"""Phrasesets API router."""
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.dependencies import get_current_player, enforce_vote_rate_limit
from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.schemas.phraseset import (
    VoteRequest,
    VoteResponse,
    PhraseSetResults,
    PhrasesetDetails,
    ClaimPrizeResponse,
    PhrasesetHistory,
    CompletedPhrasesetsResponse,
    PracticePhraseset,
)
from backend.services import TransactionService
from backend.services.qf import QFVoteService, PhrasesetService
from backend.services.auth_service import GameType
from backend.utils.exceptions import RoundExpiredError, AlreadyVotedError
from backend.utils import ensure_utc
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# QF-specific wrapper for enforce_vote_rate_limit
async def enforce_qf_vote_rate_limit(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> QFPlayer:
    """Enforce vote rate limits for QF game."""
    return await enforce_vote_rate_limit(
        request=request,
        game_type=GameType.QF,
        authorization=authorization,
        db=db
    )


# QF-specific wrapper for get_current_player
async def get_qf_player(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> QFPlayer:
    """Get current QF player."""
    return await get_current_player(
        request=request,
        game_type=GameType.QF,
        authorization=authorization,
        db=db
    )


@router.post("/{phraseset_id}/vote", response_model=VoteResponse | dict)
async def submit_vote(
    phraseset_id: UUID = Path(...),
    request: VoteRequest = ...,
    player: QFPlayer = Depends(enforce_qf_vote_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit vote for a phraseset.

    Automatically detects if this is a party phraseset and routes accordingly.
    """
    from backend.services.qf.party_coordination_service import PartyCoordinationService
    from backend.models.qf.party_phraseset import PartyPhraseset
    from sqlalchemy import select

    # Check if this phraseset is part of a party session
    party_phraseset_result = await db.execute(
        select(PartyPhraseset).where(PartyPhraseset.phraseset_id == phraseset_id)
    )
    party_phraseset = party_phraseset_result.scalar_one_or_none()

    if party_phraseset:
        # PARTY MODE: Find the player's vote round
        logger.info(f"Submitting party vote for phraseset {phraseset_id}")

        # Get the player's active vote round for this phraseset
        vote_round_result = await db.execute(
            select(Round)
            .where(Round.player_id == player.player_id)
            .where(Round.round_type == 'vote')
            .where(Round.phraseset_id == phraseset_id)
            .where(Round.status == 'active')
        )
        vote_round = vote_round_result.scalar_one_or_none()
        if not vote_round:
            raise HTTPException(status_code=404, detail="No active vote round found for this phraseset")

        # Use party coordination service
        coordination_service = PartyCoordinationService(db)
        transaction_service = TransactionService(db, GameType.QF)
        result = await coordination_service.submit_party_vote(
            session_id=party_phraseset.session_id,
            player=player,
            round_id=vote_round.round_id,
            phraseset_id=phraseset_id,
            phrase=request.phrase,
            transaction_service=transaction_service
        )

        return {
            **result,
            "party_session_id": str(party_phraseset.session_id),
        }

    else:
        # NORMAL MODE: Use regular service
        transaction_service = TransactionService(db, GameType.QF)
        vote_service = QFVoteService(db)

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
    player: QFPlayer = Depends(get_qf_player),
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
    player: QFPlayer = Depends(get_qf_player),
    db: AsyncSession = Depends(get_db),
):
    """Get voting results for a phraseset (triggers prize collection on first view)."""
    transaction_service = TransactionService(db, GameType.QF)
    vote_service = QFVoteService(db)

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
    player: QFPlayer = Depends(get_qf_player),
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
    player: QFPlayer = Depends(get_qf_player),
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
    limit: int = 10,
    offset: int = 0,
    player: QFPlayer = Depends(get_qf_player),
    db: AsyncSession = Depends(get_db),
):
    """Get a paginated list of all completed phrasesets.

    Returns metadata including start time, finalization time, and vote count.
    Returns 10 items per page by default, ordered by finalization time (most recent first).
    """
    phraseset_service = PhrasesetService(db)
    try:
        result = await phraseset_service.get_completed_phrasesets(limit=limit, offset=offset)
        return CompletedPhrasesetsResponse(**result)
    except Exception as exc:
        logger.error(f"Error getting completed phrasesets: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get completed phrasesets")


@router.get("/{phraseset_id}/public-details", response_model=PhrasesetDetails)
async def get_public_phraseset_details(
    phraseset_id: UUID = Path(...),
    player: QFPlayer = Depends(get_qf_player),
    db: AsyncSession = Depends(get_db),
):
    """Return full details for a COMPLETED phraseset (public access for review)."""
    phraseset_service = PhrasesetService(db)
    try:
        details = await phraseset_service.get_public_phraseset_details(phraseset_id)
        return PhrasesetDetails(**details)
    except ValueError as exc:
        message = str(exc)
        if message == "Phraseset not found":
            raise HTTPException(status_code=404, detail=message)
        if message == "Phraseset not finalized":
            raise HTTPException(status_code=403, detail=message)
        raise HTTPException(status_code=400, detail=message)


@router.get("/practice/random", response_model=PracticePhraseset)
async def get_random_practice_phraseset(
    player: QFPlayer = Depends(get_qf_player),
    db: AsyncSession = Depends(get_db),
):
    """Get a random completed phraseset for practice mode.

    Returns a phraseset that the user was NOT involved in, for practicing rounds.
    """
    phraseset_service = PhrasesetService(db)
    try:
        practice_data = await phraseset_service.get_random_practice_phraseset(player.player_id)
        return PracticePhraseset(**practice_data)
    except ValueError as exc:
        message = str(exc)
        if message == "No phrasesets available for practice":
            raise HTTPException(status_code=404, detail=message)
        raise HTTPException(status_code=400, detail=message)
    except Exception as exc:
        logger.error(f"Error getting random practice phraseset: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get practice phraseset")
