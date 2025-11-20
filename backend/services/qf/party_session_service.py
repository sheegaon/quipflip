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
from backend.services.ai.ai_service import AI_PLAYER_EMAIL_DOMAIN
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


class AlreadyInAnotherSessionError(PartyModeError):
    """Raised when player tries to join a different session while active in one."""
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

    @staticmethod
    def _is_ai_player(player: QFPlayer | None) -> bool:
        """Determine whether a player account represents an AI participant."""
        if not player or not getattr(player, 'email', None):
            return False
        return player.email.lower().endswith(AI_PLAYER_EMAIL_DOMAIN)

    async def create_session(
        self,
        host_player_id: UUID,
        min_players: int = 6,
        max_players: int = 9,
        prompts_per_player: int = 1,
        copies_per_player: int = 2,
        votes_per_player: int = 3,
    ) -> PartySession:
        """Create a new party session with unique party code.

        Args:
            host_player_id: UUID of the host player
            min_players: Minimum players required to start (default: 6)
            max_players: Maximum players allowed (default: 9)
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
        now = datetime.now(UTC)
        participant = PartyParticipant(
            participant_id=uuid.uuid4(),
            session_id=session.session_id,
            player_id=host_player_id,
            status='READY',
            is_host=True,
            joined_at=now,
            ready_at=now,
            last_activity_at=now,
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
        # Subquery to get participant counts for all sessions
        participant_counts = (
            select(
                PartyParticipant.session_id,
                func.count(PartyParticipant.participant_id).label("participant_count"),
            )
            .group_by(PartyParticipant.session_id)
            .subquery()
        )

        # A single query to fetch all required data for open, non-full parties
        stmt = (
            select(
                PartySession.session_id,
                PartySession.max_players,
                PartySession.min_players,
                PartySession.created_at,
                QFPlayer.username.label("host_username"),
                func.coalesce(participant_counts.c.participant_count, 0).label("participant_count"),
            )
            .join(QFPlayer, PartySession.host_player_id == QFPlayer.player_id)
            .outerjoin(
                participant_counts,
                PartySession.session_id == participant_counts.c.session_id,
            )
            .where(PartySession.status == "OPEN")
            .where(
                func.coalesce(participant_counts.c.participant_count, 0)
                < PartySession.max_players
            )
            .order_by(PartySession.created_at.desc())
        )

        result = await self.db.execute(stmt)

        parties = [
            {
                'session_id': str(session.session_id),
                'host_username': session.host_username or "Unknown",
                'participant_count': session.participant_count,
                'min_players': session.min_players,
                'max_players': session.max_players,
                'created_at': session.created_at,
                'is_full': False,  # Already filtered by the query
            }
            for session in result.all()
        ]

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

        # Check if player is already in another active session
        active_session = await self.get_active_session_for_player(player_id)
        if active_session:
            raise AlreadyInAnotherSessionError(
                "Player is already participating in another active party session"
            )

        # Create participant
        now = datetime.now(UTC)
        participant = PartyParticipant(
            participant_id=uuid.uuid4(),
            session_id=session_id,
            player_id=player_id,
            status='READY',
            is_host=False,
            joined_at=now,
            ready_at=now,
            last_activity_at=now,
        )

        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)

        logger.info(f"Player {player_id} joined session {session_id}")
        return participant

    async def add_ai_player(
        self,
        session_id: UUID,
        host_player_id: UUID,
        game_type: "GameType",
    ) -> PartyParticipant:
        """Add an AI player to the session (host only, lobby only).

        Args:
            session_id: UUID of the session
            host_player_id: UUID of the host player (for verification)
            game_type: Game type for AI player creation

        Returns:
            PartyParticipant: Created AI participant

        Raises:
            SessionNotFoundError: If session doesn't exist
            NotHostError: If caller is not the host
            SessionAlreadyStartedError: If session has already started
            SessionFullError: If session is at max capacity
        """
        # Get session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Verify caller is host
        host_participant = await self.get_participant(session_id, host_player_id)
        if not host_participant or not host_participant.is_host:
            raise NotHostError("Only the host can add AI players")

        # Check if session has started
        if session.status != 'OPEN':
            raise SessionAlreadyStartedError("Cannot add AI players after session has started")

        # Check if session is full
        participant_count = await self._get_participant_count(session_id)
        if participant_count >= session.max_players:
            raise SessionFullError(f"Session is full (max {session.max_players} players)")

        # Get or create AI player
        from backend.services.ai.ai_service import AIService, AI_PLAYER_EMAIL_DOMAIN
        ai_player = await AIService(self.db).get_or_create_ai_player(
            game_type=game_type,
            email=f"ai_party_{uuid.uuid4().hex[:4]}{AI_PLAYER_EMAIL_DOMAIN}",
        )

        # Create participant
        participant = PartyParticipant(
            participant_id=uuid.uuid4(),
            session_id=session_id,
            player_id=ai_player.player_id,
            status='READY',  # AI players are always ready
            is_host=False,
            joined_at=datetime.now(UTC),
            ready_at=datetime.now(UTC),
            last_activity_at=datetime.now(UTC),
        )

        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)

        # Load the player relationship
        await self.db.refresh(participant, attribute_names=['player'])

        logger.info(f"AI player {ai_player.player_id} added to session {session_id}")
        return participant

    async def remove_participant(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> bool:
        """Remove a player from the session.

        Players can leave at any time, including during active games.
        If the host leaves, another participant is automatically promoted.

        Args:
            session_id: UUID of the session
            player_id: UUID of the player to remove

        Returns:
            bool: True if session was deleted (was empty), False otherwise

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        # Get session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

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

    async def remove_inactive_participants(self, session_id: UUID) -> List[Dict]:
        """Remove participants who have been inactive for more than 5 minutes.

        A participant is considered inactive if:
        - connection_status is 'disconnected' AND
        - last_activity_at is more than 5 minutes ago

        Uses batch operations for efficiency and atomicity.

        Args:
            session_id: UUID of the session to check

        Returns:
            List[Dict]: List of removed participants with their info
        """
        from backend.services.qf.party_websocket_manager import get_party_websocket_manager

        # Calculate cutoff time (5 minutes ago)
        cutoff_time = datetime.now(UTC) - timedelta(minutes=5)

        # Fetch all inactive participants with player info in a single query
        result = await self.db.execute(
            select(
                PartyParticipant.participant_id,
                PartyParticipant.player_id,
                PartyParticipant.is_host,
                QFPlayer.username,
            )
            .join(QFPlayer, PartyParticipant.player_id == QFPlayer.player_id)
            .where(
                and_(
                    PartyParticipant.session_id == session_id,
                    PartyParticipant.connection_status == 'disconnected',
                    PartyParticipant.last_activity_at < cutoff_time
                )
            )
        )
        inactive_rows = result.all()

        if not inactive_rows:
            return []

        # Process in memory to prepare for batch operations
        removed_participants = []
        participant_ids_to_delete = []
        any_host_removed = False

        for row in inactive_rows:
            participant_ids_to_delete.append(row.participant_id)
            removed_participants.append({
                'player_id': str(row.player_id),
                'username': row.username,
                'was_host': row.is_host,
            })
            if row.is_host:
                any_host_removed = True

        # Batch delete all inactive participants in a single operation
        if participant_ids_to_delete:
            await self.db.execute(
                select(PartyParticipant)
                .where(PartyParticipant.participant_id.in_(participant_ids_to_delete))
            )
            # Use delete() with synchronize_session=False for better performance
            from sqlalchemy import delete as sql_delete
            await self.db.execute(
                sql_delete(PartyParticipant)
                .where(PartyParticipant.participant_id.in_(participant_ids_to_delete))
                .execution_options(synchronize_session=False)
            )

        # Check if session is now empty
        remaining_count = await self._get_participant_count(session_id)

        if remaining_count == 0:
            # Session is empty - delete it
            await self._delete_empty_session(session_id)
            # Don't commit yet - _delete_empty_session handles its own commit
            logger.info(f"Removed {len(removed_participants)} inactive participants from session {session_id} (session deleted)")
            return removed_participants

        # Handle host reassignment if needed
        new_host_info = None
        if any_host_removed:
            # Reassign host to oldest remaining participant
            await self._reassign_host(session_id)

            # Get new host info for notification
            new_host_result = await self.db.execute(
                select(
                    PartyParticipant.player_id,
                    QFPlayer.username,
                )
                .join(QFPlayer, PartyParticipant.player_id == QFPlayer.player_id)
                .where(
                    and_(
                        PartyParticipant.session_id == session_id,
                        PartyParticipant.is_host == True
                    )
                )
            )
            new_host_row = new_host_result.first()
            if new_host_row:
                new_host_info = {
                    'player_id': str(new_host_row.player_id),
                    'username': new_host_row.username,
                }

        # Commit all database changes in a single transaction
        await self.db.commit()

        logger.info(f"Removed {len(removed_participants)} inactive participants from session {session_id}")

        # Send WebSocket notifications after successful commit
        ws_manager = get_party_websocket_manager()

        for participant in removed_participants:
            await ws_manager.notify_player_left(
                session_id=session_id,
                player_id=UUID(participant['player_id']),
                username=participant['username'],
                participant_count=remaining_count,
            )

        # Send host change notification if applicable
        if new_host_info:
            await ws_manager.notify_session_update(
                session_id=session_id,
                session_status={
                    'new_host_player_id': new_host_info['player_id'],
                    'new_host_username': new_host_info['username'],
                    'reason': 'inactive_player_removed',
                    'message': f"{new_host_info['username']} is now the host"
                }
            )

        return removed_participants

    async def cleanup_inactive_sessions(self) -> Dict[str, int]:
        """Clean up inactive participants across all open sessions."""
        result = await self.db.execute(
            select(PartySession.session_id).where(PartySession.status == 'OPEN')
        )
        session_ids = [row.session_id for row in result]

        participants_removed = 0
        sessions_deleted = 0

        for session_id in session_ids:
            removed = await self.remove_inactive_participants(session_id)
            participants_removed += len(removed)
            session_exists = await self.get_session_by_id(session_id)
            if not session_exists:
                sessions_deleted += 1

        return {
            'sessions_checked': len(session_ids),
            'participants_removed': participants_removed,
            'sessions_deleted': sessions_deleted,
        }

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

    async def get_active_session_for_player(
        self,
        player_id: UUID,
    ) -> Optional[PartySession]:
        """Return an active session that already includes the player."""

        result = await self.db.execute(
            select(PartySession)
            .join(PartyParticipant, PartyParticipant.session_id == PartySession.session_id)
            .where(PartyParticipant.player_id == player_id)
            .where(PartySession.status.in_(['OPEN', 'IN_PROGRESS']))
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
                'is_ai': self._is_ai_player(player),
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

        # Update the round record to reference party_round_id for fast lookup
        round_result = await self.db.execute(
            select(Round).where(Round.round_id == round_id)
        )
        round_obj = round_result.scalar_one_or_none()
        if round_obj:
            round_obj.party_round_id = party_round.party_round_id

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
