"""Party Mode service for managing party sessions."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, UTC, timedelta
from typing import Optional, List, Dict
from uuid import UUID
import uuid
import logging
import random
import string

from backend.models.qf.player import QFPlayer
from backend.models.qf.party_session import PartySession
from backend.models.qf.party_participant import PartyParticipant
from backend.models.qf.party_round import PartyRound
from backend.models.qf.party_phraseset import PartyPhraseset
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.config import get_settings
from backend.utils.exceptions import QuipflipException

logger = logging.getLogger(__name__)
settings = get_settings()


# Custom exceptions for Party Mode
class PartyModeError(QuipflipException):
    """Base exception for Party Mode errors."""
    pass


class SessionNotFoundError(PartyModeError):
    """Raised when party session is not found."""
    pass


class SessionAlreadyStartedError(PartyModeError):
    """Raised when trying to join/modify a session that has already started."""
    pass


class SessionFullError(PartyModeError):
    """Raised when trying to join a full session."""
    pass


class AlreadyInSessionError(PartyModeError):
    """Raised when player tries to join a session they're already in."""
    pass


class NotHostError(PartyModeError):
    """Raised when non-host tries to perform host-only action."""
    pass


class NotEnoughPlayersError(PartyModeError):
    """Raised when trying to start with insufficient players."""
    pass


class WrongPhaseError(PartyModeError):
    """Raised when action attempted in wrong party phase."""
    pass


class AlreadySubmittedError(PartyModeError):
    """Raised when player has already submitted required rounds for current phase."""
    pass


class PartySessionService:
    """Service for managing party sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create_session(
        self,
        host_player_id: UUID,
        min_players: int = 3,
        max_players: int = 8,
        prompts_per_player: int = 1,
        copies_per_player: int = 2,
        votes_per_player: int = 3,
    ) -> PartySession:
        """Create a new party session with unique party code.

        Args:
            host_player_id: UUID of the host player
            min_players: Minimum players required to start (default: 3)
            max_players: Maximum players allowed (default: 8)
            prompts_per_player: Number of prompts each player must submit (default: 1)
            copies_per_player: Number of copies each player must submit (default: 2)
            votes_per_player: Number of votes each player must submit (default: 3)

        Returns:
            PartySession: Created session

        Raises:
            PartyModeError: If session creation fails
        """
        # Generate unique party code
        party_code = await self._generate_unique_party_code()

        # Create session
        session = PartySession(
            session_id=uuid.uuid4(),
            party_code=party_code,
            host_player_id=host_player_id,
            min_players=min_players,
            max_players=max_players,
            prompts_per_player=prompts_per_player,
            copies_per_player=copies_per_player,
            votes_per_player=votes_per_player,
            current_phase='LOBBY',
            status='OPEN',
            created_at=datetime.now(UTC),
        )

        self.db.add(session)

        # Add host as first participant
        participant = PartyParticipant(
            participant_id=uuid.uuid4(),
            session_id=session.session_id,
            player_id=host_player_id,
            status='JOINED',
            is_host=True,
            joined_at=datetime.now(UTC),
        )

        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Created party session {session.session_id} with code {party_code}")
        return session

    async def _generate_unique_party_code(self, max_attempts: int = 3) -> str:
        """Generate a unique party code.

        Format: ABCD1234 (4 letters + 4 digits, excluding ambiguous chars)

        Args:
            max_attempts: Maximum retry attempts if collision occurs

        Returns:
            str: Unique 8-character party code

        Raises:
            PartyModeError: If unable to generate unique code after max_attempts
        """
        # Exclude ambiguous characters: O, I, L, 0, 1
        letters = string.ascii_uppercase.replace('O', '').replace('I', '').replace('L', '')
        digits = string.digits.replace('0', '').replace('1', '')

        for attempt in range(max_attempts):
            # Generate 4 letters + 4 digits
            code_letters = ''.join(random.choices(letters, k=4))
            code_digits = ''.join(random.choices(digits, k=4))
            party_code = code_letters + code_digits

            # Check if code already exists
            result = await self.db.execute(
                select(PartySession).where(PartySession.party_code == party_code)
            )
            existing = result.scalar_one_or_none()

            if not existing:
                return party_code

        raise PartyModeError("Failed to generate unique party code after maximum attempts")

    async def get_session_by_id(self, session_id: UUID) -> Optional[PartySession]:
        """Get session by ID.

        Args:
            session_id: UUID of the session

        Returns:
            PartySession or None if not found
        """
        result = await self.db.execute(
            select(PartySession).where(PartySession.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_session_by_code(self, party_code: str) -> Optional[PartySession]:
        """Get session by party code.

        Args:
            party_code: Party code string

        Returns:
            PartySession or None if not found
        """
        result = await self.db.execute(
            select(PartySession).where(PartySession.party_code == party_code)
        )
        return result.scalar_one_or_none()

    async def list_active_parties(self) -> List[Dict]:
        """Get list of all joinable party sessions.

        Returns only sessions that are:
        - In OPEN status (lobby, not started)
        - Not full (participant_count < max_players)
        - Ordered by created_at desc (newest first)

        Returns:
            List[Dict]: List of party session summaries
        """
        from backend.schemas.party import PartyListItemResponse

        # Query sessions with participant counts
        result = await self.db.execute(
            select(
                PartySession.session_id,
                PartySession.max_players,
                PartySession.min_players,
                PartySession.created_at,
                func.count(PartyParticipant.participant_id).label('participant_count')
            )
            .outerjoin(PartyParticipant, PartySession.session_id == PartyParticipant.session_id)
            .where(PartySession.status == 'OPEN')
            .group_by(PartySession.session_id)
            .order_by(PartySession.created_at.desc())
        )

        sessions = result.all()

        # Build response list
        parties = []
        for session in sessions:
            # Get host username
            host_result = await self.db.execute(
                select(QFPlayer.username)
                .join(PartyParticipant, PartyParticipant.player_id == QFPlayer.player_id)
                .where(
                    and_(
                        PartyParticipant.session_id == session.session_id,
                        PartyParticipant.is_host == True
                    )
                )
            )
            host_username = host_result.scalar_one_or_none() or "Unknown"

            is_full = session.participant_count >= session.max_players

            # Only include non-full sessions
            if not is_full:
                parties.append(
                    PartyListItemResponse(
                        session_id=str(session.session_id),
                        host_username=host_username,
                        participant_count=session.participant_count,
                        min_players=session.min_players,
                        max_players=session.max_players,
                        created_at=session.created_at,
                        is_full=is_full,
                    )
                )

        return parties

    async def add_participant(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> PartyParticipant:
        """Add a player to the session.

        Args:
            session_id: UUID of the session
            player_id: UUID of the player to add

        Returns:
            PartyParticipant: Created participant

        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionAlreadyStartedError: If session has already started
            SessionFullError: If session is at max capacity
            AlreadyInSessionError: If player is already in session
        """
        # Get session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Check if session has started
        if session.status != 'OPEN':
            raise SessionAlreadyStartedError("Cannot join session that has already started")

        # Check if session is full
        participant_count = await self._get_participant_count(session_id)
        if participant_count >= session.max_players:
            raise SessionFullError(f"Session is full (max {session.max_players} players)")

        # Check if player is already in session
        existing_participant = await self.get_participant(session_id, player_id)
        if existing_participant:
            raise AlreadyInSessionError("Player is already in this session")

        # Create participant
        participant = PartyParticipant(
            participant_id=uuid.uuid4(),
            session_id=session_id,
            player_id=player_id,
            status='JOINED',
            is_host=False,
            joined_at=datetime.now(UTC),
        )

        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)

        logger.info(f"Player {player_id} joined session {session_id}")
        return participant

    async def remove_participant(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> bool:
        """Remove a player from the session (lobby only).

        Args:
            session_id: UUID of the session
            player_id: UUID of the player to remove

        Returns:
            bool: True if session was deleted (was empty), False otherwise

        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionAlreadyStartedError: If session has already started
        """
        # Get session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Can only remove from lobby
        if session.status != 'OPEN':
            raise SessionAlreadyStartedError("Cannot leave session that has already started")

        # Get participant
        participant = await self.get_participant(session_id, player_id)
        if participant:
            was_host = participant.is_host

            await self.db.delete(participant)
            await self.db.commit()

            logger.info(f"Player {player_id} left session {session_id}")

            # Check if any participants remain
            remaining_count = await self._get_participant_count(session_id)

            if remaining_count == 0:
                # Last player left - delete the session
                await self._delete_empty_session(session_id)
                return True
            elif was_host:
                # Host left but others remain - reassign host
                await self._reassign_host(session_id)

            return False

        return False

    async def _reassign_host(self, session_id: UUID) -> None:
        """Reassign host to another participant if host leaves.

        Args:
            session_id: UUID of the session
        """
        # Get remaining participants
        result = await self.db.execute(
            select(PartyParticipant)
            .where(PartyParticipant.session_id == session_id)
            .order_by(PartyParticipant.joined_at)
        )
        participants = result.scalars().all()

        if participants:
            # Make first participant the new host
            new_host = participants[0]
            new_host.is_host = True
            await self.db.commit()
            logger.info(f"Reassigned host to player {new_host.player_id} in session {session_id}")

    async def _get_participant_count(self, session_id: UUID) -> int:
        """Get count of participants in a session.

        Args:
            session_id: UUID of the session

        Returns:
            int: Number of participants
        """
        from sqlalchemy import func

        result = await self.db.execute(
            select(func.count(PartyParticipant.participant_id))
            .where(PartyParticipant.session_id == session_id)
        )
        count = result.scalar()
        return count or 0

    async def _delete_empty_session(self, session_id: UUID) -> None:
        """Delete a party session when it becomes empty.

        This method deletes the session and all related data via cascade.
        Related data includes: PartyParticipant, PartyRound, PartyPhraseset.

        Args:
            session_id: UUID of the session to delete
        """
        session = await self.get_session_by_id(session_id)
        if session:
            await self.db.delete(session)
            await self.db.commit()
            logger.info(f"Deleted empty party session {session_id}")

    async def mark_participant_ready(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> PartyParticipant:
        """Mark participant as ready in lobby.

        Args:
            session_id: UUID of the session
            player_id: UUID of the player

        Returns:
            PartyParticipant: Updated participant

        Raises:
            SessionNotFoundError: If session doesn't exist
            SessionAlreadyStartedError: If session has already started
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.status != 'OPEN':
            raise SessionAlreadyStartedError("Session has already started")

        participant = await self.get_participant(session_id, player_id)
        if not participant:
            raise PartyModeError(f"Player {player_id} not in session")

        participant.status = 'READY'
        participant.ready_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(participant)

        logger.info(f"Player {player_id} marked ready in session {session_id}")
        return participant

    async def start_session(self, session_id: UUID, requesting_player_id: UUID) -> PartySession:
        """Start the party session (host only).

        Args:
            session_id: UUID of the session
            requesting_player_id: UUID of the player requesting start

        Returns:
            PartySession: Updated session

        Raises:
            SessionNotFoundError: If session doesn't exist
            NotHostError: If requester is not the host
            NotEnoughPlayersError: If below minimum player count
            SessionAlreadyStartedError: If session already started
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.status != 'OPEN':
            raise SessionAlreadyStartedError("Session has already started")

        # Check if requester is host
        host_participant = await self.get_participant(session_id, requesting_player_id)
        if not host_participant or not host_participant.is_host:
            raise NotHostError("Only the host can start the session")

        # Check minimum player count
        participant_count = await self._get_participant_count(session_id)
        if participant_count < session.min_players:
            raise NotEnoughPlayersError(
                f"Need at least {session.min_players} players (currently {participant_count})"
            )

        # Start session
        session.status = 'IN_PROGRESS'
        session.current_phase = 'PROMPT'
        session.started_at = datetime.now(UTC)
        session.locked_at = datetime.now(UTC)
        session.phase_started_at = datetime.now(UTC)

        # Update all participants to ACTIVE
        await self.db.execute(
            PartyParticipant.__table__.update()
            .where(PartyParticipant.session_id == session_id)
            .values(status='ACTIVE')
        )

        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Started session {session_id} with {participant_count} players")
        return session

    async def advance_phase(self, session_id: UUID) -> PartySession:
        """Advance session to next phase.

        Phase progression: LOBBY → PROMPT → COPY → VOTE → RESULTS

        Args:
            session_id: UUID of the session

        Returns:
            PartySession: Updated session

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Determine next phase
        phase_progression = {
            'LOBBY': 'PROMPT',
            'PROMPT': 'COPY',
            'COPY': 'VOTE',
            'VOTE': 'RESULTS',
            'RESULTS': 'COMPLETED',
        }

        new_phase = phase_progression.get(session.current_phase)
        if not new_phase:
            logger.warning(f"Cannot advance from phase {session.current_phase}")
            return session

        # Update session
        session.current_phase = new_phase
        session.phase_started_at = datetime.now(UTC)

        # If moving to RESULTS, mark session as completed
        if new_phase == 'RESULTS':
            session.completed_at = datetime.now(UTC)

        # If moving to COMPLETED, update status
        if new_phase == 'COMPLETED':
            session.status = 'COMPLETED'

        # If moving to VOTE, mark all party phrasesets as available for voting
        if new_phase == 'VOTE':
            await self._mark_phrasesets_available_for_voting(session_id)

        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Advanced session {session_id} to phase {new_phase}")
        return session

    async def _mark_phrasesets_available_for_voting(self, session_id: UUID) -> None:
        """Mark all party phrasesets as available for voting.

        Args:
            session_id: UUID of the session
        """
        await self.db.execute(
            PartyPhraseset.__table__.update()
            .where(PartyPhraseset.session_id == session_id)
            .values(available_for_voting=True)
        )
        await self.db.commit()

    async def can_advance_phase(self, session_id: UUID) -> bool:
        """Check if all participants have completed current phase.

        Args:
            session_id: UUID of the session

        Returns:
            bool: True if all participants done with current phase
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            return False

        # Get all participants
        result = await self.db.execute(
            select(PartyParticipant)
            .where(PartyParticipant.session_id == session_id)
            .where(PartyParticipant.status == 'ACTIVE')
        )
        participants = result.scalars().all()

        if not participants:
            return False

        # Check completion based on phase
        if session.current_phase == 'PROMPT':
            required = session.prompts_per_player
            return all(p.prompts_submitted >= required for p in participants)

        elif session.current_phase == 'COPY':
            required = session.copies_per_player
            return all(p.copies_submitted >= required for p in participants)

        elif session.current_phase == 'VOTE':
            required = session.votes_per_player
            return all(p.votes_submitted >= required for p in participants)

        return False

    async def get_participant(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> Optional[PartyParticipant]:
        """Get participant by session and player ID.

        Args:
            session_id: UUID of the session
            player_id: UUID of the player

        Returns:
            PartyParticipant or None if not found
        """
        result = await self.db.execute(
            select(PartyParticipant)
            .where(PartyParticipant.session_id == session_id)
            .where(PartyParticipant.player_id == player_id)
        )
        return result.scalar_one_or_none()

    async def _get_participant_count(self, session_id: UUID) -> int:
        """Get count of participants in session.

        Args:
            session_id: UUID of the session

        Returns:
            int: Number of participants
        """
        result = await self.db.execute(
            select(func.count(PartyParticipant.participant_id))
            .where(PartyParticipant.session_id == session_id)
        )
        return result.scalar() or 0

    async def get_participants(self, session_id: UUID) -> List[PartyParticipant]:
        """Get all participants in session.

        Args:
            session_id: UUID of the session

        Returns:
            List[PartyParticipant]: List of participants
        """
        result = await self.db.execute(
            select(PartyParticipant)
            .where(PartyParticipant.session_id == session_id)
            .order_by(PartyParticipant.joined_at)
        )
        return list(result.scalars().all())

    async def get_session_status(self, session_id: UUID) -> Dict:
        """Get full session status including participants and progress.

        Args:
            session_id: UUID of the session

        Returns:
            dict: Complete session status

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Get participants with player info
        result = await self.db.execute(
            select(PartyParticipant, QFPlayer)
            .join(QFPlayer, PartyParticipant.player_id == QFPlayer.player_id)
            .where(PartyParticipant.session_id == session_id)
            .order_by(PartyParticipant.joined_at)
        )
        participants_data = result.all()

        participants_info = []
        for participant, player in participants_data:
            participants_info.append({
                'participant_id': str(participant.participant_id),
                'player_id': str(participant.player_id),
                'username': player.username,
                'is_host': participant.is_host,
                'status': participant.status,
                'prompts_submitted': participant.prompts_submitted,
                'copies_submitted': participant.copies_submitted,
                'votes_submitted': participant.votes_submitted,
                'prompts_required': session.prompts_per_player,
                'copies_required': session.copies_per_player,
                'votes_required': session.votes_per_player,
                'joined_at': participant.joined_at.isoformat() if participant.joined_at else None,
                'ready_at': participant.ready_at.isoformat() if participant.ready_at else None,
            })

        # Calculate progress
        total_prompts = sum(p['prompts_submitted'] for p in participants_info)
        total_copies = sum(p['copies_submitted'] for p in participants_info)
        total_votes = sum(p['votes_submitted'] for p in participants_info)

        required_prompts = session.prompts_per_player * len(participants_info)
        required_copies = session.copies_per_player * len(participants_info)
        required_votes = session.votes_per_player * len(participants_info)

        players_ready_for_next = sum(
            1 for p in participants_info
            if (session.current_phase == 'PROMPT' and p['prompts_submitted'] >= session.prompts_per_player) or
               (session.current_phase == 'COPY' and p['copies_submitted'] >= session.copies_per_player) or
               (session.current_phase == 'VOTE' and p['votes_submitted'] >= session.votes_per_player) or
               (session.current_phase == 'LOBBY' and p['status'] == 'READY')
        )

        return {
            'session_id': str(session.session_id),
            'party_code': session.party_code,
            'host_player_id': str(session.host_player_id),
            'status': session.status,
            'current_phase': session.current_phase,
            'min_players': session.min_players,
            'max_players': session.max_players,
            'phase_started_at': session.phase_started_at.isoformat() if session.phase_started_at else None,
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'completed_at': session.completed_at.isoformat() if session.completed_at else None,
            'participants': participants_info,
            'progress': {
                'total_prompts': total_prompts,
                'total_copies': total_copies,
                'total_votes': total_votes,
                'required_prompts': required_prompts,
                'required_copies': required_copies,
                'required_votes': required_votes,
                'players_ready_for_next_phase': players_ready_for_next,
                'total_players': len(participants_info),
            },
        }

    async def link_round_to_party(
        self,
        session_id: UUID,
        player_id: UUID,
        round_id: UUID,
        round_type: str,
        phase: str,
    ) -> PartyRound:
        """Link a round to party session without incrementing progress counters.

        Use this when a round starts (before submission).

        Args:
            session_id: UUID of the session
            player_id: UUID of the player
            round_id: UUID of the round
            round_type: Type of round ('prompt', 'copy', 'vote')
            phase: Current phase ('PROMPT', 'COPY', 'VOTE')

        Returns:
            PartyRound: Created party round link
        """
        # Get participant
        participant = await self.get_participant(session_id, player_id)
        if not participant:
            raise PartyModeError(f"Player {player_id} not in session {session_id}")

        # Create party round link
        party_round = PartyRound(
            party_round_id=uuid.uuid4(),
            session_id=session_id,
            round_id=round_id,
            participant_id=participant.participant_id,
            round_type=round_type,
            phase=phase,
            created_at=datetime.now(UTC),
        )

        self.db.add(party_round)
        participant.last_activity_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(party_round)

        logger.info(f"Linked {round_type} round {round_id} to party session {session_id}")
        return party_round

    async def increment_participant_progress(
        self,
        session_id: UUID,
        player_id: UUID,
        round_type: str,
    ) -> PartyParticipant:
        """Increment participant progress counter after successful round submission.

        Use this when a round is successfully submitted.

        Args:
            session_id: UUID of the session
            player_id: UUID of the player
            round_type: Type of round ('prompt', 'copy', 'vote')

        Returns:
            PartyParticipant: Updated participant
        """
        # Get participant
        participant = await self.get_participant(session_id, player_id)
        if not participant:
            raise PartyModeError(f"Player {player_id} not in session {session_id}")

        # Increment appropriate counter
        if round_type == 'prompt':
            participant.prompts_submitted += 1
        elif round_type == 'copy':
            participant.copies_submitted += 1
        elif round_type == 'vote':
            participant.votes_submitted += 1

        participant.last_activity_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(participant)

        logger.info(
            f"Incremented {round_type} progress for player {player_id} in session {session_id} "
            f"(now {participant.prompts_submitted}/{participant.copies_submitted}/{participant.votes_submitted})"
        )
        return participant

    async def link_phraseset_to_party(
        self,
        session_id: UUID,
        phraseset_id: UUID,
        created_in_phase: str,
    ) -> PartyPhraseset:
        """Link phraseset to party session.

        Args:
            session_id: UUID of the session
            phraseset_id: UUID of the phraseset
            created_in_phase: Phase where phraseset was created

        Returns:
            PartyPhraseset: Created party phraseset link
        """
        party_phraseset = PartyPhraseset(
            party_phraseset_id=uuid.uuid4(),
            session_id=session_id,
            phraseset_id=phraseset_id,
            created_in_phase=created_in_phase,
            available_for_voting=False,
            created_at=datetime.now(UTC),
        )

        self.db.add(party_phraseset)
        await self.db.commit()
        await self.db.refresh(party_phraseset)

        logger.info(f"Linked phraseset {phraseset_id} to session {session_id}")
        return party_phraseset
