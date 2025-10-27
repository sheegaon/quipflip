"""
AI Copy Service for automated backup copy and vote generation.

This service provides AI-generated backup copies and votes when human players
are unavailable, supporting multiple AI providers (OpenAI, Gemini)
with configurable fallback behavior and comprehensive metrics tracking.
"""

import logging
import random

from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.phraseset_activity import PhrasesetActivity
from backend.models.vote import Vote
from backend.services.ai.metrics_service import AIMetricsService, MetricsTracker
from backend.services.player_service import PlayerService
from backend.services.round_service import RoundService
from .prompt_builder import build_copy_prompt


logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    """Raised when AI service fails."""


class AICopyError(RuntimeError):
    """Raised when AI copy generation fails."""


class AIVoteError(RuntimeError):
    """Raised when AI vote generation fails."""


class AIService:
    """
    Service for generating AI backup copies and votes using multiple providers.

    Supports OpenAI and Gemini as AI providers, with automatic fallback,
    configurable provider selection, and comprehensive metrics tracking.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize AI service.

        Args:
            db: Database session
            validator: Phrase validator for checking generated phrases
        """
        self.db = db
        self.settings = get_settings()
        if self.settings.use_phrase_validator_api:
            from backend.services.phrase_validation_client import get_phrase_validation_client
            self.phrase_validator = get_phrase_validation_client()
        else:
            from backend.services.phrase_validator import get_phrase_validator
            self.phrase_validator = get_phrase_validator()
        self.common_words = None
        self.metrics_service = AIMetricsService(db)

        # Determine which provider to use based on config and available API keys
        self.provider = self._determine_provider()
        if self.provider == "openai":
            self.ai_model = self.settings.ai_openai_model
        else:  # gemini
            self.ai_model = self.settings.ai_gemini_model

    def _determine_provider(self) -> str:
        """
        Determine which AI provider to use based on configuration and API keys.

        Returns:
            Provider name: "openai" or "gemini"

        Priority:
        1. Use configured provider if API key is available
        2. Fall back to other provider if configured one is unavailable
        3. Default to OpenAI if both are available
        """
        configured_provider = self.settings.ai_provider.lower()
        openai_key = self.settings.openai_api_key
        gemini_key = self.settings.gemini_api_key

        # Check if configured provider is available
        if configured_provider == "openai" and openai_key:
            logger.info("Using OpenAI as AI copy provider")
            return "openai"
        elif configured_provider == "gemini" and gemini_key:
            logger.info("Using Gemini as AI copy provider")
            return "gemini"
        elif configured_provider == "none":
            logger.error("No AI provider configured")
            raise AIServiceError("AI provider set to 'none' - cannot proceed")

        # Fallback logic
        if openai_key:
            logger.warning(
                f"Configured provider '{configured_provider}' not available, falling back to OpenAI"
            )
            return "openai"
        elif gemini_key:
            logger.warning(
                f"Configured provider '{configured_provider}' not available, falling back to Gemini"
            )
            return "gemini"

        # No provider available
        logger.error("No AI provider API keys found (OPENAI_API_KEY or GEMINI_API_KEY)")
        raise AIServiceError("No AI provider configured - set OPENAI_API_KEY or GEMINI_API_KEY")

    async def _get_or_create_ai_player(self, username="AI_COPY_BACKUP") -> Player:
        """
        Get or create the AI player account.

        Returns:
            The AI player instance

        Raises:
            AIServiceError: If AI player cannot be created or is in invalid state

        Note:
            Transaction management is handled by the caller (run_backup_cycle).
            This method should NOT commit or refresh the session.
        """
        try:
            # Check if AI player exists
            result = await self.db.execute(select(Player).where(Player.username == username))
            ai_player = result.scalar_one_or_none()

            if not ai_player:
                # Create AI player
                player_service = PlayerService(self.db)

                ai_player = await player_service.create_player(
                    username=username,
                    email=f"{username.lower()}@quipflip.internal",
                    password_hash="not-used-for-ai-player",
                    pseudonym="Clever Lexical Runner",
                    pseudonym_canonical="cleverlexicalrunner",
                )
                # Note: Do not commit here - let caller manage transaction
                logger.info("Created AI backup player account")
            else:
                # Validate AI player is in good state
                if ai_player.balance < -1000:
                    logger.warning(
                        f"AI player has very negative balance: {ai_player.balance}. "
                        "This may indicate an issue with payout logic."
                    )

                # Check for stuck active rounds (shouldn't happen, but handle gracefully)
                if ai_player.active_round_id:
                    logger.warning(
                        f"AI player has stuck active round: {ai_player.active_round_id}. "
                        "Clearing it to allow new operations."
                    )
                    # Clear the stuck round - AI doesn't use traditional rounds
                    ai_player.active_round_id = None
                    await self.db.flush()

            return ai_player

        except Exception as e:
            logger.error(f"Failed to get/create AI player: {e}")
            raise AIServiceError(f"AI player initialization failed: {e}")

    async def get_common_words(self) -> list[str]:
        """
        Get the list of common words to allow in AI-generated phrases.

        Returns:
            List of common words
        """
        if self.common_words is None:
            try:
                result = await self.phrase_validator.common_words()

                # Handle different return types from phrase validator
                if isinstance(result, (list, tuple)):
                    self.common_words = list(result)
                elif isinstance(result, set):
                    self.common_words = list(result)
                    logger.debug(f"Converted set to list for common_words: {len(self.common_words)} words")
                else:
                    logger.error(f"phrase_validator.common_words() returned {type(result)}, expected list/tuple/set")
                    self.common_words = []

            except Exception as e:
                logger.error(f"Failed to get common words: {e}")
                self.common_words = []

        return self.common_words

    async def generate_copy_phrase(self, original_phrase: str, prompt_round: Round) -> str:
        """
        Generate a copy phrase using the configured AI provider with proper copy validation.

        Args:
            original_phrase: The original phrase to create a copy of
            prompt_round: The prompt round object to get context and check existing copies

        Returns:
            Generated and validated copy phrase

        Raises:
            AICopyError: If generation or validation fails
        """
        # Determine if another copy already exists for duplicate/similarity checks
        other_copy_phrase = None
        if prompt_round.round_id:
            result = await self.db.execute(
                select(Round.copy_phrase)
                .where(Round.prompt_round_id == prompt_round.round_id)
                .where(Round.round_type == "copy")
                .where(Round.status == "submitted")
            )
            other_copy_phrase = result.scalars().first()

        async with MetricsTracker(
                self.metrics_service,
                operation_type="copy_generation",
                provider=self.provider,
                model=self.ai_model,
        ) as tracker:
            try:
                # Generate using configured provider
                ai_prompt = build_copy_prompt(original_phrase, other_copy_phrase)
                common_words = await self.get_common_words()
                if not isinstance(common_words, (list, tuple)):
                    logger.warning(f"common_words is not iterable: {type(common_words)}, using empty list")
                    common_words = []

                ai_prompt = ai_prompt.format(common_words=", ".join(common_words))
                if self.provider == "openai":
                    from backend.services.ai.openai_api import generate_copy
                else:  # gemini
                    from backend.services.ai.gemini_api import generate_copy
                phrase = await generate_copy(
                    prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)
            except Exception as e:
                # Wrap API exceptions in AICopyError
                logger.error(f"Failed to generate AI copy: {e}")
                raise AICopyError(f"Failed to generate AI copy using {ai_prompt=}: {e}")

            # Use the same validation logic as round_service for copy phrases
            is_valid, error_message = await self.phrase_validator.validate_copy(
                phrase,
                original_phrase,
                other_copy_phrase,
                prompt_round.prompt_text,
            )

            if not is_valid and 'too similar' in error_message:
                ai_prompt += f"\nNote: Your response of {phrase} was too similar. Generate a very different phrase."
                try:
                    phrase = await generate_copy(
                        prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)
                except Exception as e:
                    logger.error(f"Failed to generate AI copy on retry: {e}")
                    raise AICopyError(f"Failed to generate AI copy using retry {ai_prompt=}: {e}")

            # Retry validation
            is_valid, error_message = await self.phrase_validator.validate_copy(
                phrase,
                original_phrase,
                other_copy_phrase,
                prompt_round.prompt_text,
            )

            if not is_valid:
                tracker.set_result(
                    phrase,
                    success=False,
                    response_length=len(phrase),
                    validation_passed=False,
                )
                raise AICopyError(f"AI generated invalid copy phrase {phrase} for "
                                  f"{original_phrase=} {other_copy_phrase=}: {error_message}")

            # Track successful generation
            tracker.set_result(
                phrase,
                success=True,
                response_length=len(phrase),
                validation_passed=True,
            )

            logger.info(f"AI ({self.provider}) generated valid copy: '{phrase}' for original: '{original_phrase}'")
            return phrase

    async def generate_vote_choice(self, phraseset: Phraseset) -> str:
        """
        Generate a vote choice using the configured AI provider with metrics tracking.

        Args:
            phraseset: The phraseset to vote on (must have prompt and 3 phrases loaded)

        Returns:
            The chosen phrase (one of the 3 phrases in the phraseset)

        Raises:
            AIVoteError: If vote generation fails
        """
        from backend.services.ai.vote_helper import generate_vote_choice

        # Extract prompt and phrases from denormalized fields on Phraseset
        prompt_text = phraseset.prompt_text
        phrases = [
            phraseset.original_phrase,
            phraseset.copy_phrase_1,
            phraseset.copy_phrase_2,
        ]
        random.shuffle(phrases)

        async with MetricsTracker(
                self.metrics_service,
                operation_type="vote_generation",
                provider=self.provider,
                model=self.ai_model,
        ) as tracker:
            # Generate vote choice
            choice_index = await generate_vote_choice(
                prompt_text=prompt_text,
                phrases=phrases,
                provider=self.provider,
                model=self.ai_model,
                timeout=self.settings.ai_timeout_seconds,
            )

            chosen_phrase = phrases[choice_index]

            # Determine if vote is correct
            vote_correct = chosen_phrase == phraseset.original_phrase

            # Track the vote
            tracker.set_result(
                chosen_phrase,
                success=True,
                response_length=len(str(choice_index)),
                vote_correct=vote_correct,
            )

            logger.info(
                f"AI ({self.provider}) voted for '{chosen_phrase}' ({'CORRECT' if vote_correct else 'INCORRECT'})")

            return chosen_phrase

    async def _has_ai_attempted_prompt(self, prompt_round_id: str, lookback_hours: int = 24) -> bool:
        """
        Check if AI has already attempted to generate a copy for this prompt.

        Args:
            prompt_round_id: The prompt round ID to check
            lookback_hours: How far back to look for attempts (default: 24 hours)

        Returns:
            True if AI has attempted this prompt recently, False otherwise
        """
        from backend.models.ai_metric import AIMetric
        
        # Look back specified hours for attempts
        since = datetime.now(UTC) - timedelta(hours=lookback_hours)
        
        # Check if there are any copy generation attempts for this prompt
        # We use the prompt round ID in error messages, so we can search for it
        result = await self.db.execute(
            select(AIMetric.metric_id)
            .where(AIMetric.operation_type == "copy_generation")
            .where(AIMetric.created_at >= since)
            .where(AIMetric.error_message.contains(str(prompt_round_id)))
            .limit(1)
        )
        
        return result.scalar_one_or_none() is not None

    async def run_backup_cycle(self) -> None:
        """
        Run a backup cycle to provide AI copies for waiting prompts and AI votes for waiting phrasesets.

        This method:
        1. Finds prompts that have been waiting for copies longer than the backup delay
        2. Filters out prompts that AI has already attempted recently
        3. Generates AI copies for those prompts
        4. Submits the copies as the AI player
        5. Finds phrasesets that have been waiting for votes longer than the backup delay
        6. Generates AI votes for those phrasesets
        7. Submits the votes as the AI player

        Note:
            This is the main entry point for the AI backup system and manages the complete transaction lifecycle.
        """
        import uuid

        stats = {
            "prompts_checked": 0,
            "prompts_filtered_already_attempted": 0,
            "copies_generated": 0,
            "phrasesets_checked": 0,
            "votes_generated": 0,
            "errors": 0,
        }

        try:
            # Get or create AI copy player (within transaction)
            ai_copy_player = await self._get_or_create_ai_player()

            # Query for submitted prompt rounds that:
            # 1. Don't have a phraseset yet (still waiting for copies)
            # 2. Are older than the backup delay
            # 3. Don't belong to the AI player (avoid self-copies)
            # 4. Haven't been copied by the AI player already
            
            # Determine backup delay
            cutoff_time = datetime.now(UTC) - timedelta(minutes=self.settings.ai_backup_delay_minutes)

            # Get all prompt rounds that meet our basic criteria
            result = await self.db.execute(
                select(Round)
                .join(Player, Player.player_id == Round.player_id)
                .outerjoin(Phraseset, Phraseset.prompt_round_id == Round.round_id)
                .where(Round.round_type == 'prompt')
                .where(Round.status == 'submitted')
                .where(Round.created_at <= cutoff_time)
                .where(Round.player_id != ai_copy_player.player_id)
                .where(~Player.username.like('%test%'))  # Exclude test players
                .where(Phraseset.phraseset_id.is_(None))  # No phraseset yet
                .order_by(Round.created_at.asc())  # Process oldest first
                .limit(self.settings.ai_backup_batch_size)  # Configurable batch size
            )
            
            waiting_prompts = list(result.scalars().all())
            
            # Filter out prompts already copied by AI (check separately to avoid complex joins)
            filtered_prompts = []
            for prompt_round in waiting_prompts:
                ai_copy_result = await self.db.execute(
                    select(Round.round_id)
                    .where(Round.prompt_round_id == prompt_round.round_id)
                    .where(Round.round_type == 'copy')
                    .where(Round.player_id == ai_copy_player.player_id)
                )
                
                if ai_copy_result.scalar_one_or_none() is None:
                    filtered_prompts.append(prompt_round)
            
            # Filter out prompts that AI has already attempted recently
            final_prompts = []
            for prompt_round in filtered_prompts:
                has_attempted = await self._has_ai_attempted_prompt(str(prompt_round.round_id))
                if not has_attempted:
                    final_prompts.append(prompt_round)
                else:
                    stats["prompts_filtered_already_attempted"] += 1
                    logger.debug(f"Skipping prompt {prompt_round.round_id} - AI already attempted recently")
            
            stats["prompts_checked"] = len(final_prompts)
            logger.info(
                f"Found {len(final_prompts)} prompts waiting for AI backup copies "
                f"(filtered out {stats['prompts_filtered_already_attempted']} already attempted)"
            )

            # Process each waiting prompt
            for prompt_round in final_prompts:
                try:
                    # Generate AI copy phrase with proper validation context
                    copy_phrase = await self.generate_copy_phrase(prompt_round.submitted_phrase, prompt_round)

                    # Create copy round for AI player
                    round_service = RoundService(self.db)

                    # Start copy round for AI player
                    copy_round = Round(
                        round_id=uuid.uuid4(),
                        player_id=ai_copy_player.player_id,
                        round_type='copy',
                        status='submitted',
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(minutes=3),  # Standard copy round time
                        cost=0,  # AI doesn't pay
                        prompt_round_id=prompt_round.round_id,
                        original_phrase=prompt_round.submitted_phrase,
                        copy_phrase=copy_phrase.upper(),
                        system_contribution=0,  # AI contributions are free
                    )
                    
                    self.db.add(copy_round)
                    
                    # Update prompt round copy assignment
                    if prompt_round.copy1_player_id is None:
                        prompt_round.copy1_player_id = ai_copy_player.player_id
                        prompt_round.phraseset_status = "waiting_copy1"
                    elif prompt_round.copy2_player_id is None:
                        prompt_round.copy2_player_id = ai_copy_player.player_id
                        # Check if we now have both copies and can create phraseset
                        if prompt_round.copy1_player_id is not None:
                            phraseset = await round_service.create_phraseset_if_ready(prompt_round)
                            if phraseset:
                                prompt_round.phraseset_status = "active"
                    
                    stats["copies_generated"] += 1

                except Exception as e:
                    logger.error(f"Failed to generate AI copy for prompt {prompt_round.round_id}: {e}")
                    stats["errors"] += 1
                    continue

            # Query for phrasesets waiting for votes that:
            # 1. Are in "open" or "closing" status (accepting votes)
            # 2. Were created older than the backup delay
            # 3. Don't have contributions from the AI player (avoid self-votes) [disabled]
            # 4. Haven't been voted on by the AI player already (using subquery) [disabled]
            # 5. Exclude phrasesets from test players [disabled]

            # Create subquery to find phrasesets where AI has already voted
            # ai_voted_subquery = select(Vote.phraseset_id).where(Vote.player_id == ai_player.player_id)

            # Get all phrasesets that meet our basic criteria
            phraseset_result = await self.db.execute(
                select(Phraseset)
                # .join(Round, Round.round_id == Phraseset.prompt_round_id)
                # .join(Player, Player.player_id == Round.player_id)
                .where(Phraseset.status.in_(["open", "closing"]))
                .where(Phraseset.created_at <= cutoff_time)
                # .where(~Player.username.like('%test%'))  # Exclude test players
                # .where(Phraseset.phraseset_id.not_in(ai_voted_subquery))  # Exclude already voted
                .options(
                    selectinload(Phraseset.prompt_round),
                    selectinload(Phraseset.copy_round_1),
                    selectinload(Phraseset.copy_round_2),
                )
                .order_by(Phraseset.created_at.asc())  # Process oldest first
                .limit(self.settings.ai_backup_batch_size)  # Use configured batch size
            )
            
            # Filter out phrasesets with activity after cutoff_time
            waiting_phrasesets = list(phraseset_result.scalars().all())
            filtered_phrasesets = []
            for phraseset in waiting_phrasesets:
                activity = await self.db.execute(
                    select(PhrasesetActivity)
                    .where(PhrasesetActivity.phraseset_id == phraseset.phraseset_id)
                    .where(PhrasesetActivity.created_at > cutoff_time)
                )
                if len(activity.scalars().all()) == 0:
                    filtered_phrasesets.append(phraseset)

            # # Filter out phrasesets where AI was a contributor (in-memory check since we need loaded relationships)
            # filtered_phrasesets = []
            # for phraseset in waiting_phrasesets:
            #     try:
            #         # Safely get player IDs from loaded relationships
            #         contributor_player_ids = {
            #             r.player_id
            #             for r in (
            #                 phraseset.prompt_round,
            #                 phraseset.copy_round_1,
            #                 phraseset.copy_round_2,
            #             )
            #             if r
            #         }
            #
            #         # Skip if AI player was a contributor
            #         if ai_player.player_id not in contributor_player_ids:
            #             filtered_phrasesets.append(phraseset)
            #         else:
            #             logger.debug(f"Skipping phraseset {phraseset.phraseset_id} - AI was a contributor")
            #
            #     except Exception as e:
            #         logger.error(f"Error checking phraseset {phraseset.phraseset_id} contributors: {e}")
            #         # Skip this phraseset to avoid further errors
            #         continue

            stats["phrasesets_checked"] = len(filtered_phrasesets)
            logger.info(
                f"Found {len(filtered_phrasesets)} phrasesets waiting for AI backup votes: {filtered_phrasesets}")
            
            # Initialize services once for all votes (performance improvement)
            from backend.services.vote_service import VoteService
            from backend.services.transaction_service import TransactionService
            vote_service = VoteService(self.db)
            transaction_service = TransactionService(self.db)

            # Get or create AI copy player (within transaction)
            ai_vote_player = await self._get_or_create_ai_player(f"AI_VOTE_BACKUP_{random.randint(1000, 9999)}")

            # Process each waiting phraseset
            for phraseset in filtered_phrasesets:
                try:
                    # Generate AI vote choice
                    chosen_phrase = await self.generate_vote_choice(phraseset)

                    # Use VoteService for centralized voting logic
                    vote = await vote_service.submit_system_vote(
                        phraseset=phraseset,
                        player=ai_vote_player,
                        chosen_phrase=chosen_phrase,
                        transaction_service=transaction_service,
                    )

                    stats["votes_generated"] += 1
                    logger.info(
                        f"AI generated vote '{vote.voted_phrase}' for phraseset {phraseset.phraseset_id} "
                        f"({'CORRECT' if vote.correct else 'INCORRECT'}, payout: ${vote.payout})"
                    )

                except Exception as e:
                    logger.error(f"Failed to generate AI vote for phraseset {phraseset.phraseset_id}: {e}")
                    stats["errors"] += 1
                    continue
            
            # Commit all changes
            await self.db.commit()

        except Exception as exc:
            logger.error(f"AI backup cycle failed: {exc}")
            await self.db.rollback()
            stats["errors"] += 1

        finally:
            logger.info(f"AI backup cycle completed: {stats}")
