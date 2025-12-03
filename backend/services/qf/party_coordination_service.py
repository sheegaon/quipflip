"""Party Mode coordination service for managing party-scoped rounds."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, not_
from typing import Optional, List, Callable, TypeVar, Any
from uuid import UUID
import asyncio
import logging
import random
from sqlalchemy.exc import OperationalError

from backend.models.qf.player import QFPlayer
from backend.models.qf.party_session import PartySession
from backend.models.qf.party_participant import PartyParticipant
from backend.models.qf.party_round import PartyRound
from backend.models.qf.party_phraseset import PartyPhraseset
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.prompt import Prompt
from backend.services.transaction_service import TransactionService
from backend.utils.model_registry import GameType
from backend.services.qf.round_service import QFRoundService
from backend.services.qf.vote_service import QFVoteService
from backend.services.qf.party_session_service import (
    PartySessionService,
    SessionNotFoundError,
    WrongPhaseError,
    AlreadySubmittedError,
    PartyModeError,
)
from backend.services.qf.party_websocket_manager import get_party_websocket_manager
from backend.services.qf.queue_service import QFQueueService
from backend.config import get_settings
from backend.utils.exceptions import NoPromptsAvailableError, NoPhrasesetsAvailableError
from backend.services.ai.ai_service import AI_PLAYER_EMAIL_DOMAIN
from backend.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar('T')


async def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    jitter: bool = True,
    operation_name: str = "operation",
) -> Any:
    """
    Retry an async function with exponential backoff.

    This is specifically designed to handle lock contention during parallel
    AI submissions. When multiple AI players try to start rounds simultaneously,
    transient lock conflicts can occur despite per-player locking.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.5s)
        max_delay: Maximum delay between retries (default: 5s)
        jitter: Add random jitter to delays to prevent thundering herd (default: True)
        operation_name: Name for logging purposes

    Returns:
        Result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except (TimeoutError, OperationalError) as e:
            last_exception = e
            if attempt < max_retries:
                # Calculate exponential backoff delay
                delay = min(base_delay * (2 ** attempt), max_delay)

                # Add jitter to prevent synchronized retries
                if jitter:
                    delay = delay * (0.5 + random.random())

                logger.warning(
                    f"🔄 [RETRY] {operation_name} failed with lock timeout (attempt {attempt + 1}/{max_retries + 1}). "
                    f"Retrying in {delay:.2f}s... Error: {e}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"❌ [RETRY] {operation_name} failed after {max_retries + 1} attempts. Giving up. Error: {e}"
                )
                raise
        except Exception as e:
            # For non-timeout errors, fail immediately
            logger.error(f"❌ [RETRY] {operation_name} failed with non-retryable error: {e}")
            raise


class PartyCoordinationService:
    """Service for coordinating party rounds with existing round services."""

    def __init__(
        self,
        db: AsyncSession,
        party_session_service: Optional[PartySessionService] = None,
        round_service: Optional[QFRoundService] = None,
        vote_service: Optional[QFVoteService] = None,
    ):
        self.db = db
        self.settings = get_settings()
        self.party_session_service = party_session_service or PartySessionService(db)
        self.round_service = round_service or QFRoundService(db)
        self.vote_service = vote_service or QFVoteService(db)
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
        transaction_service: TransactionService,
    ) -> dict:
        """Submit prompt round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            round_id: UUID of the round
            phrase: Submitted phrase
            transaction_service: Transaction service instance

        Returns:
            dict: Result with round data and session status
        """
        # Submit via normal round service
        result = await self.round_service.submit_prompt_phrase(
            round_id, phrase, player, transaction_service
        )

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
        can_advance = await self.party_session_service.can_advance_phase(session_id)
        logger.info(f"After prompt submission - can_advance_phase={can_advance} for session {session_id}")

        if can_advance:
            logger.info(f"Advancing phase for session {session_id} from PROMPT to COPY")
            session = await self.party_session_service.advance_phase(session_id)

            # Broadcast phase transition
            await self.ws_manager.notify_phase_transition(
                session_id=session_id,
                old_phase='PROMPT',
                new_phase=session.current_phase,
                message="All prompts submitted! Time to write copies.",
            )

            # Trigger AI submissions for new phase (COPY)
            await self._trigger_ai_submissions_for_new_phase(
                session_id=session_id,
                transaction_service=transaction_service,
            )
        else:
            logger.info(f"Not advancing phase yet for session {session_id} - waiting for more submissions")

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
        eligible_prompt_round_id, prompt_from_queue = await self._get_eligible_prompt_for_copy(
            session_id, player.player_id
        )

        if not eligible_prompt_round_id:
            raise NoPromptsAvailableError("No eligible prompts available for copying")

        # Start copy round with specific prompt
        round_obj, _ = await self.round_service.start_copy_round(
            player=player,
            transaction_service=transaction_service,
            prompt_round_id=eligible_prompt_round_id,
            force_prompt_round=True,
            prompt_from_queue=prompt_from_queue,
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
        transaction_service: TransactionService,
    ) -> dict:
        """Submit copy round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            round_id: UUID of the round
            phrase: Submitted phrase
            transaction_service: Transaction service instance

        Returns:
            dict: Result with round data and session status
        """
        # Submit via normal round service
        result = await self.round_service.submit_copy_phrase(
            round_id, phrase, player, transaction_service
        )

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

            # Trigger AI submissions for new phase (VOTE)
            await self._trigger_ai_submissions_for_new_phase(
                session_id=session_id,
                transaction_service=transaction_service,
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
        transaction_service: TransactionService,
    ) -> dict:
        """Submit vote round within party context.

        Args:
            session_id: UUID of the party session
            player: Player object
            round_id: UUID of the round
            phraseset_id: UUID of the phraseset
            phrase: Selected phrase
            transaction_service: Transaction service instance

        Returns:
            dict: Result with vote data and session status
        """
        # Get objects
        round_obj = await self.db.get(Round, round_id)
        phraseset_obj = await self.db.get(Phraseset, phraseset_id)

        if not round_obj or not phraseset_obj:
            raise ValueError("Round or phraseset not found")

        # Submit via normal vote service
        result = await self.vote_service.submit_vote(
            round=round_obj,
            phraseset=phraseset_obj,
            phrase=phrase,
            player=player,
            transaction_service=transaction_service,
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
    ) -> tuple[Optional[UUID], bool]:
        """Get eligible prompt round for player to copy.

        Prioritizes party prompts, then falls back to global pool while filtering out
        any prompts written by players in the current party. Excludes:
        - Player's own prompts
        - Prompts already copied by this player
        - Prompts player abandoned

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player

        Returns:
            Tuple of (eligible prompt round ID or None, whether the prompt originated from the global queue)
        """
        # Prompts this player has already copied
        result = await self.db.execute(
            select(Round.prompt_round_id)
            .where(Round.player_id == player_id)
            .where(Round.round_type == 'copy')
            .distinct()
        )
        already_copied = {row[0] for row in result.all() if row[0]}

        # Party prompts (PROMPT phase only)
        result = await self.db.execute(
            select(PartyRound)
            .where(PartyRound.session_id == session_id)
            .where(PartyRound.round_type == 'prompt')
            .where(PartyRound.phase == 'PROMPT')
        )
        party_prompt_rounds = result.scalars().all()
        party_prompt_round_ids = [pr.round_id for pr in party_prompt_rounds]

        if party_prompt_round_ids:
            result = await self.db.execute(
                select(Round.round_id, Round.player_id)
                .where(Round.round_id.in_(party_prompt_round_ids))
            )
            prompt_players = {round_id: prompt_player_id for round_id, prompt_player_id in result.all()}

            eligible_party_prompts = [
                pr
                for pr in party_prompt_rounds
                if pr.round_id not in already_copied
                and prompt_players.get(pr.round_id) not in {player_id, None}
            ]

            if eligible_party_prompts:
                return eligible_party_prompts[0].round_id, False

        # Fallback: reuse prompt rounds from the global queue that are not authored by
        # anyone currently in the party session.
        participants = await self.party_session_service.get_participants(session_id)
        party_player_ids = {p.player_id for p in participants if p.player_id}
        skipped_prompt_ids: list[UUID] = []
        queue_length = QFQueueService.get_prompt_rounds_waiting()

        for _ in range(queue_length):
            prompt_round_id = QFQueueService.get_next_prompt_round()
            if not prompt_round_id:
                break

            prompt_round = await self.db.get(Round, prompt_round_id)
            if not prompt_round or prompt_round.round_type != 'prompt':
                continue

            if prompt_round.player_id in party_player_ids:
                skipped_prompt_ids.append(prompt_round_id)
                continue

            if prompt_round.round_id in already_copied:
                skipped_prompt_ids.append(prompt_round_id)
                continue

            if prompt_round.status != 'submitted':
                continue

            # Found an eligible prompt; requeue skipped prompts before returning
            for skipped_id in skipped_prompt_ids:
                QFQueueService.add_prompt_round_to_queue(skipped_id)

            return prompt_round.round_id, True

        # Requeue any skipped prompts if no eligible option was found
        for skipped_id in skipped_prompt_ids:
            QFQueueService.add_prompt_round_to_queue(skipped_id)

        return None, False

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

    async def _process_single_ai_prompt_submission(
        self,
        session_id: UUID,
        session: PartySession,
        participant: PartyParticipant,
        ai_service,
        transaction_service: TransactionService,
        coordination_service: Optional['PartyCoordinationService'] = None,
    ) -> Optional[str]:
        """Process a single AI prompt submission.

        Args:
            session_id: Party session ID
            session: Party session object
            participant: AI participant to process
            ai_service: AI service instance
            transaction_service: Transaction service
            coordination_service: Optional isolated coordination service for DB isolation

        Returns:
            Submitted phrase if successful, None if skipped or failed
        """
        try:
            # Use provided coordination service or fall back to self
            coord = coordination_service or self

            # Check if AI has submitted all prompts
            if participant.prompts_submitted >= session.prompts_per_player:
                logger.info(f"🤖 [AI SUBMIT] {participant.player.username} already submitted {participant.prompts_submitted} prompts, skipping")
                return None

            logger.info(f"🤖 [AI SUBMIT] {participant.player.username} needs to submit prompt ({participant.prompts_submitted}/{session.prompts_per_player})")

            # Submit prompt round (with retry logic for lock contention)
            logger.info(f"🤖 [AI SUBMIT] Starting prompt round for {participant.player.username}")
            round_obj, party_round_id = await retry_with_backoff(
                func=lambda: coord.start_party_prompt_round(
                    session_id=session_id,
                    player=participant.player,
                    transaction_service=transaction_service,
                ),
                operation_name=f"start_prompt_round for AI {participant.player.username}",
            )
            logger.info(f"🤖 [AI SUBMIT] Created round {round_obj.round_id} for {participant.player.username}")

            # Generate phrase for prompt based on the actual quip round prompt text
            phrase = await ai_service.generate_quip_response(round_obj.prompt_text, round_obj.round_id)
            logger.info(f"🤖 [AI SUBMIT] Generated response for {participant.player.username}: '{phrase}'")

            # Submit phrase (with retry logic for lock contention)
            logger.info(f"🤖 [AI SUBMIT] Submitting phrase for {participant.player.username}")
            await retry_with_backoff(
                func=lambda: coord.submit_party_prompt(
                    session_id=session_id,
                    player=participant.player,
                    round_id=round_obj.round_id,
                    phrase=phrase,
                    transaction_service=transaction_service,
                ),
                operation_name=f"submit_prompt for AI {participant.player.username}",
            )

            logger.info(f"🤖 [AI SUBMIT] ✅ AI player {participant.player.username} submitted prompt: '{phrase}'")
            return phrase

        except Exception as e:
            logger.error(f"🤖 [AI SUBMIT] ❌ Error processing prompt for {participant.player.username}: {e}", exc_info=True)
            raise

    async def _process_single_ai_copy_submission(
        self,
        session_id: UUID,
        session: PartySession,
        participant: PartyParticipant,
        ai_service,
        transaction_service: TransactionService,
        coordination_service: Optional['PartyCoordinationService'] = None,
    ) -> Optional[str]:
        """Process a single AI copy submission.

        Args:
            session_id: Party session ID
            session: Party session object
            participant: AI participant to process
            ai_service: AI service instance
            transaction_service: Transaction service
            coordination_service: Optional isolated coordination service for DB isolation

        Returns:
            Submitted copy phrase if successful, None if skipped or failed
        """
        try:
            # Use provided coordination service or fall back to self
            coord = coordination_service or self

            # Check if AI has submitted all copies
            if participant.copies_submitted >= session.copies_per_player:
                return None

            # Submit copy round (with retry logic for lock contention)
            try:
                round_obj, party_round_id = await retry_with_backoff(
                    func=lambda: coord.start_party_copy_round(
                        session_id=session_id,
                        player=participant.player,
                        transaction_service=transaction_service,
                    ),
                    operation_name=f"start_copy_round for AI {participant.player.username}",
                )
            except NoPromptsAvailableError:
                logger.info(f"No eligible prompts for AI {participant.player.username}")
                return None

            prompt_round_result = await coord.db.execute(
                select(Round).where(Round.round_id == round_obj.prompt_round_id)
            )
            prompt_round = prompt_round_result.scalar_one_or_none()
            if not prompt_round:
                logger.warning(
                    f"Prompt round {round_obj.prompt_round_id} not found for AI {participant.player.username}"
                )
                return None

            # Generate impostor phrase
            copy_phrase = await ai_service.get_impostor_phrase(prompt_round)

            # Submit copy phrase (with retry logic for lock contention)
            await retry_with_backoff(
                func=lambda: coord.submit_party_copy(
                    session_id=session_id,
                    player=participant.player,
                    round_id=round_obj.round_id,
                    phrase=copy_phrase,
                    transaction_service=transaction_service,
                ),
                operation_name=f"submit_copy for AI {participant.player.username}",
            )

            logger.info(f"🤖 [AI SUBMIT] ✅ AI player {participant.player.username} submitted copy: {copy_phrase}")
            return copy_phrase

        except Exception as e:
            logger.error(f"🤖 [AI SUBMIT] ❌ Error processing copy for {participant.player.username}: {e}", exc_info=True)
            raise

    async def _process_single_ai_vote_submission(
        self,
        session_id: UUID,
        session: PartySession,
        participant: PartyParticipant,
        ai_service,
        transaction_service: TransactionService,
        coordination_service: Optional['PartyCoordinationService'] = None,
    ) -> Optional[str]:
        """Process a single AI vote submission.

        Args:
            session_id: Party session ID
            session: Party session object
            participant: AI participant to process
            ai_service: AI service instance
            transaction_service: Transaction service
            coordination_service: Optional isolated coordination service for DB isolation

        Returns:
            Chosen phrase if successful, None if skipped or failed
        """
        try:
            # Use provided coordination service or fall back to self
            coord = coordination_service or self

            # Check if AI has submitted all votes
            if participant.votes_submitted >= session.votes_per_player:
                return None

            # Get eligible phraseset to vote on
            phraseset_id = await coord._get_eligible_phraseset_for_vote(
                session_id, participant.player_id
            )

            if not phraseset_id:
                logger.info(f"No eligible phrasesets for AI {participant.player.username}")
                return None

            # Get phraseset details
            phraseset_result = await coord.db.execute(
                select(Phraseset).where(Phraseset.phraseset_id == phraseset_id)
            )
            phraseset = phraseset_result.scalar_one_or_none()

            if not phraseset:
                return None

            # Generate vote
            seed = participant.player_id.int
            chosen_phrase = await ai_service.generate_vote_choice(phraseset, seed)

            # Submit vote round (with retry logic for lock contention)
            round_obj, party_round_id = await retry_with_backoff(
                func=lambda: coord.start_party_vote_round(
                    session_id=session_id,
                    player=participant.player,
                    transaction_service=transaction_service,
                ),
                operation_name=f"start_vote_round for AI {participant.player.username}",
            )

            # Submit vote (with retry logic for lock contention)
            await retry_with_backoff(
                func=lambda: coord.submit_party_vote(
                    session_id=session_id,
                    player=participant.player,
                    round_id=round_obj.round_id,
                    phraseset_id=phraseset_id,
                    phrase=chosen_phrase,
                    transaction_service=transaction_service,
                ),
                operation_name=f"submit_vote for AI {participant.player.username}",
            )

            logger.info(f"🤖 [AI SUBMIT] ✅ AI player {participant.player.username} voted for: {chosen_phrase}")
            return chosen_phrase

        except Exception as e:
            logger.error(f"🤖 [AI SUBMIT] ❌ Error processing vote for {participant.player.username}: {e}", exc_info=True)
            raise

    async def process_ai_submissions(
        self,
        session_id: UUID,
        transaction_service: TransactionService,
    ) -> dict:
        """
        Process submissions for all AI participants in the current phase.

        This method parallelizes AI submissions to prevent round timer expiry.
        All AI API calls (which take ~60s each) run concurrently instead of
        sequentially.

        Args:
            session_id: UUID of the party session
            transaction_service: Transaction service for player operations

        Returns:
            dict: Summary of AI submissions processed
        """
        from backend.services.ai.ai_service import AIService, AICopyError, AIVoteError

        stats = {
            'prompts_submitted': 0,
            'copies_submitted': 0,
            'votes_submitted': 0,
            'errors': 0,
        }

        try:
            # Get session
            session = await self.party_session_service.get_session_by_id(session_id)
            logger.info(f"🤖 [AI PROCESS] Session {session_id} - status: {session.status if session else 'NOT_FOUND'}, phase: {session.current_phase if session else 'N/A'}")

            if not session or session.status != 'IN_PROGRESS':
                logger.info(f"🤖 [AI PROCESS] Session {session_id} not in progress, skipping AI submissions")
                return stats

            # Get all participants
            participants = await self.party_session_service.get_participants(session_id)
            logger.info(f"🤖 [AI PROCESS] Found {len(participants)} total participants in session {session_id}")

            # Filter AI participants (check if email contains AI_PLAYER_EMAIL_DOMAIN)
            ai_participants = []
            for p in participants:
                player_email = p.player.email if p.player else 'NO_EMAIL'
                is_ai = p.player and AI_PLAYER_EMAIL_DOMAIN in p.player.email
                logger.info(f"🤖 [AI PROCESS] Participant {p.participant_id}: email={player_email}, is_ai={is_ai}, prompts={p.prompts_submitted}/{session.prompts_per_player}")
                if is_ai:
                    ai_participants.append(p)

            if not ai_participants:
                logger.info(f"🤖 [AI PROCESS] No AI participants found in session {session_id}")
                return stats

            logger.info(f"🤖 [AI PROCESS] 🚀 Processing {len(ai_participants)} AI participants IN PARALLEL for {session.current_phase} phase")

            # Create parallel tasks based on current phase
            # IMPORTANT: Each task gets its own database session to avoid "Session is already flushing" errors
            # when multiple coroutines try to flush simultaneously
            submission_tasks = []

            if session.current_phase == 'PROMPT':
                submission_tasks = [
                    self._run_ai_submission_with_isolated_session(
                        self._process_single_ai_prompt_submission,
                        session_id, session, participant
                    )
                    for participant in ai_participants
                ]
            elif session.current_phase == 'COPY':
                submission_tasks = [
                    self._run_ai_submission_with_isolated_session(
                        self._process_single_ai_copy_submission,
                        session_id, session, participant
                    )
                    for participant in ai_participants
                ]
            elif session.current_phase == 'VOTE':
                submission_tasks = [
                    self._run_ai_submission_with_isolated_session(
                        self._process_single_ai_vote_submission,
                        session_id, session, participant
                    )
                    for participant in ai_participants
                ]

            # Execute all AI submissions IN PARALLEL (critical for preventing timer expiry)
            if submission_tasks:
                logger.info(f"🤖 [AI PROCESS] ⚡ Executing {len(submission_tasks)} AI submissions in parallel")
                results = await asyncio.gather(*submission_tasks, return_exceptions=True)

                # Count successes and failures
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"🤖 [AI SUBMIT] ❌ Error for {ai_participants[i].player.username}: {result}", exc_info=result)
                        stats['errors'] += 1
                    elif result is not None:  # None means skipped (already submitted)
                        # Count successful submissions
                        if session.current_phase == 'PROMPT':
                            stats['prompts_submitted'] += 1
                        elif session.current_phase == 'COPY':
                            stats['copies_submitted'] += 1
                        elif session.current_phase == 'VOTE':
                            stats['votes_submitted'] += 1

            logger.info(f"🤖 [AI PROCESS] ✅ Parallel AI submissions completed for session {session_id}: {stats}")

            # Check if phase can advance (now that all AI are done)
            if await self.party_session_service.can_advance_phase(session_id):
                logger.info(f"🤖 [AI PROCESS] 🎯 All participants ready, advancing phase for session {session_id}")
                advanced_session = await self.party_session_service.advance_phase_atomic(session_id)
                if advanced_session:
                    logger.info(f"🤖 [AI PROCESS] ✅ Phase advanced to {advanced_session.current_phase} for session {session_id}")
                    # Recursively trigger AI for next phase
                    await self._trigger_ai_submissions_for_new_phase(session_id, transaction_service)
                else:
                    logger.debug(f"🤖 [AI PROCESS] Phase advancement was already handled by another process for session {session_id}")

            return stats

        except Exception as e:
            logger.error(f"🤖 [AI PROCESS] ❌ Fatal error processing AI submissions for session {session_id}: {e}", exc_info=True)
            stats['errors'] += 1
            return stats

    async def _run_ai_submission_with_isolated_session(
        self,
        submission_func,
        session_id: UUID,
        session: PartySession,
        participant: PartyParticipant,
    ) -> Optional[str]:
        """Run an AI submission with its own isolated database session.

        This prevents "Session is already flushing" errors that occur when multiple
        coroutines try to flush the same session simultaneously during parallel AI submissions.

        The key is that ALL services (RoundService, TransactionService, AIService, etc.)
        must use the same isolated session to avoid cross-session conflicts.

        Args:
            submission_func: The async submission function to call
            session_id: Party session ID
            session: Party session object
            participant: AI participant to process

        Returns:
            Result of the submission function
        """
        async with AsyncSessionLocal() as task_db:
            # Create fresh service instances with the isolated session
            # This ensures all operations within the submission use the same session
            from backend.services.ai.ai_service import AIService

            task_round_service = QFRoundService(task_db)
            task_vote_service = QFVoteService(task_db)
            task_party_session_service = PartySessionService(task_db)
            task_transaction_service = TransactionService(task_db, game_type=GameType.QF)
            ai_service = AIService(task_db)

            # Create a temporary coordination service with isolated services
            task_coordination = PartyCoordinationService(
                db=task_db,
                party_session_service=task_party_session_service,
                round_service=task_round_service,
                vote_service=task_vote_service,
            )

            return await submission_func(
                session_id, session, participant, ai_service, task_transaction_service,
                coordination_service=task_coordination
            )

    async def _trigger_ai_submissions_for_new_phase(
        self,
        session_id: UUID,
        transaction_service: TransactionService,
    ) -> None:
        """Automatically trigger AI submissions when a new phase starts.

        This method is called after phase transitions to ensure AI players
        submit their prompts/copies/votes automatically without manual intervention.

        Args:
            session_id: The party session ID
            transaction_service: Transaction service for database operations
        """
        try:
            logger.info(f"🤖 [AI TRIGGER] Starting automatic AI submissions for session {session_id}")
            stats = await self.process_ai_submissions(session_id, transaction_service)
            logger.info(f"🤖 [AI TRIGGER] Completed AI submissions for session {session_id}: {stats}")
        except Exception as e:
            logger.error(
                f"🤖 [AI TRIGGER] Failed to process automatic AI submissions for session {session_id}: {e}",
                exc_info=True
            )
