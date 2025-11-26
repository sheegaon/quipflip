"""
AI Service for automated quip phrase, impostor phrase, and vote generation.

This service provides AI-generated hints, backup copies and votes when human players
are unavailable, supporting multiple AI providers (OpenAI, Gemini)
with configurable fallback behavior and comprehensive metrics tracking.
"""

import logging
import asyncio
import random
from uuid import UUID

from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.player_base import PlayerBase
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.ai_phrase_cache import QFAIPhraseCache
from backend.models.qf.ai_quip_cache import QFAIQuipCache, QFAIQuipPhrase, QFAIQuipPhraseUsage
from backend.services.ai.metrics_service import AIMetricsService, MetricsTracker
from backend.utils.model_registry import GameType, AIPlayerType
from .prompt_builder import build_impostor_prompt
from backend.utils.passwords import hash_password
from backend.services.username_service import UsernameService

logger = logging.getLogger(__name__)


AI_PLAYER_EMAIL_DOMAIN = "@quipflip.internal"
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
        self._prompt_completions_cache = None  # Lazy-loaded CSV cache for quip responses
        self._impostor_completions_cache = None  # Lazy-loaded CSV cache for impostor phrases

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
        # Check if configured provider is available
        if self.settings.ai_provider == "openai" and self.settings.openai_api_key:
            logger.debug("Using OpenAI as AI provider")
            return "openai"
        elif self.settings.ai_provider == "gemini" and self.settings.gemini_api_key:
            logger.debug("Using Gemini as AI provider")
            return "gemini"
        elif self.settings.ai_provider == "none":
            logger.error("No AI provider configured")
            raise AIServiceError("AI provider set to 'none' - cannot proceed")

        # Fallback logic
        if self.settings.openai_api_key:
            logger.warning(f"Configured provider '{self.settings.ai_provider}' not available, falling back to OpenAI")
            return "openai"
        elif self.settings.gemini_api_key:
            logger.warning(f"Configured provider '{self.settings.ai_provider}' not available, falling back to Gemini")
            return "gemini"

        # No provider available
        logger.error("No AI provider API keys found (OPENAI_API_KEY or GEMINI_API_KEY)")
        raise AIServiceError("No AI provider configured - set OPENAI_API_KEY or GEMINI_API_KEY")

    async def _prompt_ai(self, prompt_text: str) -> str:
        """Send a prompt to the AI provider and return the response"""
        logger.info(f"Sending {prompt_text=} to AI provider {self.provider} {self.ai_model}")
        start_time = datetime.now(UTC)
        if self.provider == "openai":
            from backend.services.ai.openai_api import generate_response
        elif self.provider == "gemini":
            from backend.services.ai.gemini_api import generate_response
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")

        response = await generate_response(
            prompt_text,
            model=self.ai_model,
            timeout=self.settings.ai_timeout_seconds,
        )

        elapsed = (datetime.now(UTC) - start_time).total_seconds()
        logger.info(f"AI provider ({self.provider}) responded {response} in {elapsed:.2f}s")

        if not response or not response.strip():
            raise AICopyError("AI provider returned empty response")

        return response

    async def get_or_create_ai_player(self, ai_player_type: AIPlayerType, excluded: list | None = None) -> PlayerBase:
        """
        Get or create an AI player account for the specified game type.

        Args:
            ai_player_type: The type of AI player to create
            excluded: A list of AI player IDs to exclude

        Returns:
            The AI player instance

        Raises:
            AIServiceError: If AI player cannot be created or is in invalid state

        Note:
            Transaction management is handled by the caller (run_backup_cycle).
            This method should NOT commit or refresh the session.
        """
        # Instantiate the correct player service and model based on game type
        if (ai_player_type in
                [AIPlayerType.QF_QUIP, AIPlayerType.QF_IMPOSTOR, AIPlayerType.QF_VOTER, AIPlayerType.QF_PARTY]):
            from backend.models.qf.player import QFPlayer
            from backend.services.qf.player_service import QFPlayerService as PlayerService
            player_model = QFPlayer
            game_type = GameType.QF
        elif ai_player_type in [AIPlayerType.IR_PLAYER]:
            from backend.models.ir.player import IRPlayer
            from backend.services.ir.player_service import IRPlayerService as PlayerService
            player_model = IRPlayer
            game_type = GameType.IR
        else:
            raise ValueError(f"Unsupported {ai_player_type=}")

        email_patterns = {
            AIPlayerType.QF_QUIP: f"ai_quip_%{AI_PLAYER_EMAIL_DOMAIN}",
            AIPlayerType.QF_IMPOSTOR: f"ai_impostor_%{AI_PLAYER_EMAIL_DOMAIN}",
            AIPlayerType.QF_VOTER: f"ai_voter_%{AI_PLAYER_EMAIL_DOMAIN}",
            AIPlayerType.QF_PARTY: f"ai_party_%{AI_PLAYER_EMAIL_DOMAIN}",
            AIPlayerType.IR_PLAYER: IR_AI_PLAYER_EMAIL,
        }
        target_email = email_patterns.get(ai_player_type)
        if target_email is None:
            raise ValueError(f"Unsupported {ai_player_type=}")

        try:
            # Get all AI players using the correct model and type
            result = await self.db.execute(
                select(player_model)
                .where(player_model.email.like(target_email))
            )
            ai_players = set(result.scalars().all())
            if excluded:
                ai_players = {p for p in ai_players if p.player_id not in excluded}

            if game_type == GameType.QF:
                ai_players = {p for p in ai_players if p.wallet > 100}  # Ensure sufficient funds for QF AI players

            if not ai_players:
                # Create AI player using the correct service
                player_service = PlayerService(self.db)
                
                # Generate unique username
                username_service = UsernameService(self.db, game_type=game_type)
                username, canonical = await username_service.generate_unique_username()

                import uuid
                target_email = target_email.replace('%', uuid.uuid4().hex[:4])
                ai_player = await player_service.create_player(
                    username=username,
                    email=target_email,
                    password_hash=hash_password("not-used-for-ai-player"),
                )
                logger.info(f"Created {game_type.value} AI player account: {username}")
            else:
                ai_player = random.choice(list(ai_players))
                # Validate AI player is in good state (QF-specific validations)
                if game_type == GameType.QF:
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

    def _load_prompt_completions(self) -> dict[str, list[str]]:
        """
        Lazy-load pre-cached prompt completions from CSV file.

        Returns:
            Dictionary mapping normalized prompt text to list of completion phrases
        """
        if self._prompt_completions_cache is not None:
            return self._prompt_completions_cache

        import csv
        from pathlib import Path

        self._prompt_completions_cache = {}
        csv_path = Path(__file__).parent.parent.parent / "data" / "prompt_completions.csv"

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    prompt = row.get('prompt', '').strip().lower()
                    if not prompt:
                        continue

                    # Collect all phrase columns (phrase_1 through phrase_10)
                    phrases = []
                    for i in range(1, 11):
                        phrase_key = f'phrase_{i}'
                        if phrase_key in row and row[phrase_key]:
                            phrases.append(row[phrase_key].strip())

                    if phrases:
                        self._prompt_completions_cache[prompt] = phrases

        except FileNotFoundError:
            logger.warning(f"Prompt completions CSV not found at {csv_path}")
        except Exception as e:
            logger.error(f"Failed to load prompt completions CSV: {e}")

        return self._prompt_completions_cache

    async def _get_unused_csv_phrases(self, normalized_prompt: str) -> list[str]:
        """
        Get unused phrases from CSV cache for the given prompt.

        Args:
            normalized_prompt: The normalized prompt text (lowercase, stripped)

        Returns:
            List of phrases from CSV that haven't been used yet
        """
        csv_cache = self._load_prompt_completions()

        # Check if prompt exists in CSV
        if normalized_prompt not in csv_cache:
            return []

        available_phrases = csv_cache[normalized_prompt]

        # Query for phrases already used (in QFAIQuipPhrase where phrase_text matches)
        result = await self.db.execute(
            select(QFAIQuipPhrase.phrase_text)
            .join(QFAIQuipCache, QFAIQuipCache.cache_id == QFAIQuipPhrase.cache_id)
            .where(QFAIQuipCache.prompt_text == normalized_prompt)
        )
        used_phrases = {phrase.lower() for phrase in result.scalars().all()}

        # Filter out used phrases
        unused = [p for p in available_phrases if p.lower() not in used_phrases]

        logger.debug(
            f"Found {len(unused)} unused phrases from CSV for prompt '{normalized_prompt}' "
            f"({len(available_phrases)} total, {len(used_phrases)} used)"
        )

        return unused

    @staticmethod
    def _normalize_phrase_for_lookup(phrase: str) -> str:
        """
        Normalize a phrase for cache lookup by removing stop words.

        Removes articles, possessives, and demonstratives that don't affect
        core meaning, allowing "a birthday cake" to match "birthday cake".

        Args:
            phrase: The phrase to normalize

        Returns:
            Normalized phrase with stop words removed
        """
        # Words to remove (articles, possessives, demonstratives)
        stop_words = {
            'a', 'an', 'the', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'this', 'that', 'these', 'those'
        }

        # Convert to lowercase and split into words
        words = phrase.lower().split()

        # Filter out stop words
        filtered_words = [w for w in words if w not in stop_words]

        # Rejoin with spaces
        normalized = ' '.join(filtered_words)

        # If everything was filtered out, return original (lowercase)
        if not normalized:
            return phrase.lower()

        return normalized

    def _load_impostor_completions(self) -> dict[str, list[str]]:
        """
        Lazy-load pre-cached impostor phrases from CSV file.

        Creates bidirectional mapping where ANY phrase in a row can serve as the original,
        and all other phrases in that row are valid impostors.

        Returns:
            Dictionary where each phrase maps to the full equivalence set (all 6 phrases)
        """
        if self._impostor_completions_cache is not None:
            return self._impostor_completions_cache

        import csv
        from pathlib import Path

        self._impostor_completions_cache = {}
        csv_path = Path(__file__).parent.parent.parent / "data" / "fakes.csv"
        equivalence_sets_count = 0

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    original = row.get('original_phrase', '').strip()
                    if not original:
                        continue

                    # Collect all phrases in this equivalence set (original + 5 copies)
                    all_phrases = [original]
                    for i in range(1, 6):
                        phrase_key = f'copy_phrase{i}'
                        if phrase_key in row and row[phrase_key]:
                            all_phrases.append(row[phrase_key].strip())

                    # Create bidirectional mapping: each phrase maps to the FULL set
                    if len(all_phrases) > 1:
                        equivalence_sets_count += 1
                        for phrase in all_phrases:
                            # Normalize for lookup (remove stop words)
                            normalized_phrase = self._normalize_phrase_for_lookup(phrase)
                            # Each phrase maps to all phrases in the set (including itself)
                            self._impostor_completions_cache[normalized_phrase] = all_phrases

        except FileNotFoundError:
            logger.warning(f"Impostor phrases CSV not found at {csv_path}")
        except Exception as e:
            logger.error(f"Failed to load impostor phrases CSV: {e}")

        return self._impostor_completions_cache

    async def _get_unused_csv_impostor_phrases(self, original_phrase: str) -> list[str]:
        """
        Get unused impostor phrases from CSV cache for the given original phrase.

        With bidirectional mapping, any phrase in a row can be the "original" and
        the other phrases in that row are valid impostors.

        Args:
            original_phrase: The original phrase to find impostors for

        Returns:
            List of impostor phrases from CSV that haven't been used yet
        """
        csv_cache = self._load_impostor_completions()

        # Normalize for lookup (removes stop words like "a", "the", "my", etc.)
        normalized_original = self._normalize_phrase_for_lookup(original_phrase)

        # Check if original phrase exists in CSV equivalence sets
        if normalized_original not in csv_cache:
            return []

        # Get full equivalence set (all phrases that mean the same thing)
        equivalence_set = csv_cache[normalized_original]

        # Query for phrases already used in ANY cache for ANY phrase in this equivalence set
        # We need to check all phrases in the set since they're semantically equivalent
        result = await self.db.execute(
            select(QFAIPhraseCache.validated_phrases)
            .join(Round, Round.round_id == QFAIPhraseCache.prompt_round_id)
            .where(func.lower(Round.submitted_phrase).in_([p.lower() for p in equivalence_set]))
        )

        # Flatten all used phrases from all caches
        used_phrases = set()
        for cache_phrases in result.scalars().all():
            if cache_phrases:
                used_phrases.update(p.lower() for p in cache_phrases)

        # Filter out: 1) phrases that normalize to same as submitted, 2) already used phrases
        # We normalize each candidate to handle variations like "a cake" vs "cake"
        unused = [
            p for p in equivalence_set
            if self._normalize_phrase_for_lookup(p) != normalized_original
            and p.lower() not in used_phrases
        ]

        return unused

    async def _get_existing_impostor_phrase(self, prompt_round_id: UUID | None) -> str | None:
        """Fetch an existing submitted impostor phrase for the quip round, if any."""
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

    async def generate_quip_response(self, prompt_text: str, prompt_round_id: UUID) -> str:
        """
        Generate or reuse a creative quip for a quip round, with caching.

        Args:
            prompt_text: The prompt to respond to
            prompt_round_id: The quip round ID consuming the cached phrase

        Returns:
            Generated phrase

        Raises:
            AICopyError: If generation fails
        """
        if not prompt_round_id:
            raise AICopyError("prompt_round_id is required to track cached quip usage")

        try:
            cache = await self._get_or_create_quip_cache(prompt_text)
            phrase = await self._select_cached_quip_phrase(cache)

            usage = QFAIQuipPhraseUsage(phrase_id=phrase.phrase_id, prompt_round_id=prompt_round_id)
            self.db.add(usage)
            await self.db.flush()

            logger.info(f"AI ({self.provider}) provided cached quip phrase {prompt_round_id=} ({phrase.phrase_id=})")
            return phrase.phrase_text

        except Exception as e:
            logger.error(f"Failed to generate prompt phrase: {e}")
            raise AICopyError(f"Prompt generation failed: {e!s}") from e

    async def _get_or_create_quip_cache(self, prompt_text: str) -> QFAIQuipCache:
        """Fetch or build a cache of validated quip responses for a prompt."""
        from backend.services.ai.prompt_builder import build_quip_prompt
        from backend.utils import lock_client

        normalized_prompt = prompt_text.strip()
        if not normalized_prompt:
            raise AICopyError("Prompt text is required for quip generation")

        lock_name = f"ai_quip_generation:{normalized_prompt.lower()}"

        try:
            # AI generation can take up to 60s especially under load
            with lock_client.lock(lock_name, timeout=120):
                cache_result = await self.db.execute(
                    select(QFAIQuipCache)
                    .options(selectinload(QFAIQuipCache.phrases))
                    .where(QFAIQuipCache.prompt_text == normalized_prompt)
                    .order_by(QFAIQuipCache.created_at.desc())
                    .limit(1)
                )
                existing_cache = cache_result.scalars().first()
                if existing_cache and existing_cache.phrases:
                    return existing_cache

                # Try CSV cache first before calling AI API
                unused_csv_phrases = await self._get_unused_csv_phrases(normalized_prompt.lower())
                if unused_csv_phrases:
                    logger.info(f"Found {len(unused_csv_phrases)} unused CSV phrases for '{normalized_prompt}'")

                    # Validate CSV phrases
                    validated_phrases = []
                    errors = []
                    for test_phrase in unused_csv_phrases:
                        test_phrase = test_phrase.strip()
                        if not test_phrase:
                            continue

                        # Basic length checks
                        if len(test_phrase) < 4:
                            error_message = "Phrase too short"
                            errors.append((test_phrase, error_message))
                            logger.debug(f"CSV phrase invalid '{test_phrase}': {error_message}")
                            continue
                        if len(test_phrase) > 100:
                            error_message = "Phrase too long"
                            errors.append((test_phrase, error_message))
                            logger.debug(f"CSV phrase invalid '{test_phrase}': {error_message}")
                            continue

                        # Validate with phrase validator
                        is_valid, error_message = await self.phrase_validator.validate_prompt_phrase(
                            test_phrase, normalized_prompt
                        )
                        if is_valid:
                            validated_phrases.append(test_phrase)
                        else:
                            errors.append((test_phrase, error_message))
                            logger.debug(f"CSV phrase invalid '{test_phrase}': {error_message}")

                    # If we have at least one valid CSV phrase, create cache
                    if validated_phrases:
                        cache = QFAIQuipCache(
                            prompt_text=normalized_prompt,
                            generation_provider="csv_cache",
                            generation_model="pre_generated",
                        )
                        self.db.add(cache)
                        await self.db.flush()

                        for phrase in validated_phrases:
                            self.db.add(QFAIQuipPhrase(cache_id=cache.cache_id, phrase_text=phrase))

                        await self.db.flush()
                        logger.info(
                            f"Created cache from CSV with {len(validated_phrases)} validated phrases for '{normalized_prompt}' "
                            f"({len(errors)} invalid)"
                        )
                        return cache

                    logger.info(
                        f"No valid CSV phrases found for '{normalized_prompt}' ({len(errors)} failed validation), "
                        "falling back to AI generation"
                    )

                # Fall back to AI generation if no CSV phrases available
                ai_prompt = build_quip_prompt(normalized_prompt)
                common_words = await self.get_common_words()
                if not isinstance(common_words, (list, tuple)):
                    logger.warning(f"common_words is not iterable: {type(common_words)}, using empty list")
                    common_words = []

                common_words = [word for word in common_words if len(word) > 3]
                ai_prompt = ai_prompt.format(common_words=", ".join(common_words))

                test_phrases = await self._prompt_ai(ai_prompt)
                test_phrases = test_phrases.split(";")

                validated_phrases = []
                errors = []
                for test_phrase in test_phrases:
                    test_phrase = test_phrase.strip()
                    if not test_phrase:
                        continue

                    if len(test_phrase) < 4:
                        error_message = "Phrase too short"
                        errors.append((test_phrase, error_message))
                        logger.info(f"AI generated invalid prompt phrase '{test_phrase}': {error_message}")
                        continue
                    if len(test_phrase) > 100:
                        error_message = "Phrase too long"
                        errors.append((test_phrase, error_message))
                        logger.info(f"AI generated invalid prompt phrase '{test_phrase}': {error_message}")
                        continue

                    is_valid, error_message = await self.phrase_validator.validate_prompt_phrase(
                        test_phrase, normalized_prompt
                    )
                    if is_valid:
                        validated_phrases.append(test_phrase)
                    else:
                        errors.append((test_phrase, error_message))
                        logger.info(f"AI generated invalid prompt phrase '{test_phrase}': {error_message}")

                if not validated_phrases:
                    raise AICopyError(f"AI generated no valid phrases for prompt '{normalized_prompt}': {errors=}")

                cache = QFAIQuipCache(
                    prompt_text=normalized_prompt,
                    generation_provider=self.provider,
                    generation_model=self.ai_model,
                )
                self.db.add(cache)
                await self.db.flush()

                for phrase in validated_phrases:
                    self.db.add(QFAIQuipPhrase(cache_id=cache.cache_id, phrase_text=phrase))

                await self.db.flush()
                logger.info(f"AI ({self.provider}) generated and cached {len(validated_phrases)} "
                            f"quip phrase(s) for prompt '{normalized_prompt}'")
                return cache

        except asyncio.CancelledError:
            # Server shutdown or task cancellation - exit immediately
            logger.info(f"AI quip generation cancelled for prompt '{normalized_prompt}'")
            raise
        except TimeoutError:
            logger.warning(f"Could not acquire lock for AI quip generation of prompt '{normalized_prompt}', "
                           f"another process may be handling it")
            fallback = await self.db.execute(
                select(QFAIQuipCache)
                .options(selectinload(QFAIQuipCache.phrases))
                .where(QFAIQuipCache.prompt_text == normalized_prompt)
                .order_by(QFAIQuipCache.created_at.desc())
                .limit(1)
            )
            cache = fallback.scalars().first()
            if cache:
                return cache
            raise AICopyError("Quip cache unavailable after lock timeout")

    async def _select_cached_quip_phrase(self, cache: QFAIQuipCache) -> QFAIQuipPhrase:
        """Pick the least-used cached quip phrase, allowing reuse when needed."""
        usage_counts = (
            select(
                QFAIQuipPhraseUsage.phrase_id,
                func.count(QFAIQuipPhraseUsage.usage_id).label("use_count"),
            )
            .group_by(QFAIQuipPhraseUsage.phrase_id)
            .subquery()
        )

        phrase_result = await self.db.execute(
            select(QFAIQuipPhrase, func.coalesce(usage_counts.c.use_count, 0))
            .outerjoin(usage_counts, QFAIQuipPhrase.phrase_id == usage_counts.c.phrase_id)
            .where(QFAIQuipPhrase.cache_id == cache.cache_id)
            .order_by(func.coalesce(usage_counts.c.use_count, 0).asc(), QFAIQuipPhrase.created_at.asc())
            .limit(1)
        )
        selection = phrase_result.first()
        if not selection:
            raise AICopyError("No cached quip phrases available")

        phrase, use_count = selection
        logger.debug(f"Selected cached quip {phrase.phrase_id=} with {use_count} prior use(s) for {cache.cache_id=}")
        return phrase

    async def generate_and_cache_impostor_phrases(self, prompt_round: Round) -> QFAIPhraseCache:
        """Generate and cache multiple validated copy phrases for a prompt round."""
        import uuid as uuid_module
        from backend.utils import lock_client

        async def _generate_cache() -> QFAIPhraseCache:
            result = await self.db.execute(
                select(QFAIPhraseCache).where(QFAIPhraseCache.prompt_round_id == prompt_round.round_id)
            )
            existing_cache = result.scalar_one_or_none()
            if existing_cache:
                logger.debug(f"Using existing phrase cache for prompt_round {prompt_round.round_id}")
                return existing_cache

            original_phrase = prompt_round.submitted_phrase
            other_copy_phrase = await self._get_existing_impostor_phrase(prompt_round.round_id)

            unused_csv_phrases = await self._get_unused_csv_impostor_phrases(original_phrase)
            if unused_csv_phrases:
                logger.info(f"Found {len(unused_csv_phrases)} unused CSV impostor phrases for '{original_phrase}'")
                validated_phrases: list[str] = []
                errors: list[tuple[str, str]] = []
                for test_phrase in unused_csv_phrases:
                    test_phrase = test_phrase.strip()
                    if not test_phrase:
                        continue
                    is_valid, error_message = await self.phrase_validator.validate_copy(
                        test_phrase,
                        original_phrase,
                        other_copy_phrase,
                        prompt_round.prompt_text,
                    )
                    if is_valid:
                        validated_phrases.append(test_phrase)
                    else:
                        errors.append((test_phrase, error_message))
                        logger.debug(f"CSV impostor phrase invalid '{test_phrase}': {error_message}")

                if len(validated_phrases) >= 3:
                    csv_cache_id = uuid_module.uuid4()
                    cache = QFAIPhraseCache(
                        cache_id=csv_cache_id,
                        prompt_round_id=prompt_round.round_id,
                        original_phrase=original_phrase,
                        prompt_text=prompt_round.prompt_text,
                        validated_phrases=validated_phrases[:5],
                        generation_provider="csv_cache",
                        generation_model="pre_generated",
                    )
                    self.db.add(cache)
                    await self.db.flush()
                    logger.info(
                        f"Created impostor cache from CSV with {len(validated_phrases)} validated phrases for '{original_phrase}' "
                        f"({len(errors)} invalid)"
                    )
                    return cache

                logger.info(
                    f"No valid CSV impostor phrases found for '{original_phrase}' ({len(errors)} failed validation), "
                    "falling back to AI generation"
                )

            max_attempts = 2
            attempt = 0
            cache_id = uuid_module.uuid4()
            validated_phrases: list[str] = []
            common_words = await self.get_common_words()
            common_words = [word for word in common_words if len(word) > 3]

            while attempt < max_attempts:
                attempt += 1
                prompt_text = build_impostor_prompt(original_phrase, other_copy_phrase)
                prompt_text = prompt_text.format(common_words=", ".join(common_words))

                response = await self._prompt_ai(prompt_text)

                raw_phrases = [p.strip().upper() for p in response.split(";") if p.strip()]
                unique_phrases: list[str] = []
                for phrase in raw_phrases:
                    if phrase not in unique_phrases:
                        unique_phrases.append(phrase)

                async with MetricsTracker(
                    self.metrics_service,
                    operation_type="copy_generation",
                    provider=self.provider,
                    model=self.ai_model,
                    cache_id=cache_id,
                ) as tracker:
                    validated_phrases = []
                    errors = []
                    for phrase in unique_phrases:
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
                            logger.debug(f"AI impostor phrase invalid '{phrase}': {error_message}")

                    success = len(validated_phrases) >= 3
                    tracker.set_result(
                        f"{len(validated_phrases)} phrases" if success else "",
                        success=success,
                        response_length=sum(len(p) for p in validated_phrases) if success else 0,
                        validation_passed=success,
                    )

                if success:
                    break

                if attempt == 1 and len(validated_phrases) >= 1 and other_copy_phrase is None:
                    other_copy_phrase = validated_phrases[0]
                    logger.info(
                        f"Retrying AI generation with other_copy_phrase='{other_copy_phrase}' "
                        f"after first attempt yielded {len(validated_phrases)} valid phrases"
                    )
                    continue

                raise AICopyError(
                    f"AI generated only {len(validated_phrases)} valid phrases (need 3+) for "
                    f"{original_phrase=} {other_copy_phrase=} after {attempt} attempt(s): {errors=}"
                )

            cache = QFAIPhraseCache(
                cache_id=cache_id,
                prompt_round_id=prompt_round.round_id,
                original_phrase=original_phrase,
                prompt_text=prompt_round.prompt_text,
                validated_phrases=validated_phrases[:5],
                generation_provider=self.provider,
                generation_model=self.ai_model,
            )
            self.db.add(cache)
            await self.db.flush()
            logger.info(
                f"AI ({self.provider}) generated and cached {len(validated_phrases)} valid phrases "
                f"for prompt_round {prompt_round.round_id}"
            )
            return cache

        lock_name = f"ai_phrase_generation:{prompt_round.round_id}"
        lock_retry_attempts = 3
        lock_retry_delay = 0.25

        for lock_attempt in range(lock_retry_attempts):
            try:
                # AI generation can take up to 60s especially under load
                with lock_client.lock(lock_name, timeout=120):
                    return await _generate_cache()
            except asyncio.CancelledError:
                # Server shutdown or task cancellation - exit immediately
                logger.info(f"AI phrase generation cancelled for prompt round {prompt_round.round_id}")
                raise
            except TimeoutError:
                logger.warning(
                    f"Could not acquire lock for AI phrase generation of prompt round {prompt_round.round_id} "
                    f"(attempt {lock_attempt + 1}/{lock_retry_attempts})"
                )
                result = await self.db.execute(
                    select(QFAIPhraseCache).where(QFAIPhraseCache.prompt_round_id == prompt_round.round_id)
                )
                existing_cache = result.scalar_one_or_none()
                if existing_cache:
                    logger.debug(f"Using cache created by another process for prompt_round {prompt_round.round_id}")
                    return existing_cache

                if lock_attempt + 1 == lock_retry_attempts:
                    raise AICopyError("Could not acquire lock for AI phrase generation and no cache exists")

                await asyncio.sleep(lock_retry_delay * (lock_attempt + 1))
            except Exception as exc:
                logger.error(
                    f"Error acquiring lock for AI phrase generation of prompt round {prompt_round.round_id}: {exc}",
                    exc_info=True,
                )
                raise AICopyError(f"AI phrase generation failed: {exc!s}") from exc


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

                other_copy_phrase = await self._get_existing_impostor_phrase(prompt_round.round_id)
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
        except asyncio.CancelledError:
            # Server shutdown or task cancellation - exit immediately
            logger.info(f"AI phrase revalidation cancelled for {prompt_round.round_id=}")
            raise
        except TimeoutError:
            logger.warning(f"Could not acquire lock for AI phrase revalidation of {prompt_round.round_id=}")
            return None

        return await self.generate_and_cache_impostor_phrases(prompt_round)

    async def get_impostor_phrase(self, prompt_round: Round) -> str:
        """
        Generate an impostor phrase using cached validated phrases.

        This method now uses the phrase cache to avoid redundant AI API calls.
        It selects a random phrase from the cache and removes it from the list.

        Args:
            prompt_round: The prompt round object to get context and check existing copies

        Returns:
            Generated and validated impostor phrase

        Raises:
            AICopyError: If generation or validation fails
        """
        # Get or generate phrase cache
        cache = await self.generate_and_cache_impostor_phrases(prompt_round)

        # Select random phrase from cache
        if not cache.validated_phrases or len(cache.validated_phrases) == 0:
            # Cache is empty, regenerate
            logger.warning(f"Phrase cache for {prompt_round.round_id=} is empty, regenerating...")
            # Delete empty cache and regenerate
            await self.db.delete(cache)
            await self.db.flush()
            cache = await self.generate_and_cache_impostor_phrases(prompt_round)

        # Select random phrase
        selected_phrase = random.choice(cache.validated_phrases)

        # Remove selected phrase from cache (so next backup copy gets a different one)
        cache.validated_phrases = [p for p in cache.validated_phrases if p != selected_phrase]
        cache.used_for_backup_copy = True
        await self.db.flush()

        logger.info(
            f"AI ({self.provider}) {selected_phrase=} ({len(cache.validated_phrases)} phrases remaining in cache)")
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
        cache = await self.generate_and_cache_impostor_phrases(prompt_round)

        # Mark cache as used for hints
        cache.used_for_hints = True
        await self.db.flush()

        # Return first 'count' phrases (don't remove from cache - all players get same hints)
        hints = cache.validated_phrases[:count]

        if len(hints) == 0:
            raise AICopyError("Phrase cache is empty, cannot provide hints")

        logger.info(f"AI ({self.provider}) provided {len(hints)} cached hints for prompt_round {prompt_round.round_id}")

        return hints

    async def generate_vote_choice(self, phraseset: Phraseset, seed: int) -> str:
        """
        Generate a vote choice using the configured AI provider with metrics tracking.

        Args:
            phraseset: The phraseset to vote on (must have prompt and 3 phrases loaded)
            seed: Random seed for reproducibility

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
                seed=seed,
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

    async def run_backup_cycle(self) -> None:
        """
        Run a backup cycle to provide AI copies for waiting prompts and AI votes for waiting phrasesets.

        This method delegates to QFBackupOrchestrator for the actual backup logic.

        Note:
            This is the main entry point for the QuipFlip AI backup system.
        """
        from backend.services.ai.qf_backup_orchestrator import QFBackupOrchestrator

        orchestrator = QFBackupOrchestrator(self)
        await orchestrator.run_backup_cycle()

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
            response_text = await self._prompt_ai(prompt)

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
            raise AICopyError(f"Backronym generation failed: {e!s}") from e

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
            response_text = await self._prompt_ai(prompt)

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
            raise AIVoteError(f"Backronym vote generation failed: {e!s}") from e

    async def run_ir_backup_cycle(self) -> None:
        """
        Run backup cycle for Initial Reaction game.

        This method delegates to IRBackupOrchestrator for the actual backup logic.

        Note:
            This is the main entry point for the Initial Reaction AI backup system.
        """
        from backend.services.ai.ir_backup_orchestrator import IRBackupOrchestrator

        orchestrator = IRBackupOrchestrator(self)
        await orchestrator.run_backup_cycle()
