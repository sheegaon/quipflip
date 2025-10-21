"""
AI Copy Service for automated backup copy and vote generation.

This service provides AI-generated backup copies and votes when human players
are unavailable, supporting multiple AI providers (OpenAI, Gemini)
with configurable fallback behavior and comprehensive metrics tracking.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.services.phrase_validator import PhraseValidator
from backend.services.ai_metrics_service import AIMetricsService, MetricsTracker
from backend.services.player_service import PlayerService
from backend.services.round_service import RoundService

logger = logging.getLogger(__name__)


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

    def __init__(self, db: AsyncSession, validator: PhraseValidator):
        """
        Initialize AI copy service.

        Args:
            db: Database session
            validator: Phrase validator for checking generated phrases
        """
        self.db = db
        self.validator = validator
        self.metrics_service = AIMetricsService(db)
        self.settings = get_settings()

        # Determine which provider to use based on config and available API keys
        self.provider = self._determine_provider()

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
        configured_provider = self.settings.ai_copy_provider.lower()
        openai_key = self.settings.openai_api_key
        gemini_key = self.settings.gemini_api_key

        # Check if configured provider is available
        if configured_provider == "openai" and openai_key:
            logger.info("Using OpenAI as AI copy provider")
            return "openai"
        elif configured_provider == "gemini" and gemini_key:
            logger.info("Using Gemini as AI copy provider")
            return "gemini"

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
        raise AICopyError("No AI provider configured - set OPENAI_API_KEY or GEMINI_API_KEY")

    async def _get_or_create_ai_player(self) -> Player:
        """
        Get or create the AI player account.

        Returns:
            The AI player instance

        Note:
            Transaction management is handled by the caller (run_backup_cycle).
            This method should NOT commit or refresh the session.
        """
        # Check if AI player exists
        result = await self.db.execute(select(Player).where(Player.username == "AI_BACKUP"))
        ai_player = result.scalar_one_or_none()

        if not ai_player:
            # Create AI player
            player_service = PlayerService(self.db)

            ai_player = await player_service.create_player(
                username="AI_BACKUP",
                email="ai@quipflip.internal",
                password_hash="not-used-for-ai-player",
                pseudonym="Clever Lexical Runner",
                pseudonym_canonical="cleverlexicalrunner",
            )
            # Note: Do not commit here - let caller manage transaction
            logger.info("Created AI backup player account")

        return ai_player

    async def generate_copy_phrase(self, original_phrase: str) -> str:
        """
        Generate a copy phrase using the configured AI provider with metrics tracking.

        Args:
            original_phrase: The original phrase to create a copy of

        Returns:
            Generated and validated copy phrase

        Raises:
            AICopyError: If generation or validation fails
        """
        model = (
            self.settings.ai_copy_openai_model
            if self.provider == "openai"
            else self.settings.ai_copy_gemini_model
        )

        async with MetricsTracker(
                self.metrics_service,
                operation_type="copy_generation",
                provider=self.provider,
                model=model,
        ) as tracker:
            try:
                # Generate using configured provider
                if self.provider == "openai":
                    from backend.services.openai_api import generate_copy as openai_generate
                    phrase = await openai_generate(
                        original_phrase=original_phrase,
                        model=self.settings.ai_copy_openai_model,
                        timeout=self.settings.ai_copy_timeout_seconds,
                    )
                else:  # gemini
                    from backend.services.gemini_api import generate_copy as gemini_generate
                    phrase = await gemini_generate(
                        original_phrase=original_phrase,
                        model=self.settings.ai_copy_gemini_model,
                        timeout=self.settings.ai_copy_timeout_seconds,
                    )
            except Exception as e:
                # Wrap API exceptions in AICopyError
                logger.error(f"Failed to generate AI copy: {e}")
                raise AICopyError(f"Failed to generate AI copy: {e}")

            # Validate the generated phrase
            is_valid, error_message = self.validator.validate(phrase)

            if not is_valid:
                tracker.set_result(
                    phrase,
                    success=False,
                    response_length=len(phrase),
                    validation_passed=False,
                )
                raise AICopyError(
                    f"AI generated invalid phrase: {error_message}"
                )

            # Track successful generation
            tracker.set_result(
                phrase,
                success=True,
                response_length=len(phrase),
                validation_passed=True,
            )

            logger.info(f"AI ({self.provider}) generated valid copy: '{phrase}' for original: '{original_phrase}'")
            return phrase

    async def generate_vote_choice(self, phraseset: PhraseSet) -> str:
        """
        Generate a vote choice using the configured AI provider with metrics tracking.

        Args:
            phraseset: The phraseset to vote on (must have prompt and 3 phrases loaded)

        Returns:
            The chosen phrase (one of the 3 phrases in the phraseset)

        Raises:
            AIVoteError: If vote generation fails
        """
        from backend.services.ai_vote_helper import generate_vote_choice

        # Extract prompt and phrases
        prompt_text = phraseset.prompt_round.phrase
        phrases = [
            phraseset.prompt_round.phrase,
            phraseset.copy_round_1.phrase,
            phraseset.copy_round_2.phrase,
        ]

        model = (
            self.settings.ai_copy_openai_model
            if self.provider == "openai"
            else self.settings.ai_copy_gemini_model
        )

        async with MetricsTracker(
                self.metrics_service,
                operation_type="vote_generation",
                provider=self.provider,
                model=model,
        ) as tracker:
            # Generate vote choice
            choice_index = await generate_vote_choice(
                prompt_text=prompt_text,
                phrases=phrases,
                provider=self.provider,
                openai_model=self.settings.ai_copy_openai_model,
                gemini_model=self.settings.ai_copy_gemini_model,
                timeout=self.settings.ai_copy_timeout_seconds,
            )

            chosen_phrase = phrases[choice_index]

            # Determine if vote is correct (index 0 is the original)
            vote_correct = (choice_index == 0)

            # Track the vote
            tracker.set_result(
                chosen_phrase,
                success=True,
                response_length=len(str(choice_index)),
                vote_correct=vote_correct,
            )

            logger.info(
                f"AI ({self.provider}) voted for phrase '{chosen_phrase}' (index {choice_index}, "
                f"{'CORRECT' if vote_correct else 'INCORRECT'})"
            )

            return chosen_phrase

    async def run_backup_cycle(self) -> dict:
        """
        Run a backup cycle to provide AI copies for waiting prompts.

        This method:
        1. Finds prompts that have been waiting for copies longer than the backup delay
        2. Generates AI copies for those prompts
        3. Submits the copies as the AI player
        # TODO find and submit votes for phrasesets waiting for votes

        Returns:
            Dictionary with statistics about the backup cycle

        Note:
            This is the main entry point for the AI backup system and manages the complete transaction lifecycle.
        """
        import uuid
        from datetime import UTC

        stats = {
            "prompts_checked": 0,
            "copies_generated": 0,
            "errors": 0,
        }

        try:
            # Get or create AI player (within transaction)
            ai_player = await self._get_or_create_ai_player()

            # Find prompts waiting for copies that are older than backup delay
            cutoff_time = datetime.now(UTC) - timedelta(minutes=self.settings.ai_backup_delay_minutes)
            
            # Query for submitted prompt rounds that:
            # 1. Don't have a phraseset yet (still waiting for copies)
            # 2. Are older than the backup delay
            # 3. Don't belong to the AI player (avoid self-copies)
            # 4. Haven't been copied by the AI player already
            
            # First, get all prompt rounds that meet our basic criteria
            result = await self.db.execute(
                select(Round)
                .outerjoin(PhraseSet, PhraseSet.prompt_round_id == Round.round_id)
                .where(Round.round_type == 'prompt')
                .where(Round.status == 'submitted')
                .where(Round.created_at <= cutoff_time)
                .where(Round.player_id != ai_player.player_id)
                .where(PhraseSet.phraseset_id.is_(None))  # No phraseset yet
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
                    .where(Round.player_id == ai_player.player_id)
                )
                
                if ai_copy_result.scalar_one_or_none() is None:
                    filtered_prompts.append(prompt_round)
            
            stats["prompts_checked"] = len(filtered_prompts)
            logger.info(f"Found {len(filtered_prompts)} prompts waiting for AI backup copies")
            
            round_service = RoundService(self.db)

            # Process each waiting prompt
            for prompt_round in filtered_prompts:
                try:
                    # Generate AI copy phrase
                    copy_phrase = await self.generate_copy_phrase(prompt_round.submitted_phrase)

                    # Create copy round for AI player
                    # Start copy round for AI player
                    copy_round = Round(
                        round_id=uuid.uuid4(),
                        player_id=ai_player.player_id,
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
                        prompt_round.copy1_player_id = ai_player.player_id
                        prompt_round.phraseset_status = "waiting_copy1"
                    elif prompt_round.copy2_player_id is None:
                        prompt_round.copy2_player_id = ai_player.player_id
                        # Check if we now have both copies and can create phraseset
                        if prompt_round.copy1_player_id is not None:
                            phraseset = await round_service.create_phraseset_if_ready(prompt_round)
                            if phraseset:
                                prompt_round.phraseset_status = "active"
                    
                    stats["copies_generated"] += 1
                    logger.info(f"AI generated backup copy '{copy_phrase}' for prompt '{prompt_round.submitted_phrase}'")
                    
                except Exception as e:
                    logger.error(f"Failed to generate AI copy for prompt {prompt_round.round_id}: {e}")
                    stats["errors"] += 1
                    continue
            
            # Commit all changes
            await self.db.commit()
            logger.info(f"AI backup cycle completed: {stats}")

        except Exception as exc:
            logger.error(f"AI backup cycle failed: {exc}")
            await self.db.rollback()
            stats["errors"] += 1

        return stats
