"""Party Mode service for managing party sessions."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm.exc import StaleDataError
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
from backend.config import get_settings
from backend.services.ai.ai_service import AI_PLAYER_EMAIL_DOMAIN
from backend.utils.exceptions import QuipflipException
from backend.utils.model_registry import GameType, AIPlayerType

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
    def _next_phase(current_phase: str) -> Optional[str]:
        """Return the next gameplay phase, if any."""
        return {
            'LOBBY': 'PROMPT',
            'PROMPT': 'COPY',
            'COPY': 'VOTE',
            'VOTE': 'RESULTS',
        }.get(current_phase)

    def _phase_duration_seconds(self, phase: str) -> Optional[int]:
        """Return the configured duration for a timed party phase."""
        if phase == 'PROMPT':
            return self.settings.prompt_round_seconds
        if phase == 'COPY':
            return self.settings.copy_round_seconds
        if phase == 'VOTE':
            return self.settings.vote_round_seconds
        return None

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
        # Prevent creating multiple active sessions per player
        existing_session = await self.get_active_session_for_player(host_player_id)
        if existing_session:
            raise AlreadyInAnotherSessionError(
                f"Player {host_player_id} is already in an active party session"
            )

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
        - Have at least one human player (AI players don't count)
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

        # Subquery to count human participants (non-AI) per session
        human_participant_counts = (
            select(
                PartyParticipant.session_id,
                func.count(PartyParticipant.participant_id).label("human_count"),
            )
            .join(QFPlayer, PartyParticipant.player_id == QFPlayer.player_id)
            .where(~QFPlayer.email.ilike(f'%{AI_PLAYER_EMAIL_DOMAIN}'))
            .group_by(PartyParticipant.session_id)
            .subquery()
        )

        # A single query to fetch all required data for open, non-full parties with human players
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
            .outerjoin(
                human_participant_counts,
                PartySession.session_id == human_participant_counts.c.session_id,
            )
            .where(PartySession.status == "OPEN")
            .where(
                func.coalesce(participant_counts.c.participant_count, 0)
                < PartySession.max_players
            )
            .where(
                func.coalesce(human_participant_counts.c.human_count, 0) > 0
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
            status='JOINED',
            is_host=False,
            joined_at=now,
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
        game_type: GameType | None = None,
    ) -> PartyParticipant:
        """Add an AI player to the session (host only, lobby only).

        Args:
            session_id: UUID of the session
            host_player_id: UUID of the host player (for verification)

        Returns:
            PartyParticipant: Created AI participant

        Raises:
            SessionNotFoundError: If session doesn't exist
            NotHostError: If caller is not the host
            SessionAlreadyStartedError: If session has already started
            SessionFullError: If session is at max capacity
        """
        _ = game_type

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
        result = await self.db.execute(
            select(PartyParticipant.player_id).join(PartySession).where(
                PartySession.status.in_(['OPEN', 'IN_PROGRESS']),
                QFPlayer.email.like(f"ai_party_%{AI_PLAYER_EMAIL_DOMAIN}"))
        )
        active_pool_players = list({row.player_id for row in result.fetchall()})
        ai_player = await AIService(self.db, allow_no_provider=True).get_or_create_ai_player(
            AIPlayerType.QF_PARTY,
            excluded=active_pool_players,
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
        """Remove a player from the lobby.

        Mid-game leave is intentionally rejected until the Party forfeiture policy
        is explicitly approved. If the host leaves, another participant is
        automatically promoted. Session is deleted when the last HUMAN player
        leaves (AI players don't keep session alive).

        Args:
            session_id: UUID of the session
            player_id: UUID of the player to remove

        Returns:
            bool: True if session was deleted, False otherwise

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        # Get session
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.status != 'OPEN':
            raise SessionAlreadyStartedError("Cannot leave session that has already started")

        # Get participant
        participant = await self.get_participant(session_id, player_id)
        if participant:
            was_host = participant.is_host

            await self.db.delete(participant)
            await self.db.commit()

            logger.info(f"Player {player_id} left session {session_id}")

            # Check if any HUMAN participants remain
            # Sessions are deleted when there are no human players left, regardless of AI players
            remaining_human_count = await self._get_human_participant_count(session_id)

            if remaining_human_count == 0:
                # Last human player left - delete the session
                logger.info(f"No human players remaining in session {session_id}, deleting session")
                await self._delete_empty_session(session_id)
                return True
            elif was_host:
                # Host left but others remain - reassign host to another human if possible
                await self._reassign_host(session_id)

            return False

        return False

    async def _reassign_host(self, session_id: UUID) -> None:
        """Reassign host to another participant if host leaves.

        Prefers human players over AI players when reassigning host role.

        Args:
            session_id: UUID of the session
        """
        # Get remaining participants with player info
        result = await self.db.execute(
            select(PartyParticipant, QFPlayer)
            .join(QFPlayer, PartyParticipant.player_id == QFPlayer.player_id)
            .where(PartyParticipant.session_id == session_id)
            .order_by(PartyParticipant.joined_at)
        )
        participants_data = result.all()

        if participants_data:
            # Prefer human players as new host
            new_host = None
            for participant, player in participants_data:
                if not self._is_ai_player(player):
                    new_host = participant
                    break

            # If no human players found, use first AI player
            if not new_host and participants_data:
                new_host = participants_data[0][0]

            if new_host:
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
        """Retain inactive participants so reconnect can restore them.

        This method now only preserves the historical contract for callers that
        still expect a list-like return value. Inactive participant cleanup is
        intentionally disabled in Party Mode.
        """
        logger.info(
            "Inactive participant cleanup is disabled for session %s; reconnect should restore membership",
            session_id,
        )
        return []

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

        if participant.status == 'READY':
            participant.last_activity_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(participant)
            logger.info(f"Player {player_id} already ready in session {session_id}")
            return participant

        participant.status = 'READY'
        participant.ready_at = datetime.now(UTC)
        participant.last_activity_at = datetime.now(UTC)
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

        # Check minimum ready player count
        ready_count_result = await self.db.execute(
            select(func.count(PartyParticipant.participant_id))
            .where(PartyParticipant.session_id == session_id)
            .where(PartyParticipant.status == 'READY')
        )
        ready_count = ready_count_result.scalar() or 0
        if ready_count < session.min_players:
            raise NotEnoughPlayersError(
                f"Need at least {session.min_players} ready players (currently {ready_count})"
            )

        now = datetime.now(UTC)
        # Start session
        session.status = 'IN_PROGRESS'
        session.current_phase = 'PROMPT'
        session.started_at = now
        session.locked_at = now
        session.phase_started_at = now
        session.phase_expires_at = now + timedelta(seconds=self._phase_duration_seconds('PROMPT') or 0)

        # Update all participants to ACTIVE
        await self.db.execute(
            PartyParticipant.__table__.update()
            .where(PartyParticipant.session_id == session_id)
            .values(status='ACTIVE')
        )

        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Started session {session_id} with {ready_count} ready players")
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
        new_phase = self._next_phase(session.current_phase)
        if not new_phase:
            logger.warning(f"Cannot advance from phase {session.current_phase}")
            return session

        now = datetime.now(UTC)
        # Update session
        session.current_phase = new_phase
        session.phase_started_at = now

        if new_phase in {'PROMPT', 'COPY', 'VOTE'}:
            duration = self._phase_duration_seconds(new_phase)
            session.status = 'IN_PROGRESS'
            session.phase_expires_at = now + timedelta(seconds=duration) if duration else None
            session.completed_at = None
        else:
            session.status = 'COMPLETED'
            session.phase_expires_at = None
            session.completed_at = now

        # If moving to VOTE, mark all party phrasesets as available for voting
        if new_phase == 'VOTE':
            await self._mark_phrasesets_available_for_voting(session_id)

        await self.db.commit()
        await self.db.refresh(session)

        logger.info(f"Advanced session {session_id} to phase {new_phase}")
        return session

    async def _mark_phrasesets_available_for_voting(self, session_id: UUID) -> None:
        """Stage Party phrasesets as available in the caller's transaction.

        Args:
            session_id: UUID of the session
        """
        await self.db.execute(
            PartyPhraseset.__table__.update()
            .where(PartyPhraseset.session_id == session_id)
            .values(available_for_voting=True)
        )

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
            result = all(p.prompts_submitted >= required for p in participants)
            logger.info(
                f"can_advance_phase(PROMPT): {len(participants)} participants, "
                f"required={required}, result={result}, "
                f"progress={[(p.player_id, p.prompts_submitted) for p in participants]}"
            )
            return result

        elif session.current_phase == 'COPY':
            required = session.copies_per_player
            result = all(p.copies_submitted >= required for p in participants)
            logger.info(
                f"can_advance_phase(COPY): {len(participants)} participants, "
                f"required={required}, result={result}"
            )
            return result

        elif session.current_phase == 'VOTE':
            required = session.votes_per_player
            result = all(p.votes_submitted >= required for p in participants)
            logger.info(
                f"can_advance_phase(VOTE): {len(participants)} participants, "
                f"required={required}, result={result}"
            )
            return result

        return False

    async def advance_phase_atomic(self, session_id: UUID) -> Optional[PartySession]:
        """Advance phase with optimistic concurrency.

        Args:
            session_id: UUID of the session

        Returns:
            PartySession if phase was advanced, None if already advanced

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = await self.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if not await self.can_advance_phase(session_id):
            logger.debug(f"Phase already advanced or not ready for session {session_id}")
            return None

        original_phase = session.current_phase
        original_version = session.version

        try:
            advanced_session = await self.advance_phase(session_id)
            logger.info(
                "Advanced party session %s atomically from %s at version %s",
                session_id,
                original_phase,
                original_version,
            )
            return advanced_session
        except StaleDataError:
            await self.db.rollback()
            current_session = await self.get_session_by_id(session_id)
            if current_session and current_session.current_phase != original_phase:
                logger.debug(
                    "Party session %s already advanced to %s by another writer",
                    session_id,
                    current_session.current_phase,
                )
                return None
            logger.debug(
                "Party session %s stale during phase advance at version %s",
                session_id,
                original_version,
            )
            return None

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

    async def _get_human_participant_count(self, session_id: UUID) -> int:
        """Get count of human (non-AI) participants in session.

        Args:
            session_id: UUID of the session

        Returns:
            int: Number of human participants
        """
        result = await self.db.execute(
            select(func.count(PartyParticipant.participant_id))
            .join(QFPlayer, PartyParticipant.player_id == QFPlayer.player_id)
            .where(PartyParticipant.session_id == session_id)
            .where(~QFPlayer.email.ilike(f'%{AI_PLAYER_EMAIL_DOMAIN}'))
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
        participants = list(result.scalars().all())

        # Ensure player relationships are loaded for each participant
        for participant in participants:
            await self.db.refresh(participant, attribute_names=['player'])

        return participants

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
                'connection_status': participant.connection_status,
                'prompts_submitted': participant.prompts_submitted,
                'copies_submitted': participant.copies_submitted,
                'votes_submitted': participant.votes_submitted,
                'prompts_required': session.prompts_per_player,
                'copies_required': session.copies_per_player,
                'votes_required': session.votes_per_player,
                'joined_at': participant.joined_at.isoformat() if participant.joined_at else None,
                'ready_at': participant.ready_at.isoformat() if participant.ready_at else None,
                'last_activity_at': participant.last_activity_at.isoformat() if participant.last_activity_at else None,
                'disconnected_at': participant.disconnected_at.isoformat() if participant.disconnected_at else None,
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
            'version': session.version,
            'min_players': session.min_players,
            'max_players': session.max_players,
            'phase_started_at': session.phase_started_at.isoformat() if session.phase_started_at else None,
            'phase_expires_at': session.phase_expires_at.isoformat() if session.phase_expires_at else None,
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
            f"Incremented {round_type} progress for {player_id=} in session {session_id} "
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

    async def remove_player_from_all_sessions(self, player_id: UUID) -> int:
        """Record that a player disconnected from all active party sessions.

        Logout should not implicitly leave a party session. Presence changes are
        durable hints only; membership remains intact so reconnect can restore it.

        Args:
            player_id: UUID of the player to remove

        Returns:
            int: Number of sessions whose presence state was updated
        """
        now = datetime.now(UTC)

        # Find all active participants for this player
        result = await self.db.execute(
            select(PartyParticipant.participant_id, PartyParticipant.session_id)
            .join(PartySession, PartySession.session_id == PartyParticipant.session_id)
            .where(PartyParticipant.player_id == player_id)
            .where(PartySession.status.in_(['OPEN', 'IN_PROGRESS']))
        )

        participants = result.fetchall()
        session_count = 0

        for participant_id, session_id in participants:
            try:
                participant = await self.db.get(PartyParticipant, participant_id)
                if not participant:
                    continue

                participant.connection_status = 'disconnected'
                participant.disconnected_at = now
                participant.last_activity_at = now
                session_count += 1
            except Exception as e:
                logger.warning(f"Error updating presence for {player_id=} in session {session_id}: {e}")

        if session_count > 0:
            await self.db.commit()

        if session_count > 0:
            logger.info(f"Updated presence for {player_id=} in {session_count} party session(s)")

        return session_count

    async def cleanup_expired_sessions(
        self, max_session_age_hours: int = 24
    ) -> dict[str, int]:
        """Mark stale/expired party sessions as abandoned.

        Marks sessions that:
        - Are in OPEN status and haven't been started for too long
        - Are in IN_PROGRESS status and haven't been updated for too long

        Args:
            max_session_age_hours: Maximum age in hours before session is considered stale
                                  (default 24 hours)

        Returns:
            dict with counts of cleaned sessions by status
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=max_session_age_hours)
        stats = {
            'expired_open_sessions': 0,
            'expired_in_progress_sessions': 0,
            'removed_participants': 0,
        }

        try:
            # Clean up OPEN sessions that have been waiting too long
            result = await self.db.execute(
                select(PartySession)
                .where(PartySession.status == 'OPEN')
                .where(PartySession.created_at < cutoff_time)
            )
            open_sessions = result.scalars().all()

            for session in open_sessions:
                try:
                    session.status = 'ABANDONED'
                    session.phase_expires_at = None
                    session.updated_at = datetime.now(UTC)
                    stats['expired_open_sessions'] += 1

                    logger.info(
                        f"Abandoned OPEN session {session.party_code} "
                        f"(created {(datetime.now(UTC) - session.created_at).total_seconds() / 3600:.1f}h ago)"
                    )
                except Exception as e:
                    logger.error(f"Error expiring OPEN session {session.session_id}: {e}")

            # Clean up IN_PROGRESS sessions that have been stalled too long
            result = await self.db.execute(
                select(PartySession)
                .where(PartySession.status == 'IN_PROGRESS')
                .where(PartySession.updated_at < cutoff_time)
            )
            in_progress_sessions = result.scalars().all()

            for session in in_progress_sessions:
                try:
                    last_updated = session.updated_at or session.created_at
                    session.status = 'ABANDONED'
                    session.phase_expires_at = None
                    session.updated_at = datetime.now(UTC)
                    stats['expired_in_progress_sessions'] += 1

                    logger.info(
                        f"Abandoned IN_PROGRESS session {session.party_code} "
                        f"(inactive for {(datetime.now(UTC) - last_updated).total_seconds() / 3600:.1f}h)"
                    )
                except Exception as e:
                    logger.error(f"Error expiring IN_PROGRESS session {session.session_id}: {e}")

            # Commit all changes
            await self.db.commit()

            total_expired = stats['expired_open_sessions'] + stats['expired_in_progress_sessions']
            if total_expired > 0:
                logger.info(
                    f"Party session cleanup completed: "
                    f"{stats['expired_open_sessions']} OPEN, "
                    f"{stats['expired_in_progress_sessions']} IN_PROGRESS, "
                    f"{stats['removed_participants']} participants removed"
                )

        except Exception as e:
            logger.error(f"Error during session cleanup: {e}", exc_info=True)
            await self.db.rollback()

        return stats

    async def cleanup_disconnected_participants(
        self, inactive_minutes: int = 30
    ) -> int:
        """Retain disconnected participants so reconnect can restore them.

        Args:
            inactive_minutes: Minutes of inactivity before removal (default 30 minutes)

        Returns:
            int: Number of participants removed
        """
        logger.info(
            "Disconnected participant cleanup is disabled; presence is preserved for reconnect",
        )
        return 0
