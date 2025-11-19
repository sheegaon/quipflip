"""Party Mode coordination service for managing party-scoped rounds."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, not_
from typing import Optional, List
from uuid import UUID
import logging

from backend.models.qf.player import QFPlayer
from backend.models.qf.party_session import PartySession
from backend.models.qf.party_participant import PartyParticipant
from backend.models.qf.party_round import PartyRound
from backend.models.qf.party_phraseset import PartyPhraseset
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.prompt import Prompt
from backend.services.transaction_service import TransactionService
from backend.services.qf.round_service import RoundService
from backend.services.qf.vote_service import VoteService
from backend.services.qf.party_session_service import (
    PartySessionService,
    SessionNotFoundError,
    WrongPhaseError,
    AlreadySubmittedError,
    PartyModeError,
)
from backend.services.qf.party_websocket_manager import get_party_websocket_manager
from backend.config import get_settings
from backend.utils.exceptions import NoPromptsAvailableError, NoPhrasesetsAvailableError

logger = logging.getLogger(__name__)
settings = get_settings()


class PartyCoordinationService:
    """Service for coordinating party rounds with existing round services."""

    def __init__(
        self,
        db: AsyncSession,
        party_session_service: Optional[PartySessionService] = None,
        round_service: Optional[RoundService] = None,
        vote_service: Optional[VoteService] = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.party_session_service = party_session_service or PartySessionService(db)
        self.round_service = round_service or RoundService(db)
        self.vote_service = vote_service or VoteService(db)
        self.ws_manager = get_party_websocket_manager()

    async def start_party_prompt_round(
        self,
        session_id: UUID,
        player: QFPlayer,
        transaction_service: TransactionService,
    ) -> tuple[Round, UUID]:
        """Start a prompt round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            transaction_service: Transaction service instance

        Returns:
            tuple: (Round object, party_round_id UUID)

        Raises:
            SessionNotFoundError: If session doesn't exist
            WrongPhaseError: If session not in PROMPT phase
            AlreadySubmittedError: If player already submitted prompt
        """
        # Validate session and phase
        session = await self.party_session_service.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.current_phase != 'PROMPT':
            raise WrongPhaseError(
                f"Cannot start prompt round in {session.current_phase} phase"
            )

        # Check if player has already submitted prompt
        participant = await self.party_session_service.get_participant(
            session_id, player.player_id
        )
        if not participant:
            raise PartyModeError(f"Player {player.player_id} not in session")

        if participant.prompts_submitted >= session.prompts_per_player:
            raise AlreadySubmittedError(
                f"Player has already submitted {participant.prompts_submitted} prompt(s)"
            )

        # Start normal prompt round
        round_obj = await self.round_service.start_prompt_round(player, transaction_service)

        # Link round to party (without incrementing counter yet)
        party_round = await self.party_session_service.link_round_to_party(
            session_id=session_id,
            player_id=player.player_id,
            round_id=round_obj.round_id,
            round_type='prompt',
            phase='PROMPT',
        )

        logger.info(
            f"Started party prompt round {round_obj.round_id} for player {player.player_id} "
            f"in session {session_id}"
        )

        return round_obj, party_round.party_round_id

    async def submit_party_prompt(
        self,
        session_id: UUID,
        player: QFPlayer,
        round_id: UUID,
        phrase: str,
    ) -> dict:
        """Submit prompt round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            round_id: UUID of the round
            phrase: Submitted phrase

        Returns:
            dict: Result with round data and session status
        """
        # Submit via normal round service
        result = await self.round_service.submit_prompt_phrase(round_id, phrase, player)

        # Increment participant progress counter (only on successful submission)
        participant = await self.party_session_service.increment_participant_progress(
            session_id=session_id,
            player_id=player.player_id,
            round_type='prompt',
        )

        # Broadcast progress update
        await self.ws_manager.notify_player_progress(
            session_id=session_id,
            player_id=player.player_id,
            username=player.username,
            action='submitted_prompt',
            progress={
                'prompts_submitted': participant.prompts_submitted,
                'copies_submitted': participant.copies_submitted,
                'votes_submitted': participant.votes_submitted,
            },
            session_progress=await self._get_session_progress_summary(session_id),
        )

        # Check if all players done with prompts
        if await self.party_session_service.can_advance_phase(session_id):
            session = await self.party_session_service.advance_phase(session_id)

            # Broadcast phase transition
            await self.ws_manager.notify_phase_transition(
                session_id=session_id,
                old_phase='PROMPT',
                new_phase=session.current_phase,
                message="All prompts submitted! Time to write copies.",
            )

        return {
            'success': True,
            'phrase': phrase,
            'round_type': 'prompt',
        }

    async def start_party_copy_round(
        self,
        session_id: UUID,
        player: QFPlayer,
        transaction_service: TransactionService,
    ) -> tuple[Round, UUID]:
        """Start a copy round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            transaction_service: Transaction service instance

        Returns:
            tuple: (Round object, party_round_id UUID)

        Raises:
            SessionNotFoundError: If session doesn't exist
            WrongPhaseError: If session not in COPY phase
            AlreadySubmittedError: If player already submitted all required copies
            NoPromptsAvailableError: If no eligible prompts available
        """
        # Validate session and phase
        session = await self.party_session_service.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.current_phase != 'COPY':
            raise WrongPhaseError(
                f"Cannot start copy round in {session.current_phase} phase"
            )

        # Check if player has copies remaining
        participant = await self.party_session_service.get_participant(
            session_id, player.player_id
        )
        if not participant:
            raise PartyModeError(f"Player {player.player_id} not in session")

        if participant.copies_submitted >= session.copies_per_player:
            raise AlreadySubmittedError(
                f"Player has already submitted {participant.copies_submitted} copy(ies)"
            )

        # Get eligible prompts (party-first, then global)
        eligible_prompt_round_id = await self._get_eligible_prompt_for_copy(
            session_id, player.player_id
        )

        if not eligible_prompt_round_id:
            raise NoPromptsAvailableError("No eligible prompts available for copying")

        # Start copy round with specific prompt
        round_obj = await self.round_service.start_copy_round(
            player=player,
            transaction_service=transaction_service,
            prompt_round_id=eligible_prompt_round_id,
        )

        # Link round to party (without incrementing counter yet)
        party_round = await self.party_session_service.link_round_to_party(
            session_id=session_id,
            player_id=player.player_id,
            round_id=round_obj.round_id,
            round_type='copy',
            phase='COPY',
        )

        logger.info(
            f"Started party copy round {round_obj.round_id} for player {player.player_id} "
            f"in session {session_id}"
        )

        return round_obj, party_round.party_round_id

    async def submit_party_copy(
        self,
        session_id: UUID,
        player: QFPlayer,
        round_id: UUID,
        phrase: str,
    ) -> dict:
        """Submit copy round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            round_id: UUID of the round
            phrase: Submitted phrase

        Returns:
            dict: Result with round data and session status
        """
        # Submit via normal round service
        result = await self.round_service.submit_copy_phrase(round_id, phrase, player)

        # Increment participant progress counter (only on successful submission)
        participant = await self.party_session_service.increment_participant_progress(
            session_id=session_id,
            player_id=player.player_id,
            round_type='copy',
        )

        # If phraseset was created, link it to party
        if result.get('phraseset_created') and result.get('phraseset_id'):
            await self.party_session_service.link_phraseset_to_party(
                session_id=session_id,
                phraseset_id=result['phraseset_id'],
                created_in_phase='COPY',
            )
            logger.info(
                f"Linked phraseset {result['phraseset_id']} to party session {session_id}"
            )

        await self.ws_manager.notify_player_progress(
            session_id=session_id,
            player_id=player.player_id,
            username=player.username,
            action='submitted_copy',
            progress={
                'prompts_submitted': participant.prompts_submitted,
                'copies_submitted': participant.copies_submitted,
                'votes_submitted': participant.votes_submitted,
            },
            session_progress=await self._get_session_progress_summary(session_id),
        )

        # Check if all players done with copies
        if await self.party_session_service.can_advance_phase(session_id):
            session = await self.party_session_service.advance_phase(session_id)

            # Broadcast phase transition
            await self.ws_manager.notify_phase_transition(
                session_id=session_id,
                old_phase='COPY',
                new_phase=session.current_phase,
                message="All copies submitted! Time to vote.",
            )

        return {
            'success': True,
            'phrase': phrase,
            'round_type': 'copy',
            'phraseset_created': result.get('phraseset_created', False),
        }

    async def start_party_vote_round(
        self,
        session_id: UUID,
        player: QFPlayer,
        transaction_service: TransactionService,
    ) -> tuple[Round, UUID]:
        """Start a vote round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            transaction_service: Transaction service instance

        Returns:
            tuple: (Round object, party_round_id UUID)

        Raises:
            SessionNotFoundError: If session doesn't exist
            WrongPhaseError: If session not in VOTE phase
            AlreadySubmittedError: If player already submitted all required votes
            NoPhrasesetsAvailableError: If no eligible phrasesets available
        """
        # Validate session and phase
        session = await self.party_session_service.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        if session.current_phase != 'VOTE':
            raise WrongPhaseError(
                f"Cannot start vote round in {session.current_phase} phase"
            )

        # Check if player has votes remaining
        participant = await self.party_session_service.get_participant(
            session_id, player.player_id
        )
        if not participant:
            raise PartyModeError(f"Player {player.player_id} not in session")

        if participant.votes_submitted >= session.votes_per_player:
            raise AlreadySubmittedError(
                f"Player has already submitted {participant.votes_submitted} vote(s)"
            )

        # Get eligible phrasesets (party-first, excluding self-content)
        eligible_phraseset_id = await self._get_eligible_phraseset_for_vote(
            session_id, player.player_id
        )

        if not eligible_phraseset_id:
            raise NoPhrasesetsAvailableError("No eligible phrasesets available for voting")

        # Start vote round with specific phraseset
        round_obj = await self.vote_service.start_vote_round(
            player=player,
            transaction_service=transaction_service,
            phraseset_id=eligible_phraseset_id,
        )

        # Link round to party (without incrementing counter yet)
        party_round = await self.party_session_service.link_round_to_party(
            session_id=session_id,
            player_id=player.player_id,
            round_id=round_obj.round_id,
            round_type='vote',
            phase='VOTE',
        )

        logger.info(
            f"Started party vote round {round_obj.round_id} for player {player.player_id} "
            f"in session {session_id}"
        )

        return round_obj, party_round.party_round_id

    async def submit_party_vote(
        self,
        session_id: UUID,
        player: QFPlayer,
        round_id: UUID,
        phraseset_id: UUID,
        phrase: str,
    ) -> dict:
        """Submit vote round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            round_id: UUID of the round
            phraseset_id: UUID of the phraseset
            phrase: Selected phrase

        Returns:
            dict: Result with vote data and session status
        """
        # Submit via normal vote service
        result = await self.vote_service.submit_vote(
            player=player,
            phraseset_id=phraseset_id,
            chosen_phrase=phrase,
        )

        # Increment participant progress counter (only on successful submission)
        participant = await self.party_session_service.increment_participant_progress(
            session_id=session_id,
            player_id=player.player_id,
            round_type='vote',
        )

        await self.ws_manager.notify_player_progress(
            session_id=session_id,
            player_id=player.player_id,
            username=player.username,
            action='submitted_vote',
            progress={
                'prompts_submitted': participant.prompts_submitted,
                'copies_submitted': participant.copies_submitted,
                'votes_submitted': participant.votes_submitted,
            },
            session_progress=await self._get_session_progress_summary(session_id),
        )

        # Check if all players done with votes
        if await self.party_session_service.can_advance_phase(session_id):
            session = await self.party_session_service.advance_phase(session_id)

            # Broadcast phase transition
            await self.ws_manager.notify_phase_transition(
                session_id=session_id,
                old_phase='VOTE',
                new_phase=session.current_phase,
                message="All votes submitted! Check out the results.",
            )

        return {
            'success': True,
            'phrase': phrase,
            'round_type': 'vote',
            'correct': result.get('correct', False),
        }

    async def _get_eligible_prompt_for_copy(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> Optional[UUID]:
        """Get eligible prompt round for player to copy.

        Prioritizes party prompts, then falls back to global pool.
        Excludes:
        - Player's own prompts
        - Prompts already copied by this player
        - Prompts player abandoned

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player

        Returns:
            UUID of eligible prompt round, or None if none available
        """
        # Get party rounds for this session (PROMPT phase only)
        result = await self.db.execute(
            select(PartyRound)
            .where(PartyRound.session_id == session_id)
            .where(PartyRound.round_type == 'prompt')
            .where(PartyRound.phase == 'PROMPT')
        )
        party_prompt_rounds = result.scalars().all()
        party_prompt_round_ids = [pr.round_id for pr in party_prompt_rounds]

        # Get party prompts player hasn't copied yet
        if party_prompt_round_ids:
            # Get prompts this player has already copied
            result = await self.db.execute(
                select(Round.prompt_round_id)
                .where(Round.player_id == player_id)
                .where(Round.round_type == 'copy')
                .where(Round.prompt_round_id.in_(party_prompt_round_ids))
                .distinct()
            )
            already_copied = {row[0] for row in result.all()}

            # Filter eligible party prompts
            eligible_party_prompts = [
                pr for pr in party_prompt_rounds
                if pr.round_id not in already_copied
            ]

            # Exclude player's own prompts
            result = await self.db.execute(
                select(Round.round_id, Round.player_id)
                .where(Round.round_id.in_([pr.round_id for pr in eligible_party_prompts]))
            )
            prompt_players = {round_id: player_id for round_id, player_id in result.all()}

            eligible_party_prompts = [
                pr for pr in eligible_party_prompts
                if prompt_players.get(pr.round_id) != player_id
            ]

            if eligible_party_prompts:
                # Return first eligible party prompt
                return eligible_party_prompts[0].round_id

        # Fallback to global pool via queue service
        # This will handle abandoned prompts, flagged prompts, etc.
        # For now, return None to signal no party prompts available
        # The round service will handle global queue assignment
        return None

    async def _get_eligible_phraseset_for_vote(
        self,
        session_id: UUID,
        player_id: UUID,
    ) -> Optional[UUID]:
        """Get eligible phraseset for player to vote on.

        Prioritizes party phrasesets.
        Excludes:
        - Phrasesets where player contributed (prompt or copy)
        - Phrasesets player already voted on

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player

        Returns:
            UUID of eligible phraseset, or None if none available
        """
        # Get party phrasesets available for voting
        result = await self.db.execute(
            select(PartyPhraseset, Phraseset)
            .join(Phraseset, PartyPhraseset.phraseset_id == Phraseset.phraseset_id)
            .where(PartyPhraseset.session_id == session_id)
            .where(PartyPhraseset.available_for_voting == True)
            .where(Phraseset.status == 'voting')
        )
        party_phrasesets_data = result.all()

        if not party_phrasesets_data:
            return None

        # Get player's party rounds to check contribution
        result = await self.db.execute(
            select(PartyRound.round_id)
            .where(PartyRound.session_id == session_id)
            .join(PartyParticipant, PartyRound.participant_id == PartyParticipant.participant_id)
            .where(PartyParticipant.player_id == player_id)
        )
        player_round_ids = {row[0] for row in result.all()}

        # Filter out phrasesets where player contributed
        eligible_phrasesets = []
        for party_phraseset, phraseset in party_phrasesets_data:
            # Check if player contributed to this phraseset
            contributed = (
                phraseset.prompt_round_id in player_round_ids or
                phraseset.copy_round_1_id in player_round_ids or
                (phraseset.copy_round_2_id and phraseset.copy_round_2_id in player_round_ids)
            )

            if not contributed:
                # Check if player already voted on this phraseset
                result = await self.db.execute(
                    select(func.count())
                    .select_from(Round)
                    .where(Round.player_id == player_id)
                    .where(Round.round_type == 'vote')
                    .where(Round.phraseset_id == phraseset.phraseset_id)
                )
                already_voted = result.scalar() > 0

                if not already_voted:
                    eligible_phrasesets.append(phraseset.phraseset_id)

        if eligible_phrasesets:
            # Return first eligible phraseset
            return eligible_phrasesets[0]

        return None

    async def _get_session_progress_summary(self, session_id: UUID) -> dict:
        """Get summary of session progress.

        Args:
            session_id: UUID of the party session

        Returns:
            dict: Progress summary
        """
        session = await self.party_session_service.get_session_by_id(session_id)
        if not session:
            return {}

        # Get participants
        participants = await self.party_session_service.get_participants(session_id)

        # Count completed players for current phase
        if session.current_phase == 'PROMPT':
            required = session.prompts_per_player
            done = sum(1 for p in participants if p.prompts_submitted >= required)
        elif session.current_phase == 'COPY':
            required = session.copies_per_player
            done = sum(1 for p in participants if p.copies_submitted >= required)
        elif session.current_phase == 'VOTE':
            required = session.votes_per_player
            done = sum(1 for p in participants if p.votes_submitted >= required)
        else:
            done = 0

        return {
            'players_done_with_phase': done,
            'total_players': len(participants),
        }
