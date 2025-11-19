"""
AI Service for automated hint, copy, and vote generation.

This service provides AI-generated hints, backup copies and votes when human players
are unavailable, supporting multiple AI providers (OpenAI, Gemini)
with configurable fallback behavior and comprehensive metrics tracking.
"""

import logging
import random
from uuid import UUID

from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.player_base import PlayerBase
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.phraseset_activity import PhrasesetActivity
from backend.models.qf.vote import Vote
from backend.models.qf.ai_phrase_cache import QFAIPhraseCache
from backend.services.ai.metrics_service import AIMetricsService, MetricsTracker
from backend.services.qf import QueueService
from backend.utils.model_registry import GameType
from .prompt_builder import build_copy_prompt
from backend.utils.passwords import hash_password
from backend.services.username_service import UsernameService
from backend.services.ai.openai_api import generate_copy as openai_generate_copy
from backend.services.ai.gemini_api import generate_copy as gemini_generate_copy

logger = logging.getLogger(__name__)


AI_PLAYER_EMAIL_DOMAIN = "@quipflip.internal"
QF_AI_COPY_PLAYER_EMAIL = f"ai_copy{AI_PLAYER_EMAIL_DOMAIN}"
IR_AI_PLAYER_EMAIL = "ai_backronym_001@initialreaction.internal"


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
            from backend.services import get_phrase_validation_client
            self.phrase_validator = get_phrase_validation_client()
        else:
            from backend.services import get_phrase_validator
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
            logger.debug("Using OpenAI as AI copy provider")
            return "openai"
        elif configured_provider == "gemini" and gemini_key:
            logger.debug("Using Gemini as AI copy provider")
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

    async def get_or_create_ai_player(self, game_type: GameType, email: str | None = None) -> PlayerBase:
        """
        Get or create an AI player account for the specified game type.

        Args:
            game_type: The game type (QF or IR) to create the AI player for
            email: Optional custom email, defaults to game-specific AI email

        Returns:
            The AI player instance

        Raises:
            AIServiceError: If AI player cannot be created or is in invalid state

        Note:
            Transaction management is handled by the caller (run_backup_cycle).
            This method should NOT commit or refresh the session.
        """
        try:
            # Determine target email based on game type
            if email:
                target_email = email.strip().lower()
            elif game_type == GameType.QF:
                target_email = QF_AI_COPY_PLAYER_EMAIL
            elif game_type == GameType.IR:
                target_email = IR_AI_PLAYER_EMAIL
            else:
                raise ValueError(f"Unsupported game type: {game_type}")

            # Instantiate the correct player service and model based on game type
            if game_type == GameType.QF:
                from backend.models.qf.player import QFPlayer
                from backend.services.qf.player_service import PlayerService
                player_model = QFPlayer
            elif game_type == GameType.IR:
                from backend.models.ir.player import IRPlayer
                from backend.services.ir.player_service import PlayerService
                player_model = IRPlayer
            else:
                raise ValueError(f"Unsupported game type: {game_type}")

            # Check if AI player exists using the correct model
            result = await self.db.execute(
                select(player_model).where(player_model.email == target_email)
            )
            ai_player = result.scalar_one_or_none()

            if not ai_player:
                # Create AI player using the correct service
                player_service = PlayerService(self.db)
                
                # Generate unique username
                username_service = UsernameService(self.db, game_type=game_type)
                username = await username_service.generate_unique_username()

                ai_player = await player_service.create_player(
                    username=username,
                    email=target_email,
                    password_hash=hash_password("not-used-for-ai-player"),
                )
                logger.info(f"Created {game_type.value} AI backup player account: {username}")
            else:
                # Validate AI player is in good state (QF-specific validations)
                if game_type == GameType.QF:
                    if ai_player.wallet < 0:
                        logger.warning(
                            f"AI player has negative wallet: {ai_player.wallet}. "
                            "This may indicate an issue with payout logic."
                        )

                    # Check for stuck active rounds (shouldn't happen, but handle gracefully)
                    if hasattr(ai_player, 'active_round_id') and ai_player.active_round_id:
                        logger.warning(
                            f"AI player has stuck active round: {ai_player.active_round_id}. "
                            "Clearing it to allow new operations."
                        )
                        # Clear the stuck round - AI doesn't use traditional rounds
                        ai_player.active_round_id = None
                        await self.db.flush()

            return ai_player

        except Exception as e:
            logger.error(f"Failed to get/create {game_type.value} AI player: {e}")
            raise AIServiceError(f"{game_type.value}_ai_player_init_failed") from e

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

    async def _get_existing_copy_phrase(self, prompt_round_id: UUID | None) -> str | None:
        """Fetch an existing submitted copy phrase for the prompt round, if any."""
        if not prompt_round_id:
            return None

        result = await self.db.execute(
            select(Round.copy_phrase)
            .where(Round.prompt_round_id == prompt_round_id)
            .where(Round.round_type == "copy")
            .where(Round.status == "submitted")
            .order_by(Round.created_at.asc())
            .limit(1)
        )
        return result.scalars().first()

    async def generate_and_cache_phrases(self, prompt_round: Round) -> QFAIPhraseCache:
        """
        Generate and cache multiple validated copy phrases for a prompt round.

        This is the core method that generates 5 phrases from the AI provider,
        validates all of them, and stores 3-5 valid phrases in the cache for reuse.

        Uses distributed locking to prevent duplicate AI generation for the same prompt.

        Args:
            prompt_round: The prompt round to generate phrases for

        Returns:
            AIPhraseCache record with 3-5 validated phrases

        Raises:
            AICopyError: If fewer than 3 valid phrases can be generated
        """
        import uuid as uuid_module
        from backend.utils import lock_client

        # Use distributed lock to prevent duplicate AI generation for the same prompt
        lock_name = f"ai_phrase_generation:{prompt_round.round_id}"
        
        try:
            with lock_client.lock(lock_name, timeout=30):
                # Check if cache already exists (double-check inside lock)
                result = await self.db.execute(
                    select(QFAIPhraseCache)
                    .where(QFAIPhraseCache.prompt_round_id == prompt_round.round_id)
                )
                existing_cache = result.scalar_one_or_none()

                if existing_cache:
                    logger.debug(f"Using existing phrase cache for prompt_round {prompt_round.round_id}")
                    return existing_cache

                # Generate new phrases
                original_phrase = prompt_round.submitted_phrase
                other_copy_phrase = await self._get_existing_copy_phrase(prompt_round.round_id)

                # Build prompt and get common words
                ai_prompt = build_copy_prompt(original_phrase, other_copy_phrase)
                common_words = await self.get_common_words()
                if not isinstance(common_words, (list, tuple)):
                    logger.warning(f"common_words is not iterable: {type(common_words)}, using empty list")
                    common_words = []

                common_words = [word for word in common_words if len(word) > 3]
                ai_prompt = ai_prompt.format(common_words=", ".join(common_words))

                # Don't create cache until validation succeeds - avoids FK constraint errors
                cache_id = uuid_module.uuid4()

                async with MetricsTracker(
                        self.metrics_service,
                        operation_type="copy_generation",
                        provider=self.provider,
                        model=self.ai_model,
                        cache_id=None,  # Will be set after cache is successfully created
                ) as tracker:
                    try:
                        # Generate using configured provider
                        if self.provider == "openai":
                            test_phrases = await openai_generate_copy(
                                prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)
                        else:  # gemini
                            test_phrases = await gemini_generate_copy(
                                prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)
                        test_phrases = test_phrases.split(";")
                    except Exception as e:
                        # Wrap API exceptions in AICopyError
                        logger.error(f"Failed to generate AI copy: {e}")
                        raise AICopyError(f"Failed to generate AI copy using {ai_prompt=}: {e}")

                    # Validate all phrases
                    validated_phrases = []
                    errors = []
                    for phrase in test_phrases:
                        phrase = phrase.strip()
                        is_valid, error_message = await self.phrase_validator.validate_copy(
                            phrase,
                            original_phrase,
                            other_copy_phrase,
                            prompt_round.prompt_text,
                        )
                        if is_valid:
                            validated_phrases.append(phrase)
                        else:
                            errors.append((phrase, error_message))
                            logger.info(f"AI generated invalid copy phrase '{phrase}': {error_message}")

                    # Require at least 3 valid phrases
                    if len(validated_phrases) < 3:
                        tracker.set_result(
                            "",
                            success=False,
                            response_length=0,
                            validation_passed=False,
                        )
                        raise AICopyError(
                            f"AI generated only {len(validated_phrases)} valid phrases (need 3+) for "
                            f"{original_phrase=} {other_copy_phrase=}: {errors=}"
                        )

                    # Create and store cache now that validation succeeded
                    cache = QFAIPhraseCache(
                        cache_id=cache_id,
                        prompt_round_id=prompt_round.round_id,
                        original_phrase=original_phrase,
                        prompt_text=prompt_round.prompt_text,
                        validated_phrases=validated_phrases[:5],  # Limit to 5
                        generation_provider=self.provider,
                        generation_model=self.ai_model,
                    )
                    self.db.add(cache)
                    await self.db.flush()

                    # Update tracker with cache_id now that cache exists in DB
                    tracker.cache_id = str(cache.cache_id)

                    # Track successful generation
                    tracker.set_result(
                        f"{len(validated_phrases)} phrases",
                        success=True,
                        response_length=sum(len(p) for p in validated_phrases),
                        validation_passed=True,
                    )

                    logger.info(
                        f"AI ({self.provider}) generated and cached {len(validated_phrases)} valid phrases "
                        f"for prompt_round {prompt_round.round_id}"
                    )
                    return cache
                    
        except TimeoutError:
            logger.warning(f"Could not acquire lock for AI phrase generation of prompt round {prompt_round.round_id}, "
                           f"another process may be handling it")
            # Check one more time if cache was created by another process
            result = await self.db.execute(
                select(QFAIPhraseCache)
                .where(QFAIPhraseCache.prompt_round_id == prompt_round.round_id)
            )
            existing_cache = result.scalar_one_or_none()
            if existing_cache:
                logger.debug(f"Using cache created by another process for prompt_round {prompt_round.round_id}")
                return existing_cache
            else:
                raise AICopyError(f"Could not acquire lock for AI phrase generation and no cache exists")
        except Exception as exc:
            logger.error(
                f"Error acquiring lock for AI phrase generation of prompt round {prompt_round.round_id}: {exc}",
                exc_info=True)
            raise AICopyError(f"AI phrase generation failed: {str(exc)}") from exc

    async def revalidate_cached_phrases(self, prompt_round: Round) -> QFAIPhraseCache | None:
        """Re-run phrase validation on cached phrases and refresh the cache if needed."""

        from backend.utils import lock_client

        lock_name = f"ai_phrase_generation:{prompt_round.round_id}"

        try:
            with lock_client.lock(lock_name, timeout=30):
                result = await self.db.execute(
                    select(QFAIPhraseCache)
                    .where(QFAIPhraseCache.prompt_round_id == prompt_round.round_id)
                )
                cache = result.scalar_one_or_none()

                if not cache or not cache.validated_phrases:
                    return cache

                other_copy_phrase = await self._get_existing_copy_phrase(prompt_round.round_id)
                valid_phrases: list[str] = []

                for phrase in cache.validated_phrases:
                    is_valid, error_message = await self.phrase_validator.validate_copy(
                        phrase,
                        prompt_round.submitted_phrase,
                        other_copy_phrase,
                        prompt_round.prompt_text,
                    )

                    if is_valid:
                        valid_phrases.append(phrase)
                    else:
                        logger.info(
                            f"Cached AI phrase invalidated after first copy submission: {phrase} ({error_message})")

                if len(valid_phrases) >= 3:
                    cache.validated_phrases = valid_phrases
                    await self.db.flush()
                    return cache

                logger.info(
                    f"Cached AI phrases for {prompt_round.round_id=} fell below 3 after revalidation; regenerating")

                await self.db.delete(cache)
                await self.db.flush()
        except TimeoutError:
            logger.warning(f"Could not acquire lock for AI phrase revalidation of {prompt_round.round_id=}")
            return None

        return await self.generate_and_cache_phrases(prompt_round)

    async def generate_copy_phrase(self, original_phrase: str, prompt_round: Round) -> str:
        """
        Generate a copy phrase using cached validated phrases.

        This method now uses the phrase cache to avoid redundant AI API calls.
        It selects a random phrase from the cache and removes it from the list.

        Args:
            original_phrase: The original phrase to create a copy of
            prompt_round: The prompt round object to get context and check existing copies

        Returns:
            Generated and validated copy phrase

        Raises:
            AICopyError: If generation or validation fails
        """
        # Get or generate phrase cache
        cache = await self.generate_and_cache_phrases(prompt_round)

        # Select random phrase from cache
        if not cache.validated_phrases or len(cache.validated_phrases) == 0:
            # Cache is empty, regenerate
            logger.warning(f"Phrase cache for {prompt_round.round_id=} is empty, regenerating...")
            # Delete empty cache and regenerate
            await self.db.delete(cache)
            await self.db.flush()
            cache = await self.generate_and_cache_phrases(prompt_round)

        # Select random phrase
        selected_phrase = random.choice(cache.validated_phrases)

        # Remove selected phrase from cache (so next backup copy gets a different one)
        cache.validated_phrases = [p for p in cache.validated_phrases if p != selected_phrase]
        cache.used_for_backup_copy = True
        await self.db.flush()

        logger.info(
            f"AI ({self.provider}) {selected_phrase=} for {original_phrase=} "
            f"({len(cache.validated_phrases)} phrases remaining in cache)"
        )
        return selected_phrase

    async def get_hints(self, prompt_round: Round, count: int = 3) -> list[str]:
        """
        Get hint phrases from the phrase cache, or generate and cache if not present.

        This method reuses the phrase cache created by generate_and_cache_phrases(),
        eliminating the need for separate hint generation. All players get the same
        hints (phrases are not removed from cache).

        Args:
            prompt_round: The prompt round containing the original phrase and context
            count: Number of hints to return (default: 3)

        Returns:
            List of validated hint phrases ready for display to the player

        Raises:
            AICopyError: If hints cannot be generated or cache is unavailable
        """
        if count <= 0:
            raise AICopyError("Hint count must be at least 1")
        if not prompt_round or not prompt_round.round_id:
            raise AICopyError("Prompt round is required to generate hints")
        if not prompt_round.submitted_phrase:
            raise AICopyError("Cannot generate hints before the original phrase is submitted")

        # Get or generate phrase cache
        cache = await self.generate_and_cache_phrases(prompt_round)

        # Mark cache as used for hints
        cache.used_for_hints = True
        await self.db.flush()

        # Return first 'count' phrases (don't remove from cache - all players get same hints)
        hints = cache.validated_phrases[:count]

        if len(hints) == 0:
            raise AICopyError("Phrase cache is empty, cannot provide hints")

        logger.info(f"AI ({self.provider}) provided {len(hints)} cached hints for prompt_round {prompt_round.round_id}")

        return hints

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
        phrases = [phraseset.original_phrase, phraseset.copy_phrase_1, phraseset.copy_phrase_2]
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

    async def _has_ai_attempted_prompt_recently(self, prompt_round_id: str, lookback_hours: int = 6) -> bool:
        """
        Check if AI has already attempted to generate a copy for this prompt.

        Args:
            prompt_round_id: The prompt round ID to check
            lookback_hours: How far back to look for attempts (default: 24 hours)

        Returns:
            True if AI has attempted this prompt recently, False otherwise
        """
        from backend.models.qf.ai_metric import QFAIMetric
        
        # Look back specified hours for attempts
        since = datetime.now(UTC) - timedelta(hours=lookback_hours)
        
        # Check if there are any copy generation attempts for this prompt
        # We use the prompt round ID in error messages, so we can search for it
        result = await self.db.execute(
            select(QFAIMetric.metric_id)
            .where(QFAIMetric.operation_type == "copy_generation")
            .where(QFAIMetric.created_at >= since)
            .where(QFAIMetric.error_message.contains(str(prompt_round_id)))
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
            ai_copy_player = await self.get_or_create_ai_player(GameType.QF)

            # Query for submitted prompt rounds that:
            # 1. Don't have a phraseset yet (still waiting for copies)
            # 2. Are older than the backup delay
            # 3. Don't belong to the AI player (avoid self-copies)
            # 4. Haven't been copied by the AI player already
            
            # Determine backup delay
            cutoff_time = datetime.now(UTC) - timedelta(minutes=self.settings.ai_backup_delay_minutes)

            # Get all prompt rounds that meet our basic criteria
            from backend.models.qf.player import QFPlayer
            
            result = await self.db.execute(
                select(Round)
                .join(QFPlayer, QFPlayer.player_id == Round.player_id)
                .outerjoin(PhrasesetActivity, PhrasesetActivity.prompt_round_id == Round.round_id)
                .where(Round.round_type == 'prompt')
                .where(Round.status == 'submitted')
                .where(Round.created_at <= cutoff_time)
                .where(Round.player_id != ai_copy_player.player_id)
                .where(PhrasesetActivity.phraseset_id.is_(None))  # Not yet a phraseset
                .order_by(Round.created_at.asc())  # Process oldest first
                .limit(self.settings.ai_backup_batch_size)  # Configurable batch size
            )
            
            waiting_prompts = set(result.scalars().all())
            
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
            
            # Filter out prompts that already have a phrase cache with backup copies used
            # (This prevents wasting cached phrases on redundant backup attempts)
            final_prompts = []
            for prompt_round in filtered_prompts:
                # Check if phrase cache exists and has been used for backup
                cache_result = await self.db.execute(
                    select(QFAIPhraseCache.cache_id)
                    .where(QFAIPhraseCache.prompt_round_id == prompt_round.round_id)
                    .where(QFAIPhraseCache.used_for_backup_copy == True)
                )
                cache_exists = cache_result.scalar_one_or_none() is not None

                if not cache_exists:
                    final_prompts.append(prompt_round)
                else:
                    stats["prompts_filtered_already_attempted"] += 1
                    logger.info(f"Skipping prompt {prompt_round.round_id} - AI cache already used for backup")
            
            stats["prompts_checked"] = len(final_prompts)
            logger.info(
                f"Found {len(final_prompts)} prompts waiting for AI backup copies "
                f"(filtered out {stats['prompts_filtered_already_attempted']} already attempted)"
            )

            # Process each waiting prompt
            for prompt_round in final_prompts:
                try:
                    # Try to claim the prompt in the queue so only one worker (AI or other) processes it
                    claimed = QueueService.remove_prompt_round_from_queue(prompt_round.round_id)
                    if not claimed:
                        # Someone else claimed or removed it from the queue
                        logger.info(f"Skipping prompt {prompt_round.round_id} - could not claim from queue")
                        continue

                    # Generate AI copy phrase with proper validation context
                    copy_phrase = await self.generate_copy_phrase(prompt_round.submitted_phrase, prompt_round)

                    # Create copy round for AI player
                    from backend.services import RoundService
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
                    # Flush to ensure copy_round is visible to create_phraseset_if_ready query
                    await self.db.flush()

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
                    # Put the prompt back into the queue so it can be retried later
                    try:
                        QueueService.add_prompt_round_to_queue(prompt_round.round_id)
                        logger.info(f"Re-enqueued prompt {prompt_round.round_id} after AI failure")
                    except Exception as q_e:
                        logger.error(f"Failed to re-enqueue prompt {prompt_round.round_id}: {q_e}")
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
            from backend.models.qf.player import QFPlayer
            
            human_vote_phrasesets_subquery = (
                select(Vote.phraseset_id)
                .join(QFPlayer, QFPlayer.player_id == Vote.player_id)
                .where(~QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"))
                .distinct()
            )

            phraseset_result = await self.db.execute(
                select(Phraseset)
                .where(Phraseset.status.in_(["open", "closing"]))
                .where(Phraseset.created_at <= cutoff_time)
                .where(Phraseset.phraseset_id.in_(human_vote_phrasesets_subquery))
                .options(
                    selectinload(Phraseset.prompt_round),
                    selectinload(Phraseset.copy_round_1),
                    selectinload(Phraseset.copy_round_2),
                )
                .order_by(Phraseset.created_at.asc())  # Process oldest first
                .limit(self.settings.ai_backup_batch_size)  # Use configured batch size
            )
            
            # Get or create AI voter player (within transaction)
            ai_voter_player = await self.get_or_create_ai_player(
                GameType.QF, email=f"ai_voter_{uuid.uuid4().hex[:4]}{AI_PLAYER_EMAIL_DOMAIN}")

            # Filter out phrasesets with activity after cutoff_time and in which this AI has voted
            waiting_phrasesets = list(phraseset_result.scalars().all())
            filtered_phrasesets = []
            for phraseset in waiting_phrasesets:
                activity = await self.db.execute(
                    select(PhrasesetActivity)
                    .where(PhrasesetActivity.phraseset_id == phraseset.phraseset_id)
                    .where(PhrasesetActivity.created_at > cutoff_time)
                )
                if len(activity.scalars().all()) == 0:
                    voter_activity = await self.db.execute(
                        select(PhrasesetActivity)
                        .where(PhrasesetActivity.phraseset_id == phraseset.phraseset_id)
                        .where(PhrasesetActivity.player_id == ai_voter_player.player_id)
                    )
                    if len(voter_activity.scalars().all()) == 0:
                        filtered_phrasesets.append(phraseset)

            stats["phrasesets_checked"] = len(filtered_phrasesets)
            logger.info(
                f"Found {len(filtered_phrasesets)} phrasesets waiting for AI backup votes: {filtered_phrasesets}")
            
            # Initialize services once for all votes (performance improvement)
            from backend.services import VoteService
            from backend.services import TransactionService
            vote_service = VoteService(self.db)
            transaction_service = TransactionService(self.db)

            # Process each waiting phraseset
            for phraseset in filtered_phrasesets:
                try:
                    # Generate AI vote choice
                    chosen_phrase = await self.generate_vote_choice(phraseset)

                    # Use VoteService for centralized voting logic
                    vote = await vote_service.submit_system_vote(
                        phraseset=phraseset,
                        player=ai_voter_player,
                        chosen_phrase=chosen_phrase,
                        transaction_service=transaction_service,
                    )

                    stats["votes_generated"] += 1
                    logger.info(
                        f"AI generated vote '{vote.voted_phrase}' for phraseset {phraseset.phraseset_id} "
                        f"({'CORRECT' if vote.correct else 'INCORRECT'}, payout: {vote.payout})"
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

    async def generate_backronym(self, word: str) -> list[str]:
        """
        Generate a clever backronym for a word.

        Args:
            word: The target word (e.g., "FROG", "CAT")

        Returns:
            list[str]: Array of words forming the backronym

        Raises:
            AICopyError: If backronym generation fails
        """
        from backend.services.ai.prompt_builder import build_backronym_prompt

        try:
            word_upper = word.upper()
            letter_count = len(word_upper)

            # Build prompt
            prompt = build_backronym_prompt(word_upper, count=1)

            # Generate using configured provider
            if self.provider == "openai":
                response_text = await openai_generate_copy(prompt, self.ai_model)
            else:
                response_text = await gemini_generate_copy(prompt, self.ai_model)

            # Parse response - should be words separated by spaces
            words = response_text.strip().split()

            # Validate we got the right number of words
            if len(words) != letter_count:
                logger.warning(
                    f"AI generated {len(words)} words for {word} "
                    f"(expected {letter_count}), truncating/padding"
                )
                words = words[:letter_count]
                while len(words) < letter_count:
                    words.append("WORD")

            # Validate each word is 2-15 chars
            validated_words = []
            for w in words:
                w_clean = w.upper().replace(".", "").replace(",", "").strip()
                if 2 <= len(w_clean) <= 15 and w_clean.isalpha():
                    validated_words.append(w_clean)
                else:
                    logger.warning(f"Invalid word in backronym: {w}")
                    validated_words.append("WORD")

            logger.info(f"Generated backronym for {word}: {' '.join(validated_words)}")
            return validated_words

        except Exception as e:
            logger.error(f"Failed to generate backronym for {word}: {e}")
            raise AICopyError(f"Backronym generation failed: {str(e)}") from e

    async def generate_backronym_vote(self, word: str, backronyms: list[list[str]]) -> int:
        """
        Generate AI vote on backronym entries.

        Args:
            word: The target word
            backronyms: List of backronym word arrays (e.g., [["FUNNY", "RODENT"], ...])

        Returns:
            int: Index of chosen backronym (0-based)

        Raises:
            AIVoteError: If vote generation fails
        """
        from backend.services.ai.prompt_builder import build_backronym_vote_prompt

        try:
            word_upper = word.upper()

            # Format backronyms for prompt
            backronym_strs = [" ".join(b) if isinstance(b, list) else b for b in backronyms]

            # Build prompt
            prompt = build_backronym_vote_prompt(word_upper, backronym_strs)

            # Generate using configured provider
            if self.provider == "openai":
                response_text = await openai_generate_copy(prompt, self.ai_model)
            else:
                response_text = await gemini_generate_copy(prompt, self.ai_model)

            # Parse response - should be a number 1-5
            try:
                choice_num = int(response_text.strip())
                # Convert to 0-based index
                choice_index = choice_num - 1

                # Validate index
                if 0 <= choice_index < len(backronyms):
                    logger.info(
                        f"AI voted on {word}: chose option {choice_num} "
                        f"({backronym_strs[choice_index]})"
                    )
                    return choice_index
                else:
                    logger.warning(
                        f"AI vote out of range: {choice_num} "
                        f"(valid: 1-{len(backronyms)}), defaulting to 0"
                    )
                    return 0

            except ValueError:
                logger.warning(f"AI vote response not a number: {response_text}")
                return 0

        except Exception as e:
            logger.error(f"Failed to generate backronym vote for {word}: {e}")
            raise AIVoteError(f"Backronym vote generation failed: {str(e)}") from e

    async def generate_party_prompt(self, prompt_text: str) -> str:
        """
        Generate a creative phrase for a Party Mode prompt round.

        Args:
            prompt_text: The prompt to respond to

        Returns:
            Generated phrase (2-30 characters)

        Raises:
            AICopyError: If generation fails
        """
        from backend.services.ai.prompt_builder import build_party_prompt_generation

        try:
            # Build prompt for phrase generation
            ai_prompt = build_party_prompt_generation(prompt_text)

            # Generate using configured provider
            if self.provider == "openai":
                response_text = await openai_generate_copy(
                    prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)
            else:  # gemini
                response_text = await gemini_generate_copy(
                    prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)

            # Clean up response
            phrase = response_text.strip().upper()

            # Validate length
            if len(phrase) < 2 or len(phrase) > 30:
                logger.warning(f"AI phrase length out of range: {len(phrase)} chars, truncating")
                phrase = phrase[:30] if len(phrase) > 30 else "AI PHRASE"

            logger.info(f"AI ({self.provider}) generated party prompt phrase: {phrase}")
            return phrase

        except Exception as e:
            logger.error(f"Failed to generate party prompt phrase: {e}")
            raise AICopyError(f"Party prompt generation failed: {str(e)}") from e

    async def generate_party_copy(
        self,
        original_phrase: str,
        prompt_text: str,
        other_copy_phrase: str | None = None,
    ) -> str:
        """
        Generate a copy phrase for Party Mode.

        Reuses the existing copy generation logic but without caching
        since Party Mode rounds are one-time events.

        Args:
            original_phrase: The original phrase to copy
            prompt_text: The prompt that generated the original phrase
            other_copy_phrase: Optional existing copy to avoid

        Returns:
            Generated and validated copy phrase

        Raises:
            AICopyError: If generation or validation fails
        """
        # Build prompt and get common words
        ai_prompt = build_copy_prompt(original_phrase, other_copy_phrase)
        common_words = await self.get_common_words()
        if not isinstance(common_words, (list, tuple)):
            logger.warning(f"common_words is not iterable: {type(common_words)}, using empty list")
            common_words = []

        common_words = [word for word in common_words if len(word) > 3]
        ai_prompt = ai_prompt.format(common_words=", ".join(common_words))

        async with MetricsTracker(
                self.metrics_service,
                operation_type="party_copy_generation",
                provider=self.provider,
                model=self.ai_model,
        ) as tracker:
            try:
                # Generate using configured provider
                if self.provider == "openai":
                    test_phrases = await openai_generate_copy(
                        prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)
                else:  # gemini
                    test_phrases = await gemini_generate_copy(
                        prompt=ai_prompt, model=self.ai_model, timeout=self.settings.ai_timeout_seconds)
                test_phrases = test_phrases.split(";")
            except Exception as e:
                logger.error(f"Failed to generate AI copy: {e}")
                tracker.set_result("", success=False, response_length=0, validation_passed=False)
                raise AICopyError(f"Failed to generate AI copy: {e}")

            # Validate phrases
            for phrase in test_phrases:
                phrase = phrase.strip()
                is_valid, error_message = await self.phrase_validator.validate_copy(
                    phrase,
                    original_phrase,
                    other_copy_phrase,
                    prompt_text,
                )
                if is_valid:
                    tracker.set_result(
                        phrase,
                        success=True,
                        response_length=len(phrase),
                        validation_passed=True,
                    )
                    logger.info(f"AI ({self.provider}) generated party copy: {phrase}")
                    return phrase

            # No valid phrases found
            tracker.set_result("", success=False, response_length=0, validation_passed=False)
            raise AICopyError(f"AI generated no valid copy phrases for {original_phrase=}")

    async def generate_party_vote(self, prompt_text: str, phrases: list[str]) -> str:
        """
        Generate a vote choice for Party Mode.

        Args:
            prompt_text: The prompt text
            phrases: List of phrase options to choose from

        Returns:
            The chosen phrase (one of the phrases in the list)

        Raises:
            AIVoteError: If vote generation fails
        """
        from backend.services.ai.vote_helper import generate_vote_choice

        # Shuffle phrases for randomness
        import random
        shuffled_phrases = phrases.copy()
        random.shuffle(shuffled_phrases)

        async with MetricsTracker(
                self.metrics_service,
                operation_type="party_vote_generation",
                provider=self.provider,
                model=self.ai_model,
        ) as tracker:
            # Generate vote choice
            choice_index = await generate_vote_choice(
                prompt_text=prompt_text,
                phrases=shuffled_phrases,
                provider=self.provider,
                model=self.ai_model,
                timeout=self.settings.ai_timeout_seconds,
            )

            chosen_phrase = shuffled_phrases[choice_index]

            # Track the vote
            tracker.set_result(
                chosen_phrase,
                success=True,
                response_length=len(str(choice_index)),
            )

            logger.info(f"AI ({self.provider}) voted for party mode: '{chosen_phrase}'")
            return chosen_phrase

    async def run_ir_backup_cycle(self) -> None:
        """
        Run backup cycle for Initial Reaction game.

        Fills stalled backronym sets with AI entries and votes.
        """
        from backend.services.ir.backronym_set_service import BackronymSetService

        stats = {
            "sets_checked": 0,
            "entries_generated": 0,
            "votes_generated": 0,
            "errors": 0,
        }

        try:
            # Get or create IR AI player
            ai_player = await self.get_or_create_ai_player(GameType.IR)

            set_service = BackronymSetService(self.db)

            # Get stalled open sets
            stalled_open = await set_service.get_stalled_open_sets(
                minutes=self.settings.ir_ai_backup_delay_minutes
            )
            stats["sets_checked"] = len(stalled_open)

            # Fill stalled open sets
            for set_obj in stalled_open:
                try:
                    while set_obj.entry_count < 5:
                        # Generate backronym
                        backronym = await self.generate_backronym(set_obj.word)

                        # Add entry
                        entry = await set_service.add_entry(
                            set_id=str(set_obj.set_id),
                            player_id=str(ai_player.player_id),
                            backronym_text=backronym,
                            is_ai=True,
                        )
                        stats["entries_generated"] += 1
                        logger.info(
                            f"AI entry {entry.entry_id} added to set {set_obj.set_id}"
                        )

                        # Refresh set to get updated count
                        set_obj = await set_service.get_set_by_id(str(set_obj.set_id))
                        if not set_obj:
                            break

                except Exception as e:
                    logger.error(f"Error filling set {set_obj.set_id}: {e}")
                    stats["errors"] += 1

            # Get stalled voting sets
            stalled_voting = await set_service.get_stalled_voting_sets(minutes=self.settings.ir_ai_backup_delay_minutes)

            # Fill voting for stalled sets
            for set_obj in stalled_voting:
                try:
                    # Get entries for this set
                    from sqlalchemy import select
                    from backend.models.ir.backronym_entry import BackronymEntry

                    entries_stmt = select(BackronymEntry).where(BackronymEntry.set_id == str(set_obj.set_id))
                    entries_result = await self.db.execute(entries_stmt)
                    entries = entries_result.scalars().all()

                    if len(entries) < 5:
                        logger.warning(f"Set {set_obj.set_id} has < 5 entries, skipping voting fill")
                        continue

                    # Generate votes until we have 5
                    while set_obj.vote_count < 5:
                        # Get backronym texts as word arrays
                        backronym_strs = [e.backronym_text for e in entries]

                        # Generate vote
                        chosen_index = await self.generate_backronym_vote(set_obj.word, backronym_strs)
                        chosen_entry_id = entries[chosen_index].entry_id

                        # Add vote
                        vote = await set_service.add_vote(
                            set_id=str(set_obj.set_id),
                            player_id=str(ai_player.player_id),
                            chosen_entry_id=str(chosen_entry_id),
                            is_participant_voter=False,
                            is_ai=True,
                        )
                        stats["votes_generated"] += 1
                        logger.info(f"AI vote {vote.vote_id} added to set {set_obj.set_id}")

                        # Refresh set
                        set_obj = await set_service.get_set_by_id(str(set_obj.set_id))
                        if not set_obj:
                            break

                except Exception as e:
                    logger.error(f"Error filling votes for set {set_obj.set_id}: {e}")
                    stats["errors"] += 1

            await self.db.commit()
            logger.info(f"IR backup cycle completed: {stats}")

        except Exception as exc:
            logger.error(f"IR backup cycle failed: {exc}")
            await self.db.rollback()
            stats["errors"] += 1
