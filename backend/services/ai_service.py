"""
AI Copy Service for automated backup copy and vote generation.

This service provides AI-generated backup copies and votes when human players
are unavailable, supporting multiple AI providers (OpenAI, Gemini)
with configurable fallback behavior and comprehensive metrics tracking.
"""

import logging
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.services.phrase_validator import PhraseValidator
from backend.services.ai_metrics_service import AIMetricsService, MetricsTracker
from backend.services.player_service import PlayerService
from backend.services.round_service import RoundService
from backend.models.vote import Vote

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

    def __init__(self, db: AsyncSession, validator: PhraseValidator):
        """
        Initialize AI service.

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
            self.settings.ai_openai_model
            if self.provider == "openai"
            else self.settings.ai_gemini_model
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
                        model=self.settings.ai_openai_model,
                        timeout=self.settings.ai_timeout_seconds,
                    )
                else:  # gemini
                    from backend.services.gemini_api import generate_copy as gemini_generate
                    phrase = await gemini_generate(
                        original_phrase=original_phrase,
                        model=self.settings.ai_gemini_model,
                        timeout=self.settings.ai_timeout_seconds,
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
            self.settings.ai_openai_model
            if self.provider == "openai"
            else self.settings.ai_gemini_model
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
                openai_model=self.settings.ai_openai_model,
                gemini_model=self.settings.ai_gemini_model,
                timeout=self.settings.ai_timeout_seconds,
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

    async def _check_and_finalize_phraseset(self, phraseset: PhraseSet):
        """
        Check if phraseset should be finalized and finalize it if necessary.
        
        This mirrors the logic from VoteService._check_and_finalize() to ensure
        AI votes trigger proper finalization when conditions are met.

        Conditions for finalization:
        - 20 votes (max)
        - OR 5+ votes AND 60 seconds elapsed since 5th vote
        - OR 3 votes AND 10 minutes elapsed since 3rd vote
        """
        should_finalize = False
        current_time = datetime.now(UTC)

        # Max votes reached
        if phraseset.vote_count >= 20:
            should_finalize = True
            logger.info(f"Phraseset {phraseset.phraseset_id} reached max votes (20) via AI vote")

        # 5+ votes and 60 seconds elapsed
        elif phraseset.vote_count >= 5 and phraseset.fifth_vote_at:
            fifth_vote_at = phraseset.fifth_vote_at
            # Handle timezone-naive datetime from database
            if fifth_vote_at.tzinfo is None:
                fifth_vote_at = fifth_vote_at.replace(tzinfo=UTC)
            
            elapsed = (current_time - fifth_vote_at).total_seconds()
            if elapsed >= 60:
                should_finalize = True
                logger.info(f"Phraseset {phraseset.phraseset_id} closing window expired (60s) after AI vote")

        # 3 votes and 10 minutes elapsed (no 5th vote)
        elif phraseset.vote_count >= 3 and phraseset.third_vote_at and not phraseset.fifth_vote_at:
            third_vote_at = phraseset.third_vote_at
            # Handle timezone-naive datetime from database
            if third_vote_at.tzinfo is None:
                third_vote_at = third_vote_at.replace(tzinfo=UTC)
                
            elapsed = (current_time - third_vote_at).total_seconds()
            if elapsed >= 600:  # 10 minutes
                should_finalize = True
                logger.info(f"Phraseset {phraseset.phraseset_id} 10min window expired after AI vote")

        if should_finalize:
            await self._finalize_phraseset(phraseset)

    async def _finalize_phraseset(self, phraseset: PhraseSet):
        """
        Finalize phraseset - calculate and distribute payouts.
        
        This mirrors the logic from VoteService._finalize_wordset() to ensure
        consistent finalization behavior for AI-triggered finalization.
        """
        from backend.services.transaction_service import TransactionService
        from backend.services.scoring_service import ScoringService
        
        # Calculate payouts
        scoring_service = ScoringService(self.db)
        payouts = await scoring_service.calculate_payouts(phraseset)

        # Create prize transactions for each contributor
        transaction_service = TransactionService(self.db)
        for role in ["original", "copy1", "copy2"]:
            payout_info = payouts[role]
            if payout_info["payout"] > 0:
                await transaction_service.create_transaction(
                    payout_info["player_id"],
                    payout_info["payout"],
                    "prize_payout",
                    phraseset.phraseset_id,
                )

        # Update phraseset status
        phraseset.status = "finalized"
        phraseset.finalized_at = datetime.now(UTC)

        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        if prompt_round:
            prompt_round.phraseset_status = "finalized"

        # Note: Activity service recording is skipped in AI backup to avoid dependency complexity
        # The finalization will still be logged via the main logger

        logger.info(
            f"AI backup finalized phraseset {phraseset.phraseset_id}: "
            f"original=${payouts['original']['payout']}, "
            f"copy1=${payouts['copy1']['payout']}, "
            f"copy2=${payouts['copy2']['payout']}"
        )

    async def run_backup_cycle(self):
        """
        Run a backup cycle to provide AI copies for waiting prompts and AI votes for waiting phrasesets.

        This method:
        1. Finds prompts that have been waiting for copies longer than the backup delay
        2. Generates AI copies for those prompts
        3. Submits the copies as the AI player
        4. Finds phrasesets that have been waiting for votes longer than the backup delay
        5. Generates AI votes for those phrasesets
        6. Submits the votes as the AI player

        Note:
            This is the main entry point for the AI backup system and manages the complete transaction lifecycle.
        """
        import uuid

        stats = {
            "prompts_checked": 0,
            "copies_generated": 0,
            "phrasesets_checked": 0,
            "votes_generated": 0,
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
                .join(Player, Player.player_id == Round.player_id)
                .outerjoin(PhraseSet, PhraseSet.prompt_round_id == Round.round_id)
                .where(Round.round_type == 'prompt')
                .where(Round.status == 'submitted')
                .where(Round.created_at <= cutoff_time)
                .where(Round.player_id != ai_player.player_id)
                .where(~Player.username.like('%test%'))  # Exclude test players
                .where(PhraseSet.phraseset_id.is_(None))  # No phraseset yet
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
                    .where(Round.player_id == ai_player.player_id)
                )
                
                if ai_copy_result.scalar_one_or_none() is None:
                    filtered_prompts.append(prompt_round)
            
            stats["prompts_checked"] = len(filtered_prompts)
            logger.info(f"Found {len(filtered_prompts)} prompts waiting for AI backup copies")
            
            # Process each waiting prompt
            for prompt_round in filtered_prompts:
                try:
                    # Generate AI copy phrase
                    copy_phrase = await self.generate_copy_phrase(prompt_round.submitted_phrase)

                    # Create copy round for AI player
                    round_service = RoundService(self.db)

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
                    logger.info(f"AI generated copy '{copy_phrase}' for prompt '{prompt_round.submitted_phrase}'")
                    
                except Exception as e:
                    logger.error(f"Failed to generate AI copy for prompt {prompt_round.round_id}: {e}")
                    stats["errors"] += 1
                    continue

            # Find phrasesets waiting for votes that are older than backup delay
            # Create subquery to find phrasesets where AI has already voted
            ai_voted_subquery = (
                select(Vote.phraseset_id)
                .where(Vote.player_id == ai_player.player_id)
            )
            
            # Query for phrasesets that:
            # 1. Are in "open" or "closing" status (accepting votes)
            # 2. Were created older than the backup delay
            # 3. Don't have contributions from the AI player (avoid self-votes)
            # 4. Haven't been voted on by the AI player already (using subquery)
            # 5. Exclude phrasesets from test players
            phraseset_result = await self.db.execute(
                select(PhraseSet)
                .join(Round, Round.round_id == PhraseSet.prompt_round_id)
                .join(Player, Player.player_id == Round.player_id)
                .where(PhraseSet.status.in_(["open", "closing"]))
                .where(PhraseSet.created_at <= cutoff_time)
                .where(~Player.username.like('%test%'))  # Exclude test players
                .where(PhraseSet.phraseset_id.not_in(ai_voted_subquery))  # Exclude already voted
                .options(
                    selectinload(PhraseSet.prompt_round),
                    selectinload(PhraseSet.copy_round_1),
                    selectinload(PhraseSet.copy_round_2),
                )
                .order_by(PhraseSet.created_at.asc())  # Process oldest first
                .limit(self.settings.ai_backup_batch_size)  # Use configured batch size
            )
            
            waiting_phrasesets = list(phraseset_result.scalars().all())
            
            # Filter out phrasesets where AI was a contributor (in-memory check since we need loaded relationships)
            filtered_phrasesets = []
            for phraseset in waiting_phrasesets:
                # Skip if AI player was a contributor
                if ai_player.player_id not in {
                    phraseset.prompt_round.player_id,
                    phraseset.copy_round_1.player_id,
                    phraseset.copy_round_2.player_id,
                }:
                    filtered_phrasesets.append(phraseset)
            
            stats["phrasesets_checked"] = len(filtered_phrasesets)
            logger.info(f"Found {len(filtered_phrasesets)} phrasesets waiting for AI backup votes")
            
            # Process each waiting phraseset
            for phraseset in filtered_phrasesets:
                try:
                    # Generate AI vote choice
                    chosen_phrase = await self.generate_vote_choice(phraseset)
                    
                    # Create vote directly (simpler than going through vote service)
                    # Determine if vote is correct
                    correct = chosen_phrase == phraseset.original_phrase
                    payout = self.settings.vote_payout_correct if correct else 0
                    
                    # Create vote record
                    vote = Vote(
                        vote_id=uuid.uuid4(),
                        phraseset_id=phraseset.phraseset_id,
                        player_id=ai_player.player_id,
                        voted_phrase=chosen_phrase,
                        correct=correct,
                        payout=payout,
                    )
                    
                    self.db.add(vote)
                    await self.db.flush()
                    
                    # Give payout if correct (AI gets rewards like normal players)
                    if correct:
                        from backend.services.transaction_service import TransactionService
                        transaction_service = TransactionService(self.db)
                        await transaction_service.create_transaction(
                            ai_player.player_id,
                            payout,
                            "vote_payout",
                            vote.vote_id,
                        )
                    
                    # Update phraseset vote count
                    phraseset.vote_count += 1
                    
                    # Update vote timeline markers (copied from vote_service logic)
                    prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
                    if (prompt_round and phraseset.vote_count >= 1 and
                            prompt_round.phraseset_status not in {"closing", "finalized"}):
                        prompt_round.phraseset_status = "voting"

                    # Mark 3rd vote timestamp
                    if phraseset.vote_count == 3 and not phraseset.third_vote_at:
                        phraseset.third_vote_at = datetime.now(UTC)
                        logger.info(f"Phraseset {phraseset.phraseset_id} reached 3rd vote via AI, 10min window starts")

                    # Mark 5th vote timestamp and change status to closing
                    if phraseset.vote_count == 5 and not phraseset.fifth_vote_at:
                        phraseset.fifth_vote_at = datetime.now(UTC)
                        phraseset.status = "closing"
                        phraseset.closes_at = datetime.now(UTC) + timedelta(seconds=60)
                        if prompt_round:
                            prompt_round.phraseset_status = "closing"
                        logger.info(f"Phraseset {phraseset.phraseset_id} reached 5th vote via AI, 60sec closing window")
                    
                    # Check if phraseset should be finalized after AI vote
                    await self._check_and_finalize_phraseset(phraseset)
                    
                    stats["votes_generated"] += 1
                    logger.info(
                        f"AI generated vote '{chosen_phrase}' for phraseset {phraseset.phraseset_id} "
                        f"({'CORRECT' if correct else 'INCORRECT'}, payout: ${payout})"
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
