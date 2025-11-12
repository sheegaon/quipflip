"""Comprehensive integration tests for AI service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
import uuid

from sqlalchemy import select

from backend.services.ai.ai_service import AIService, AICopyError, AIVoteError, AIServiceError
from backend.services.ai.metrics_service import AIMetricsService
from backend.services.phrase_validator import PhraseValidator
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.ai_metric import AIMetric
from backend.models.ai_phrase_cache import AIPhraseCache
from backend.models.hint import Hint
from backend.models.vote import Vote
from backend.config import get_settings


@pytest.fixture(autouse=True)
def mock_validator():
    """Mock phrase validator."""
    settings = get_settings()
    original_openai_api_key = settings.openai_api_key
    original_use_validator = settings.use_phrase_validator_api

    if not settings.openai_api_key:
        settings.openai_api_key = "sk-test"
    settings.use_phrase_validator_api = False

    with patch("backend.services.phrase_validator.get_phrase_validator") as mock_get_validator:
        validator = MagicMock(spec=PhraseValidator)
        validator.validate.return_value = (True, "")
        mock_get_validator.return_value = validator
        yield validator

    settings.openai_api_key = original_openai_api_key
    settings.use_phrase_validator_api = original_use_validator


@pytest.fixture
def ai_service(db_session):
    """Create AI service instance."""
    return AIService(db_session)


@pytest.fixture
def mock_prompt_round():
    """Create a mock prompt round for copy generation tests."""
    round_obj = MagicMock(spec=Round)
    round_obj.round_id = uuid.uuid4()
    round_obj.phrase = "happy birthday"
    round_obj.submitted_phrase = "happy birthday"
    round_obj.round_type = "prompt"
    round_obj.prompt_text = "What do you say to celebrate someone's birth?"
    return round_obj


@pytest.fixture
def mock_phraseset():
    """Create a mock phraseset for voting tests."""
    phraseset = MagicMock(spec=Phraseset)
    phraseset.phraseset_id = uuid.uuid4()

    # Mock the properties that generate_vote_choice uses
    phraseset.prompt_text = "What do you say to celebrate someone's birth?"
    phraseset.original_phrase = "happy birthday"
    phraseset.copy_phrase_1 = "joyful anniversary"
    phraseset.copy_phrase_2 = "merry celebration"

    # Also keep the old structure for compatibility
    phraseset.prompt_round = MagicMock()
    phraseset.prompt_round.phrase = "happy birthday"

    phraseset.copy_round_1 = MagicMock()
    phraseset.copy_round_1.phrase = "joyful anniversary"

    phraseset.copy_round_2 = MagicMock()
    phraseset.copy_round_2.phrase = "merry celebration"

    return phraseset


class TestAIServiceProviderSelection:
    """Test AI provider selection logic."""

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test', 'AI_PROVIDER': 'openai'})
    def test_select_openai_when_configured(self, db_session):
        """Should select OpenAI when configured and API key available."""
        with patch('backend.services.ai.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'openai'
            settings.openai_api_key = 'sk-test'
            settings.use_phrase_validator_api = False
            service = AIService(db_session)
            assert service.provider == "openai"

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key', 'AI_PROVIDER': 'gemini'}, clear=True)
    def test_select_gemini_when_configured(self, db_session, mock_validator):
        """Should select Gemini when configured and API key available."""
        with patch('backend.services.ai.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'gemini'
            settings.gemini_api_key = 'test-key'
            settings.use_phrase_validator_api = False
            service = AIService(db_session)
            assert service.provider == "gemini"

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'}, clear=True)
    def test_fallback_to_openai_when_gemini_unavailable(self, db_session):
        """Should fallback to OpenAI when Gemini configured but unavailable."""
        with patch('backend.services.ai.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'gemini'
            settings.openai_api_key = 'sk-test'
            settings.gemini_api_key = None
            settings.use_phrase_validator_api = False
            service = AIService(db_session)
            assert service.provider == "openai"

    @patch.dict('os.environ', {}, clear=True)
    def test_raise_error_when_no_provider_available(self, db_session):
        """Should raise error when no API keys available."""
        with patch('backend.services.ai.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'openai'
            settings.openai_api_key = None
            settings.gemini_api_key = None
            settings.use_phrase_validator_api = False
            with pytest.raises(AIServiceError, match="No AI provider configured"):
                AIService(db_session)


class TestAICopyGeneration:
    """Test AI copy phrase generation."""

    @pytest.mark.asyncio
    @patch('backend.services.ai.openai_api.generate_copy')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_copy_with_openai(
            self, mock_openai, db_session, mock_prompt_round
    ):
        """Should generate copy using OpenAI."""
        # Return 5 semicolon-delimited phrases as the AI service expects
        mock_openai.return_value = "joyful celebration; festive greeting; happy wishes; merry occasion; cheerful day"

        service = AIService(db_session)
        # Mock the phrase validator's validate_copy method to return success for all phrases
        with patch.object(service.phrase_validator, 'validate_copy', return_value=(True, "")):
            result = await service.generate_copy_phrase(
                original_phrase="happy birthday",
                prompt_round=mock_prompt_round,
            )

        # Result should be one of the generated phrases
        assert result in ["joyful celebration", "festive greeting", "happy wishes", "merry occasion", "cheerful day"]
        mock_openai.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.services.ai.gemini_api.generate_copy')
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}, clear=True)
    async def test_generate_copy_with_gemini(
            self, mock_gemini, db_session, mock_prompt_round, mock_validator
    ):
        """Should generate copy using Gemini."""
        # Return 5 semicolon-delimited phrases as the AI service expects
        mock_gemini.return_value = "merry festivity; joyful party; happy times; festive cheer; celebration day"
        # Mock validate_copy as an async function
        mock_validator.validate_copy = AsyncMock(return_value=(True, ""))

        with patch('backend.services.ai.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'gemini'
            settings.gemini_api_key = 'test-key'
            settings.ai_gemini_model = 'gemini-2.5-flash-lite'
            settings.ai_timeout_seconds = 30
            settings.use_phrase_validator_api = False

            service = AIService(db_session)
            result = await service.generate_copy_phrase(
                original_phrase="happy birthday",
                prompt_round=mock_prompt_round,
            )

            # Result should be one of the generated phrases
            assert result in ["merry festivity", "joyful party", "happy times", "festive cheer", "celebration day"]
            mock_gemini.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.services.ai.openai_api.generate_copy')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_copy_validation_failure(
            self, mock_openai, db_session, mock_prompt_round
    ):
        """Should raise error when generated phrase fails validation."""
        mock_openai.return_value = "invalid phrase!!!"

        service = AIService(db_session)

        # Mock the phrase validator's validate_copy to return validation failure
        with patch.object(service.phrase_validator, 'validate_copy', return_value=(False, "Invalid characters")):
            with pytest.raises(AICopyError, match="Invalid characters"):
                await service.generate_copy_phrase(
                    original_phrase="happy birthday",
                    prompt_round=mock_prompt_round,
                )

    @pytest.mark.asyncio
    @patch('backend.services.ai.openai_api.generate_copy')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_copy_api_failure(
            self, mock_openai, db_session, mock_prompt_round
    ):
        """Should handle API failures gracefully."""
        mock_openai.side_effect = Exception("API timeout")

        service = AIService(db_session)

        with pytest.raises(AICopyError, match="Failed to generate AI copy"):
            await service.generate_copy_phrase(
                original_phrase="happy birthday",
                prompt_round=mock_prompt_round,
            )


class TestAIVoting:
    """Test AI vote generation."""

    @pytest.mark.asyncio
    @patch('backend.services.ai.ai_service.random.shuffle')
    @patch('backend.services.ai.vote_helper.generate_vote_choice')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_vote_choice(
            self, mock_vote, mock_shuffle, db_session, mock_validator, mock_phraseset
    ):
        """Should generate vote choice using AI."""
        # Don't shuffle the phrases (keep order: original, copy1, copy2)
        mock_shuffle.return_value = None
        # AI chooses index 0 (original phrase)
        mock_vote.return_value = 0

        service = AIService(db_session)
        result = await service.generate_vote_choice(mock_phraseset)

        assert result == "happy birthday"
        mock_vote.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.services.ai.ai_service.random.shuffle')
    @patch('backend.services.ai.vote_helper.generate_vote_choice')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_vote_incorrect_choice(
            self, mock_vote, mock_shuffle, db_session, mock_validator, mock_phraseset
    ):
        """Should handle incorrect vote choices."""
        # Don't shuffle the phrases (keep order: original, copy1, copy2)
        mock_shuffle.return_value = None
        # AI chooses index 1 (copy phrase)
        mock_vote.return_value = 1

        service = AIService(db_session)
        result = await service.generate_vote_choice(mock_phraseset)

        assert result == "joyful anniversary"


class TestAIMetrics:
    """Test AI metrics tracking."""

    @pytest.mark.asyncio
    @patch('backend.services.ai.openai_api.generate_copy')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_metrics_recorded_on_success(
            self, mock_openai, db_session, mock_prompt_round
    ):
        """Should record metrics on successful operation."""
        # Return 5 semicolon-delimited phrases as the AI service expects
        mock_openai.return_value = "joyful celebration; festive greeting; happy wishes; merry occasion; cheerful day"

        service = AIService(db_session)
        # Mock the phrase validator's validate_copy method to return success
        with patch.object(service.phrase_validator, 'validate_copy', return_value=(True, "")):
            await service.generate_copy_phrase(
                original_phrase="happy birthday",
                prompt_round=mock_prompt_round,
            )

        # Metrics are flushed during generation, so query them from the database
        result = await db_session.execute(
            select(AIMetric).where(AIMetric.operation_type == "copy_generation")
        )
        ai_metrics = result.scalars().all()
        assert len(ai_metrics) == 1

        metric = ai_metrics[0]
        assert metric.operation_type == "copy_generation"
        assert metric.provider == "openai"
        assert metric.success is True
        assert metric.validation_passed is True

    @pytest.mark.asyncio
    @patch('backend.services.ai.openai_api.generate_copy')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_metrics_recorded_on_failure(
            self, mock_openai, db_session, mock_prompt_round
    ):
        """Should record metrics on failed operation."""
        mock_openai.return_value = "invalid!!!"

        service = AIService(db_session)

        # Mock the phrase validator's validate_copy to return validation failure
        with patch.object(service.phrase_validator, 'validate_copy', return_value=(False, "Invalid characters")):
            with pytest.raises(AICopyError):
                await service.generate_copy_phrase(
                    original_phrase="happy birthday",
                    prompt_round=mock_prompt_round,
                )

        # Check that failure metric was created
        metrics = db_session.new
        ai_metrics = [m for m in metrics if isinstance(m, AIMetric)]
        assert len(ai_metrics) == 1

        metric = ai_metrics[0]
        assert metric.success is False
        assert metric.validation_passed is False

    @pytest.mark.asyncio
    @patch('backend.services.ai.ai_service.random.shuffle')
    @patch('backend.services.ai.vote_helper.generate_vote_choice')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_vote_metrics_track_correctness(
            self, mock_vote, mock_shuffle, db_session, mock_validator, mock_phraseset
    ):
        """Should track whether AI vote was correct."""
        # Don't shuffle the phrases (keep order: original, copy1, copy2)
        mock_shuffle.return_value = None
        mock_vote.return_value = 0  # Correct choice

        service = AIService(db_session)
        await service.generate_vote_choice(mock_phraseset)

        metrics = db_session.new
        ai_metrics = [m for m in metrics if isinstance(m, AIMetric)]
        assert len(ai_metrics) == 1

        metric = ai_metrics[0]
        assert metric.operation_type == "vote_generation"
        assert metric.vote_correct is True


class TestAIHintGeneration:
    """Test AI hint generation and persistence."""

    @staticmethod
    async def _create_prompt_round(db_session) -> Round:
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="prompt",
            status="submitted",
            prompt_text="Describe a celebratory greeting.",
            submitted_phrase="ORIGINAL PHRASE",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        db_session.add(prompt_round)
        await db_session.commit()
        await db_session.refresh(prompt_round)
        return prompt_round

    @pytest.mark.asyncio
    @patch("backend.services.ai.openai_api.generate_copy")
    async def test_generate_copy_hints_returns_cached_phrases(
            self,
            mock_openai,
            db_session,
            mock_validator,
    ):
        """Should return hints from the phrase cache."""
        prompt_round = await self._create_prompt_round(db_session)
        # Mock returns 5 semicolon-delimited phrases, and we'll call it once
        mock_openai.return_value = "Warm glow; Festive cheer; Joyful toast; Happy vibes; Merry times"

        # Mock validator to validate all phrases successfully
        mock_validator.validate_copy = AsyncMock(return_value=(True, ""))

        service = AIService(db_session)
        hints = await service.get_hints_from_cache(prompt_round, count=3)

        # Should get 3 hints from the cache (not uppercased - that happens in the UI)
        assert len(hints) == 3
        # All hints should be from the generated phrases (in original case)
        possible_hints = {"Warm glow", "Festive cheer", "Joyful toast", "Happy vibes", "Merry times"}
        for hint in hints:
            assert hint in possible_hints

        # Verify the phrase cache was created and marked as used for hints
        result = await db_session.execute(
            select(AIPhraseCache).where(AIPhraseCache.prompt_round_id == prompt_round.round_id)
        )
        cache = result.scalar_one()
        assert cache.used_for_hints is True
        assert cache.generation_provider == service.provider

        # Should have 1 metric for the cache generation
        result = await db_session.execute(
            select(AIMetric).where(AIMetric.operation_type == "copy_generation")
        )
        metrics = result.scalars().all()
        assert len(metrics) == 1
        assert metrics[0].success is True

    @pytest.mark.asyncio
    @patch("backend.services.ai.openai_api.generate_copy")
    async def test_get_hints_reuses_cache(
            self,
            mock_openai,
            db_session,
            mock_validator,
    ):
        """Should reuse existing phrase cache when called multiple times."""
        prompt_round = await self._create_prompt_round(db_session)
        # Return 5 unique phrases - the cache will store them all and hints will use 3
        mock_openai.return_value = "Unique one; Unique two; Unique three; Unique four; Unique five"

        # Mock validator to validate all phrases successfully
        mock_validator.validate_copy = AsyncMock(return_value=(True, ""))

        service = AIService(db_session)

        # First call creates the cache
        hints1 = await service.get_hints_from_cache(prompt_round, count=3)
        assert len(hints1) == 3
        assert len(set(hints1)) == 3
        assert mock_openai.await_count == 1

        # Second call reuses the cache (doesn't call generate_copy again)
        hints2 = await service.get_hints_from_cache(prompt_round, count=3)
        assert len(hints2) == 3
        assert hints1 == hints2  # Same hints returned
        assert mock_openai.await_count == 1  # Still only 1 call

        # Verify only one cache entry exists
        result = await db_session.execute(
            select(AIPhraseCache).where(AIPhraseCache.prompt_round_id == prompt_round.round_id)
        )
        caches = result.scalars().all()
        assert len(caches) == 1

        # Should have 1 metric for the cache generation (not 2)
        result = await db_session.execute(
            select(AIMetric).where(AIMetric.operation_type == "copy_generation")
        )
        metrics = result.scalars().all()
        assert len(metrics) == 1
        assert metrics[0].success is True


class TestAIMetricsService:
    """Test AI metrics service analytics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, db_session):
        """Should calculate statistics correctly."""
        metrics_service = AIMetricsService(db_session)

        # Add some test metrics
        metrics = [
            AIMetric(
                operation_type="copy_generation",
                provider="openai",
                model="gpt-5-nano",
                success=True,
                latency_ms=500,
                estimated_cost_usd=0.0001,
            ),
            AIMetric(
                operation_type="copy_generation",
                provider="openai",
                model="gpt-5-nano",
                success=False,
                error_message="Validation failed",
            ),
            AIMetric(
                operation_type="vote_generation",
                provider="gemini",
                model="gemini-2.5-flash-lite",
                success=True,
                latency_ms=300,
                estimated_cost_usd=0.00005,
                vote_correct=True,
            ),
        ]

        for metric in metrics:
            db_session.add(metric)
        await db_session.commit()

        # Get stats
        stats = await metrics_service.get_stats()

        assert stats.total_operations == 3
        assert stats.successful_operations == 2
        assert stats.failed_operations == 1
        assert stats.success_rate == pytest.approx(66.67, rel=0.1)
        assert stats.total_cost_usd > 0
        assert stats.operations_by_provider["openai"] == 2
        assert stats.operations_by_provider["gemini"] == 1

    @pytest.mark.asyncio
    async def test_get_vote_accuracy(self, db_session):
        """Should calculate vote accuracy correctly."""
        metrics_service = AIMetricsService(db_session)

        # Get initial counts
        initial_accuracy = await metrics_service.get_vote_accuracy()
        initial_total = initial_accuracy["total_votes"]
        initial_correct = initial_accuracy["correct_votes"]
        initial_incorrect = initial_accuracy["incorrect_votes"]

        # Add vote metrics
        votes = [
            AIMetric(
                operation_type="vote_generation",
                provider="openai",
                model="gpt-5-nano",
                success=True,
                vote_correct=True,
            ),
            AIMetric(
                operation_type="vote_generation",
                provider="openai",
                model="gpt-5-nano",
                success=True,
                vote_correct=True,
            ),
            AIMetric(
                operation_type="vote_generation",
                provider="openai",
                model="gpt-5-nano",
                success=True,
                vote_correct=False,
            ),
        ]

        for vote in votes:
            db_session.add(vote)
        await db_session.commit()

        # Get accuracy
        accuracy = await metrics_service.get_vote_accuracy()

        # Assert the new metrics were added correctly
        assert accuracy["total_votes"] == initial_total + 3
        assert accuracy["correct_votes"] == initial_correct + 2
        assert accuracy["incorrect_votes"] == initial_incorrect + 1

        # Check that the accuracy calculation is correct based on the new data
        expected_accuracy = ((initial_correct + 2) / (initial_total + 3)) * 100
        assert accuracy["accuracy_percent"] == pytest.approx(expected_accuracy, rel=0.1)


class TestAIPlayerManagement:
    """Test AI player creation and management."""

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_get_or_create_ai_player_creates_new(self, db_session):
        """Should create AI player if it doesn't exist."""
        service = AIService(db_session)

        with (
            patch(
                'backend.services.username_service.UsernameService.generate_unique_username',
                new=AsyncMock(return_value=("AI BACKUP", "aibackup")),
            ) as mock_generate,
            patch('backend.services.player_service.PlayerService.create_player') as mock_create,
        ):
            mock_player = Player(
                player_id=uuid.uuid4(),
                username="AI_BACKUP",
                email="ai_copy_backup@quipflip.internal",
                balance=1000,
            )
            mock_create.return_value = mock_player

            player = await service._get_or_create_ai_player()

            assert player.username == "AI_BACKUP"
            mock_create.assert_called_once()
            mock_generate.assert_awaited_once()

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_get_or_create_ai_player_reuses_existing(self, db_session):
        """Should reuse existing AI player."""
        # Create AI player first with a randomized username
        ai_player = Player(
            player_id=uuid.uuid4(),
            username="AI Copy Runner",
            username_canonical="aicopyrunner",
            email="ai_copy_backup@quipflip.internal",
            password_hash="not-used",
            balance=1000,
        )
        db_session.add(ai_player)
        await db_session.commit()

        service = AIService(db_session)

        with patch('backend.services.player_service.PlayerService.create_player') as mock_create:
            player = await service._get_or_create_ai_player()

            assert player.username == "AI Copy Runner"
            assert player.player_id == ai_player.player_id
            mock_create.assert_not_called()


@dataclass
class PhrasesetScenario:
    """Container for phraseset test data."""

    prompt_round: Round
    copy_rounds: tuple[Round, Round]
    phraseset: Phraseset


async def _create_phraseset_scenario(
    db_session,
    *,
    base_settings,
    prompter,
    copy_players,
    prompt_text,
    original_phrase,
    copy_phrases,
    created_at,
    include_human_vote=False,
    human_voter=None,
):
    """Create a phraseset scenario for backup cycle tests."""

    if len(copy_players) != 2:
        raise ValueError("copy_players must contain exactly two players")
    if len(copy_phrases) != 2:
        raise ValueError("copy_phrases must contain exactly two entries")

    prompt_round = Round(
        round_id=uuid.uuid4(),
        player_id=prompter.player_id,
        round_type="prompt",
        status="submitted",
        created_at=created_at - timedelta(minutes=2),
        expires_at=created_at + timedelta(minutes=1),
        cost=base_settings.prompt_cost,
        prompt_text=prompt_text,
        submitted_phrase=original_phrase,
        phraseset_status="active",
        copy1_player_id=copy_players[0].player_id,
        copy2_player_id=copy_players[1].player_id,
    )

    copy_rounds = []
    for index, (copy_player, copy_phrase) in enumerate(zip(copy_players, copy_phrases), start=1):
        copy_rounds.append(
            Round(
                round_id=uuid.uuid4(),
                player_id=copy_player.player_id,
                round_type="copy",
                status="submitted",
                created_at=created_at - timedelta(minutes=1, seconds=45 - (index * 15)),
                expires_at=created_at + timedelta(minutes=2),
                cost=base_settings.copy_cost_normal,
                prompt_round_id=prompt_round.round_id,
                original_phrase=original_phrase,
                copy_phrase=copy_phrase,
                system_contribution=0,
            )
        )

    db_session.add_all([prompt_round, *copy_rounds])
    await db_session.flush()

    phraseset = Phraseset(
        phraseset_id=uuid.uuid4(),
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy_rounds[0].round_id,
        copy_round_2_id=copy_rounds[1].round_id,
        prompt_text=prompt_text,
        original_phrase=original_phrase,
        copy_phrase_1=copy_phrases[0],
        copy_phrase_2=copy_phrases[1],
        status="open",
        created_at=created_at - timedelta(minutes=1),
        vote_count=1 if include_human_vote else 0,
        total_pool=(
            base_settings.prize_pool_base
            + base_settings.vote_cost
            - base_settings.vote_payout_correct
            if include_human_vote
            else base_settings.prize_pool_base
        ),
        vote_contributions=base_settings.vote_cost if include_human_vote else 0,
        vote_payouts_paid=base_settings.vote_payout_correct if include_human_vote else 0,
        system_contribution=0,
    )

    db_session.add(phraseset)

    vote = None
    if include_human_vote:
        if human_voter is None:
            raise ValueError("human_voter is required when include_human_vote is True")
        vote = Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=human_voter.player_id,
            voted_phrase=original_phrase,
            correct=True,
            payout=base_settings.vote_payout_correct,
            created_at=created_at - timedelta(seconds=30),
        )
        db_session.add(vote)

    return PhrasesetScenario(prompt_round, (copy_rounds[0], copy_rounds[1]), phraseset), vote


class TestAIBackupCycle:
    """Test AI backup cycle behavior."""

    @pytest.mark.asyncio
    async def test_run_backup_cycle_skips_phrasesets_without_human_votes(
        self,
        db_session,
        player_factory,
    ):
        """AI should only vote on phrasesets that already have human votes."""

        base_settings = get_settings()
        custom_settings = base_settings.model_copy(
            update={
                "openai_api_key": "sk-test",
                "use_phrase_validator_api": False,
                "ai_backup_delay_minutes": 0,
                "ai_backup_batch_size": 5,
            }
        )

        prompter = await player_factory()
        copier1 = await player_factory()
        copier2 = await player_factory()
        copier3 = await player_factory()
        copier4 = await player_factory()
        human_voter = await player_factory()

        now = datetime.now(UTC)

        scenario_with_vote, _ = await _create_phraseset_scenario(
            db_session,
            base_settings=base_settings,
            prompter=prompter,
            copy_players=(copier1, copier2),
            prompt_text="Prompt with human vote",
            original_phrase="ORIGINAL ONE",
            copy_phrases=("COPY ONE A", "COPY ONE B"),
            created_at=now,
            include_human_vote=True,
            human_voter=human_voter,
        )
        _ = await _create_phraseset_scenario(
            db_session,
            base_settings=base_settings,
            prompter=prompter,
            copy_players=(copier3, copier4),
            prompt_text="Prompt without human vote",
            original_phrase="ORIGINAL TWO",
            copy_phrases=("COPY TWO A", "COPY TWO B"),
            created_at=now,
            include_human_vote=False,
        )

        await db_session.commit()

        async def fake_generate_vote_choice(self, phraseset):
            return phraseset.original_phrase

        with (
            patch("backend.services.ai.ai_service.get_settings", return_value=custom_settings),
            patch.object(AIService, "generate_vote_choice", new=fake_generate_vote_choice),
            patch(
                "backend.services.vote_service.VoteService.submit_system_vote",
                new_callable=AsyncMock,
            ) as mock_submit_vote,
            patch("random.randint", return_value=1234),
        ):
            mock_submit_vote.return_value = MagicMock(
                voted_phrase="ORIGINAL ONE",
                correct=True,
                payout=base_settings.vote_payout_correct,
            )

            service = AIService(db_session)
            await service.run_backup_cycle()

        assert mock_submit_vote.await_count == 1
        called_phraseset = mock_submit_vote.await_args_list[0].kwargs["phraseset"]
        assert called_phraseset.phraseset_id == scenario_with_vote.phraseset.phraseset_id
