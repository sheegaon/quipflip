"""Party Mode API router."""
from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.qf.player import QFPlayer
from backend.schemas.party import (
    CreatePartySessionRequest,
    CreatePartySessionResponse,
    JoinPartySessionRequest,
    JoinPartySessionResponse,
    MarkReadyResponse,
    AddAIPlayerResponse,
    StartPartySessionResponse,
    PartySessionStatusResponse,
    PartyResultsResponse,
    StartPartyRoundResponse,
    SubmitPartyRoundRequest,
    SubmitPartyRoundResponse,
    PartyListResponse,
    PartyListItemResponse,
    PartyPingResponse,
)
from backend.schemas.notification import PingWebSocketMessage
from backend.services import TransactionService
from backend.services.qf import (
    NotificationConnectionManager,
    get_notification_manager,
    PartySessionService,
    PartyCoordinationService,
    PartyScoringService,
)
from backend.services.qf.party_session_service import (
    SessionNotFoundError,
    SessionAlreadyStartedError,
    SessionFullError,
    AlreadyInSessionError,
    AlreadyInAnotherSessionError,
    NotHostError,
    NotEnoughPlayersError,
    WrongPhaseError,
    AlreadySubmittedError,
    PartyModeError,
)
from backend.services.qf.party_websocket_manager import get_party_websocket_manager
from backend.services.auth_service import AuthService
from backend.utils.model_registry import GameType
from backend.utils.exceptions import (
    NoPromptsAvailableError,
    NoPhrasesetsAvailableError,
    InsufficientBalanceError,
    InvalidPhraseError,
    RoundExpiredError,
)
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()
ws_manager = get_party_websocket_manager()


@router.get("/list", response_model=PartyListResponse)
async def list_active_parties(
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get list of all joinable party sessions.

    Returns only sessions that are:
    - In OPEN status (lobby, not started)
    - Not full (participant_count < max_players)

    Returns:
        PartyListResponse: List of active parties with summary info
    """
    try:
        party_service = PartySessionService(db)
        parties_data = await party_service.list_active_parties()

        # Convert dict responses to PartyListItemResponse objects
        parties = [
            PartyListItemResponse(
                session_id=party['session_id'],
                host_username=party['host_username'],
                participant_count=party['participant_count'],
                min_players=party['min_players'],
                max_players=party['max_players'],
                created_at=party['created_at'],
                is_full=party['is_full'],
            )
            for party in parties_data
        ]

        return PartyListResponse(
            parties=parties,
            total_count=len(parties),
        )

    except Exception as e:
        logger.error(f"Error listing parties: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list parties")


@router.post("/create", response_model=CreatePartySessionResponse)
async def create_party_session(
    request: CreatePartySessionRequest,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Create a new party session.

    Returns:
        CreatePartySessionResponse: Created session with party code
    """
    try:
        party_service = PartySessionService(db)

        logger.info(f"Creating party session for player {player.player_id} with config: min={request.min_players}, max={request.max_players}, prompts={request.prompts_per_player}, copies={request.copies_per_player}, votes={request.votes_per_player}")

        # Create session
        session = await party_service.create_session(
            host_player_id=player.player_id,
            min_players=request.min_players,
            max_players=request.max_players,
            prompts_per_player=request.prompts_per_player,
            copies_per_player=request.copies_per_player,
            votes_per_player=request.votes_per_player,
        )

        logger.info(f"Created party session {session.session_id} with code {session.party_code}")

        # Get full status
        status_data = await party_service.get_session_status(session.session_id)

        return CreatePartySessionResponse(
            session_id=status_data['session_id'],
            party_code=status_data['party_code'],
            host_player_id=status_data['host_player_id'],
            status=status_data['status'],
            current_phase=status_data['current_phase'],
            created_at=status_data['created_at'],
            participants=status_data['participants'],
            min_players=status_data['min_players'],
            max_players=status_data['max_players'],
        )

    except HTTPException:
        # Re-raise HTTP exceptions (e.g., from dependencies)
        raise
    except AlreadyInAnotherSessionError:
        raise HTTPException(status_code=409, detail="already_in_another_session")
    except Exception as e:
        logger.error(f"Error creating party session: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create party session")


async def _handle_party_join(
    session_id: UUID,
    player: QFPlayer,
    party_service: PartySessionService,
) -> JoinPartySessionResponse:
    """Helper function to handle the common logic of joining a party session.

    Args:
        session_id: UUID of the party session to join
        player: Current authenticated player
        party_service: PartySessionService instance

    Returns:
        JoinPartySessionResponse: Session information after joining

    Raises:
        SessionNotFoundError: If session doesn't exist
        SessionAlreadyStartedError: If session has already started
        SessionFullError: If session is at max capacity
        AlreadyInSessionError: If player is already in session
    """
    existing_participant = await party_service.get_participant(
        session_id=session_id,
        player_id=player.player_id,
    )

    # Add participant if they're not already in the session
    if not existing_participant:
        await party_service.add_participant(
            session_id=session_id,
            player_id=player.player_id,
        )

    # Get updated status
    status_data = await party_service.get_session_status(session_id)

    # Broadcast player joined if this is a new participant
    if not existing_participant:
        await ws_manager.notify_player_joined(
            session_id=session_id,
            player_id=player.player_id,
            username=player.username,
            participant_count=len(status_data['participants']),
        )

    return JoinPartySessionResponse(
        session_id=status_data['session_id'],
        party_code=status_data['party_code'],
        status=status_data['status'],
        current_phase=status_data['current_phase'],
        participants=status_data['participants'],
        participant_count=len(status_data['participants']),
        min_players=status_data['min_players'],
        max_players=status_data['max_players'],
    )


@router.post("/join", response_model=JoinPartySessionResponse)
async def join_party_session(
    request: JoinPartySessionRequest,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Join an existing party session by code.

    Args:
        request: Join request with party_code

    Returns:
        JoinPartySessionResponse: Session information

    Raises:
        404: Session not found
        400: Session already started or full
        409: Already in session
    """
    try:
        party_service = PartySessionService(db)

        # Get session by code
        session = await party_service.get_session_by_code(request.party_code)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Party session '{request.party_code}' not found"
            )

        # Use common join logic
        return await _handle_party_join(session.session_id, player, party_service)

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Party session not found")
    except SessionAlreadyStartedError:
        raise HTTPException(status_code=400, detail="Session has already started")
    except SessionFullError:
        raise HTTPException(status_code=400, detail="Session is full")
    except AlreadyInSessionError:
        raise HTTPException(status_code=409, detail="Already in this session")
    except AlreadyInAnotherSessionError:
        raise HTTPException(status_code=409, detail="already_in_another_session")
    except Exception as e:
        logger.error(f"Error joining party session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to join party session")


@router.post("/{session_id}/join", response_model=JoinPartySessionResponse)
async def join_party_session_by_id(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Join an existing party session by session ID.

    This endpoint allows joining a party directly by its session_id,
    typically used when selecting from the party list.

    Args:
        session_id: UUID of the party session

    Returns:
        JoinPartySessionResponse: Session information

    Raises:
        404: Session not found
        400: Session already started or full
        409: Already in session
    """
    try:
        party_service = PartySessionService(db)

        # Use common join logic
        return await _handle_party_join(session_id, player, party_service)

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Party session not found")
    except SessionAlreadyStartedError:
        raise HTTPException(status_code=400, detail="Session has already started")
    except SessionFullError:
        raise HTTPException(status_code=400, detail="Session is full")
    except AlreadyInSessionError:
        raise HTTPException(status_code=409, detail="Already in this session")
    except AlreadyInAnotherSessionError:
        raise HTTPException(status_code=409, detail="already_in_another_session")
    except Exception as e:
        logger.error(f"Error joining party session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to join party session")


@router.post("/{session_id}/ready", response_model=MarkReadyResponse)
async def mark_ready(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Mark player as ready in lobby.

    Args:
        session_id: UUID of the party session

    Returns:
        MarkReadyResponse: Updated participant status

    Raises:
        404: Session not found
        400: Session already started
    """
    try:
        party_service = PartySessionService(db)

        # Mark ready
        participant = await party_service.mark_participant_ready(
            session_id=session_id,
            player_id=player.player_id,
        )

        # Get status
        status_data = await party_service.get_session_status(session_id)

        # Count ready players
        ready_count = sum(1 for p in status_data['participants'] if p['status'] == 'READY')

        # Broadcast ready status
        await ws_manager.notify_player_ready(
            session_id=session_id,
            player_id=player.player_id,
            username=player.username,
            ready_count=ready_count,
            total_count=len(status_data['participants']),
        )

        return MarkReadyResponse(
            participant_id=str(participant.participant_id),
            status=participant.status,
            session={
                'ready_count': ready_count,
                'total_count': len(status_data['participants']),
                'can_start': ready_count >= status_data['min_players'],
            },
        )

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionAlreadyStartedError:
        raise HTTPException(status_code=400, detail="Session has already started")
    except Exception as e:
        logger.error(f"Error marking ready: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark ready")


@router.post("/{session_id}/add-ai", response_model=AddAIPlayerResponse)
async def add_ai_player_to_session(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """
    Add an AI player to the party session (host only, lobby only).

    The AI player will automatically participate in all rounds.

    Args:
        session_id: UUID of the party session
        player: Current authenticated player (must be host)
        db: Database session

    Returns:
        AddAIPlayerResponse: Created AI participant info

    Raises:
        404: Session not found
        403: Player is not the host
        400: Session already started or session is full
    """
    try:
        party_service = PartySessionService(db)

        # Add AI player to session
        from backend.utils.model_registry import GameType
        participant = await party_service.add_ai_player(
            session_id=session_id,
            host_player_id=player.player_id,
        )

        # Broadcast player joined event
        await ws_manager.notify_player_joined(
            session_id=session_id,
            player_id=participant.player_id,
            username=participant.player.username,
            participant_count=await party_service._get_participant_count(session_id),
        )

        return AddAIPlayerResponse(
            participant_id=str(participant.participant_id),
            player_id=str(participant.player_id),
            username=participant.player.username,
            is_ai=True,
        )

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except NotHostError:
        raise HTTPException(status_code=403, detail="Only the host can add AI players")
    except SessionAlreadyStartedError:
        raise HTTPException(status_code=400, detail="Cannot add AI players after session has started")
    except SessionFullError:
        raise HTTPException(status_code=400, detail="Session is full")
    except Exception as e:
        logger.error(f"Error adding AI player: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add AI player")


@router.post("/{session_id}/ping", response_model=PartyPingResponse)
async def ping_party_session(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
    connection_manager: NotificationConnectionManager = Depends(
        get_notification_manager
    ),
):
    """Allow the host to ping all players with a lobby reminder."""

    try:
        party_service = PartySessionService(db)
        session = await party_service.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        participant = await party_service.get_participant(session_id, player.player_id)
        if not participant or not participant.is_host:
            raise HTTPException(status_code=403, detail="Only the host can ping players")

        join_url = f"/party/{session_id}"
        participants = await party_service.get_participants(session_id)

        ping_message = PingWebSocketMessage(
            from_username=player.username,
            timestamp=datetime.now(UTC).isoformat(),
            join_url=join_url,
        )

        for party_participant in participants:
            participant_player = party_participant.player

            if not participant_player or participant_player.player_id == player.player_id:
                continue

            if PartySessionService._is_ai_player(participant_player):
                continue

            await connection_manager.send_to_player(
                participant_player.player_id, ping_message.model_dump()
            )

        await ws_manager.notify_host_ping(
            session_id=session_id,
            host_player_id=player.player_id,
            host_username=player.username,
            join_url=join_url,
        )

        return PartyPingResponse(success=True, message="Ping sent to all players")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pinging party session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send ping")


@router.post("/{session_id}/process-ai")
async def process_ai_submissions(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger AI player submissions for the current phase (host only).

    This endpoint can be called manually or scheduled to process pending
    AI submissions for the current phase.

    Args:
        session_id: UUID of the party session
        player: Current authenticated player (must be host)
        db: Database session

    Returns:
        dict: Summary of AI submissions processed

    Raises:
        404: Session not found
        403: Player is not the host
    """
    try:
        party_service = PartySessionService(db)
        coordination_service = PartyCoordinationService(db)
        transaction_service = TransactionService(db)

        # Verify caller is host
        participant = await party_service.get_participant(session_id, player.player_id)
        if not participant or not participant.is_host:
            raise HTTPException(status_code=403, detail="Only the host can trigger AI submissions")

        # Process AI submissions
        stats = await coordination_service.process_ai_submissions(
            session_id=session_id,
            transaction_service=transaction_service,
        )

        return {
            'success': True,
            'stats': stats,
        }

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error processing AI submissions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process AI submissions")


@router.post("/{session_id}/start", response_model=StartPartySessionResponse)
async def start_party_session(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start the party session (host only).

    Args:
        session_id: UUID of the party session

    Returns:
        StartPartySessionResponse: Updated session status

    Raises:
        404: Session not found
        403: Not the host
        400: Not enough players or already started
    """
    try:
        party_service = PartySessionService(db)

        # Start session
        session = await party_service.start_session(
            session_id=session_id,
            requesting_player_id=player.player_id,
        )

        # Get status
        status_data = await party_service.get_session_status(session_id)

        # Broadcast session started
        await ws_manager.notify_session_started(
            session_id=session_id,
            current_phase=session.current_phase,
            participant_count=len(status_data['participants']),
            message="Party started! Everyone write your best original phrase.",
        )

        # Trigger AI submissions for initial PROMPT phase (synchronous to avoid async context issues)
        try:
            coordination_service = PartyCoordinationService(db)
            transaction_service = TransactionService(db)
            await coordination_service._trigger_ai_submissions_for_new_phase(
                session_id=session_id,
                transaction_service=transaction_service,
            )
            logger.info(f"AI submissions triggered for session {session_id} PROMPT phase")
        except Exception as e:
            # Log but don't fail the session start if AI submissions fail
            logger.error(f"Failed to trigger AI submissions for session {session_id}: {e}", exc_info=True)

        return StartPartySessionResponse(
            session_id=status_data['session_id'],
            status=status_data['status'],
            current_phase=status_data['current_phase'],
            phase_started_at=session.phase_started_at,
            locked_at=session.locked_at,
            participants=status_data['participants'],
        )

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except NotHostError:
        raise HTTPException(status_code=403, detail="Only the host can start the session")
    except NotEnoughPlayersError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SessionAlreadyStartedError:
        raise HTTPException(status_code=400, detail="Session has already started")
    except Exception as e:
        logger.error(f"Error starting party session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start party session")


@router.get("/{session_id}/status", response_model=PartySessionStatusResponse)
async def get_party_session_status(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get current party session status.

    Args:
        session_id: UUID of the party session

    Returns:
        PartySessionStatusResponse: Complete session status

    Raises:
        404: Session not found
    """
    try:
        party_service = PartySessionService(db)
        status_data = await party_service.get_session_status(session_id)

        return PartySessionStatusResponse(**status_data)

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error getting session status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get session status")


@router.get("/{session_id}/results", response_model=PartyResultsResponse)
async def get_party_results(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get party match results.

    Args:
        session_id: UUID of the party session

    Returns:
        PartyResultsResponse: Complete match results

    Raises:
        404: Session not found
        400: Session not in RESULTS phase
    """
    try:
        party_service = PartySessionService(db)
        scoring_service = PartyScoringService(db)

        # Verify session is in RESULTS phase
        session = await party_service.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.current_phase not in ['RESULTS', 'COMPLETED']:
            raise HTTPException(
                status_code=400,
                detail=f"Results not available yet (current phase: {session.current_phase})"
            )

        # Calculate results
        results = await scoring_service.calculate_session_results(session_id)

        return PartyResultsResponse(**results)

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        logger.error(f"Error getting party results: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get party results")


@router.post("/{session_id}/rounds/prompt", response_model=StartPartyRoundResponse)
async def start_party_prompt_round(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a prompt round within party context.

    Args:
        session_id: UUID of the party session

    Returns:
        StartPartyRoundResponse: Created round

    Raises:
        404: Session not found
        400: Wrong phase or already submitted
    """
    try:
        transaction_service = TransactionService(db)
        coordination_service = PartyCoordinationService(db)

        # Start party prompt round
        round_obj, party_round_id = await coordination_service.start_party_prompt_round(
            session_id=session_id,
            player=player,
            transaction_service=transaction_service,
        )

        # Get session progress
        party_service = PartySessionService(db)
        participant = await party_service.get_participant(session_id, player.player_id)
        session = await party_service.get_session_by_id(session_id)
        all_participants = await party_service.get_participants(session_id)
        active_participants = [p for p in all_participants if p.status == 'ACTIVE']

        # Count players ready for next phase (all active players who have submitted their prompts)
        players_ready = sum(1 for p in active_participants if p.prompts_submitted >= session.prompts_per_player)

        return StartPartyRoundResponse(
            round_id=str(round_obj.round_id),
            party_round_id=str(party_round_id),
            round_type='prompt',
            expires_at=round_obj.expires_at,
            cost=round_obj.cost,
            prompt_text=round_obj.prompt_text,
            status=round_obj.status,
            session_progress={
                'your_prompts_submitted': participant.prompts_submitted,
                'prompts_required': session.prompts_per_player,
                'players_done': players_ready,
                'total_players': len(active_participants),
            },
            party_context={
                'session_id': str(session_id),
                'current_phase': session.current_phase,
                'your_progress': {
                    'prompts_submitted': participant.prompts_submitted,
                    'prompts_required': session.prompts_per_player,
                    'copies_submitted': participant.copies_submitted,
                    'copies_required': session.copies_per_player,
                    'votes_submitted': participant.votes_submitted,
                    'votes_required': session.votes_per_player,
                },
                'session_progress': {
                    'players_ready_for_next_phase': players_ready,
                    'total_players': len(active_participants),
                },
            },
        )

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except WrongPhaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AlreadySubmittedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientBalanceError:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    except Exception as e:
        logger.error(f"Error starting party prompt round: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start prompt round")


@router.post("/{session_id}/rounds/copy", response_model=StartPartyRoundResponse)
async def start_party_copy_round(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a copy round within party context.

    Args:
        session_id: UUID of the party session

    Returns:
        StartPartyRoundResponse: Created round

    Raises:
        404: Session not found
        400: Wrong phase, already submitted, or no prompts available
    """
    try:
        transaction_service = TransactionService(db)
        coordination_service = PartyCoordinationService(db)

        # Start party copy round
        round_obj, party_round_id = await coordination_service.start_party_copy_round(
            session_id=session_id,
            player=player,
            transaction_service=transaction_service,
        )

        # Get session progress
        party_service = PartySessionService(db)
        participant = await party_service.get_participant(session_id, player.player_id)
        session = await party_service.get_session_by_id(session_id)
        all_participants = await party_service.get_participants(session_id)
        active_participants = [p for p in all_participants if p.status == 'ACTIVE']

        # Count players ready for next phase (all active players who have submitted their copies)
        players_ready = sum(1 for p in active_participants if p.copies_submitted >= session.copies_per_player)

        return StartPartyRoundResponse(
            round_id=str(round_obj.round_id),
            party_round_id=str(party_round_id),
            round_type='copy',
            expires_at=round_obj.expires_at,
            cost=round_obj.cost,
            original_phrase=round_obj.original_phrase,
            status=round_obj.status,
            session_progress={
                'your_copies_submitted': participant.copies_submitted,
                'copies_required': session.copies_per_player,
                'players_done': players_ready,
                'total_players': len(active_participants),
            },
            party_context={
                'session_id': str(session_id),
                'current_phase': session.current_phase,
                'your_progress': {
                    'prompts_submitted': participant.prompts_submitted,
                    'prompts_required': session.prompts_per_player,
                    'copies_submitted': participant.copies_submitted,
                    'copies_required': session.copies_per_player,
                    'votes_submitted': participant.votes_submitted,
                    'votes_required': session.votes_per_player,
                },
                'session_progress': {
                    'players_ready_for_next_phase': players_ready,
                    'total_players': len(active_participants),
                },
            },
        )

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except WrongPhaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AlreadySubmittedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NoPromptsAvailableError:
        raise HTTPException(status_code=400, detail="No prompts available for copying")
    except InsufficientBalanceError:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    except Exception as e:
        logger.error(f"Error starting party copy round: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start copy round")


@router.post("/{session_id}/rounds/vote", response_model=StartPartyRoundResponse)
async def start_party_vote_round(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Start a vote round within party context.

    Args:
        session_id: UUID of the party session

    Returns:
        StartPartyRoundResponse: Created round

    Raises:
        404: Session not found
        400: Wrong phase, already submitted, or no phrasesets available
    """
    try:
        transaction_service = TransactionService(db)
        coordination_service = PartyCoordinationService(db)

        # Start party vote round
        round_obj, party_round_id = await coordination_service.start_party_vote_round(
            session_id=session_id,
            player=player,
            transaction_service=transaction_service,
        )

        # Get session progress
        party_service = PartySessionService(db)
        participant = await party_service.get_participant(session_id, player.player_id)
        session = await party_service.get_session_by_id(session_id)
        all_participants = await party_service.get_participants(session_id)
        active_participants = [p for p in all_participants if p.status == 'ACTIVE']

        # Count players ready for next phase (all active players who have submitted their votes)
        players_ready = sum(1 for p in active_participants if p.votes_submitted >= session.votes_per_player)

        return StartPartyRoundResponse(
            round_id=str(round_obj.round_id),
            party_round_id=str(party_round_id),
            round_type='vote',
            expires_at=round_obj.expires_at,
            cost=settings.vote_cost,
            phraseset_id=round_obj.phraseset_id,
            prompt_text=round_obj.prompt_text,
            phrases=round_obj.phrases,
            status=round_obj.status,
            session_progress={
                'your_votes_submitted': participant.votes_submitted,
                'votes_required': session.votes_per_player,
                'players_done': players_ready,
                'total_players': len(active_participants),
            },
            party_context={
                'session_id': str(session_id),
                'current_phase': session.current_phase,
                'your_progress': {
                    'prompts_submitted': participant.prompts_submitted,
                    'prompts_required': session.prompts_per_player,
                    'copies_submitted': participant.copies_submitted,
                    'copies_required': session.copies_per_player,
                    'votes_submitted': participant.votes_submitted,
                    'votes_required': session.votes_per_player,
                },
                'session_progress': {
                    'players_ready_for_next_phase': players_ready,
                    'total_players': len(active_participants),
                },
            },
        )

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except WrongPhaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AlreadySubmittedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NoPhrasesetsAvailableError:
        raise HTTPException(status_code=400, detail="No phrasesets available for voting")
    except InsufficientBalanceError:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    except Exception as e:
        logger.error(f"Error starting party vote round: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start vote round")


@router.post("/{session_id}/rounds/{round_id}/submit", response_model=SubmitPartyRoundResponse)
async def submit_party_round(
    session_id: UUID,
    round_id: UUID,
    request: SubmitPartyRoundRequest,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Submit a party round (prompt, copy, or vote).

    Args:
        session_id: UUID of the party session
        round_id: UUID of the round
        request: Submission request with phrase

    Returns:
        SubmitPartyRoundResponse: Submission result

    Raises:
        404: Round not found
        400: Invalid phrase or round expired
    """
    try:
        coordination_service = PartyCoordinationService(db)

        # Determine round type and submit accordingly
        # For now, we'll use the coordination service to handle all submissions
        # This is a simplified approach - in production, you'd check round type first

        # For demonstration, let's assume the frontend knows which endpoint to call
        # and submits via the appropriate round type endpoint above
        # This is a catch-all that can work for any round type

        raise HTTPException(
            status_code=400,
            detail="Use specific round submission endpoints (prompt/copy/vote)"
        )

    except Exception as e:
        logger.error(f"Error submitting party round: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to submit round")


@router.post("/{session_id}/leave")
async def leave_party_session(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Leave a party session (lobby only).

    Args:
        session_id: UUID of the party session

    Returns:
        Success message

    Raises:
        404: Session not found
        400: Session already started
    """
    try:
        party_service = PartySessionService(db)

        # Get participant info before removal
        participant = await party_service.get_participant(session_id, player.player_id)
        if not participant:
            raise HTTPException(status_code=404, detail="Not in this session")

        # Remove participant (returns True if session was deleted)
        session_deleted = await party_service.remove_participant(
            session_id=session_id,
            player_id=player.player_id,
        )

        if session_deleted:
            # Last player left - session was deleted
            logger.info(f"Session {session_id} was deleted after last player left")
            return {
                "success": True,
                "message": "Left party session",
                "session_deleted": True,
            }

        # Session still exists - get status and broadcast
        status_data = await party_service.get_session_status(session_id)

        # Broadcast player left
        await ws_manager.notify_player_left(
            session_id=session_id,
            player_id=player.player_id,
            username=player.username,
            participant_count=len(status_data['participants']),
        )

        return {
            "success": True,
            "message": "Left party session",
            "session_deleted": False,
        }

    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")
    except SessionAlreadyStartedError:
        raise HTTPException(status_code=400, detail="Cannot leave session that has started")
    except Exception as e:
        logger.error(f"Error leaving party session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to leave session")


@router.websocket("/{session_id}/ws")
async def party_websocket_endpoint(
    websocket: WebSocket,
    session_id: UUID,
):
    """WebSocket endpoint for real-time party session updates.

    Requires authentication via token in query params (?token=...) or cookies.

    Args:
        websocket: WebSocket connection
        session_id: UUID of the party session
    """
    # Get token from query params or cookies
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.cookies.get(settings.access_token_cookie_name)

    if not token:
        logger.warning("Party WebSocket connection attempted without token")
        await websocket.close(code=4001, reason="No authentication token")
        return

    # Validate token and get player
    try:
        from backend.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            auth_service = AuthService(db, game_type=GameType.QF)
            payload = auth_service.decode_access_token(token)

            player_id_str = payload.get("sub")
            if not player_id_str:
                logger.warning("Party WebSocket token missing player_id")
                await websocket.close(code=4002, reason="Invalid token")
                return

            player_id = UUID(player_id_str)

            # Verify player is in this session
            party_service = PartySessionService(db)
            participant = await party_service.get_participant(session_id, player_id)

            if not participant:
                logger.warning(f"Player {player_id} attempted to connect to session they're not in")
                await websocket.close(code=4003, reason="Not a participant in this session")
                return

            context = websocket.query_params.get("context")

            # Connect WebSocket and update connection status
            await ws_manager.connect(session_id, player_id, websocket, db, context=context)
            logger.info(f"Party WebSocket connected for {player_id=} in session {session_id}")

            try:
                # Keep connection alive
                while True:
                    try:
                        # Wait for messages (we don't expect any, but this keeps connection alive)
                        await websocket.receive_text()
                    except WebSocketDisconnect:
                        break

            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"Party WebSocket error for {player_id=}: {e}", exc_info=True)
            finally:
                await ws_manager.disconnect(session_id, player_id, db, context=context)
                logger.info(f"Party WebSocket disconnected for {player_id=}")

    except Exception as e:
        logger.warning(f"Party WebSocket authentication failed: {e}")
        try:
            await websocket.close(code=4000, reason="Authentication failed")
        except Exception:
            pass  # Connection may already be closed
