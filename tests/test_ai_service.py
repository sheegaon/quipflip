"""
Comprehensive integration tests for AI service.

Tests AI copy generation, voting, metrics tracking, and error handling.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC
import uuid

from backend.services.ai.ai_service import AIService, AICopyError, AIVoteError, AIServiceError
from backend.services.ai_metrics_service import AIMetricsService
from backend.services.phrase_validator import PhraseValidator
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.models.ai_metric import AIMetric


@pytest.fixture
def mock_validator():
    """Mock phrase validator."""
    validator = MagicMock(spec=PhraseValidator)
    validator.validate.return_value = (True, "")
    return validator


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
    round_obj.prompt_text = "What do you say to celebrate someone's birth?"
    return round_obj


@pytest.fixture
def mock_phraseset():
    """Create a mock phraseset for voting tests."""
    phraseset = MagicMock(spec=PhraseSet)
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
    @patch('backend.services.phrase_validator.get_phrase_validator')
    def test_select_openai_when_configured(self, mock_get_validator, db_session):
        """Should select OpenAI when configured and API key available."""
        mock_validator = MagicMock()
        mock_get_validator.return_value = mock_validator

        with patch('backend.services.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'openai'
            settings.openai_api_key = 'sk-test'
            settings.use_phrase_validator_api = False
            service = AIService(db_session)
            assert service.provider == "openai"

    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key', 'AI_PROVIDER': 'gemini'}, clear=True)
    @patch('backend.services.phrase_validator.get_phrase_validator')
    def test_select_gemini_when_configured(self, mock_get_validator, db_session):
        """Should select Gemini when configured and API key available."""
        mock_validator = MagicMock()
        mock_get_validator.return_value = mock_validator

        with patch('backend.services.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'gemini'
            settings.gemini_api_key = 'test-key'
            settings.use_phrase_validator_api = False
            service = AIService(db_session)
            assert service.provider == "gemini"

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'}, clear=True)
    @patch('backend.services.phrase_validator.get_phrase_validator')
    def test_fallback_to_openai_when_gemini_unavailable(self, mock_get_validator, db_session):
        """Should fallback to OpenAI when Gemini configured but unavailable."""
        mock_validator = MagicMock()
        mock_get_validator.return_value = mock_validator

        with patch('backend.services.ai_service.get_settings') as mock_settings:
            settings = mock_settings.return_value
            settings.ai_provider = 'gemini'
            settings.openai_api_key = 'sk-test'
            settings.gemini_api_key = None
            settings.use_phrase_validator_api = False
            service = AIService(db_session)
            assert service.provider == "openai"

    @patch.dict('os.environ', {}, clear=True)
    @patch('backend.services.phrase_validator.get_phrase_validator')
    def test_raise_error_when_no_provider_available(self, mock_get_validator, db_session):
        """Should raise error when no API keys available."""
        mock_validator = MagicMock()
        mock_get_validator.return_value = mock_validator

        with patch('backend.services.ai_service.get_settings') as mock_settings:
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
    @patch('backend.services.openai_api.generate_copy')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_copy_with_openai(
            self, mock_openai, db_session, mock_prompt_round
    ):
        """Should generate copy using OpenAI."""
        mock_openai.return_value = "joyful celebration"

        service = AIService(db_session)
        # Mock the phrase validator's validate_copy method to return success
        with patch.object(service.phrase_validator, 'validate_copy', return_value=(True, "")):
            result = await service.generate_copy_phrase(
                original_phrase="happy birthday",
                prompt_round=mock_prompt_round,
            )

        assert result == "joyful celebration"
        mock_openai.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.services.gemini_api.generate_copy')
    @patch('backend.services.phrase_validator.get_phrase_validator')
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}, clear=True)
    async def test_generate_copy_with_gemini(
            self, mock_get_validator, mock_gemini, db_session, mock_prompt_round
    ):
        """Should generate copy using Gemini."""
        mock_gemini.return_value = "merry festivity"
        mock_validator = MagicMock()
        # Mock validate_copy as an async function
        from unittest.mock import AsyncMock
        mock_validator.validate_copy = AsyncMock(return_value=(True, ""))
        mock_get_validator.return_value = mock_validator

        with patch('backend.services.ai_service.get_settings') as mock_settings:
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

            assert result == "merry festivity"
            mock_gemini.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.services.openai_api.generate_copy')
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
    @patch('backend.services.openai_api.generate_copy')
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
    @patch('backend.services.ai_vote_helper.generate_vote_choice')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_vote_choice(
            self, mock_vote, db_session, mock_validator, mock_phraseset
    ):
        """Should generate vote choice using AI."""
        # AI chooses index 0 (original phrase)
        mock_vote.return_value = 0

        service = AIService(db_session)
        result = await service.generate_vote_choice(mock_phraseset)

        assert result == "happy birthday"
        mock_vote.assert_called_once()

    @pytest.mark.asyncio
    @patch('backend.services.ai_vote_helper.generate_vote_choice')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_generate_vote_incorrect_choice(
            self, mock_vote, db_session, mock_validator, mock_phraseset
    ):
        """Should handle incorrect vote choices."""
        # AI chooses index 1 (copy phrase)
        mock_vote.return_value = 1

        service = AIService(db_session)
        result = await service.generate_vote_choice(mock_phraseset)

        assert result == "joyful anniversary"


class TestAIMetrics:
    """Test AI metrics tracking."""

    @pytest.mark.asyncio
    @patch('backend.services.openai_api.generate_copy')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_metrics_recorded_on_success(
            self, mock_openai, db_session, mock_prompt_round
    ):
        """Should record metrics on successful operation."""
        mock_openai.return_value = "joyful celebration"

        service = AIService(db_session)
        # Mock the phrase validator's validate_copy method to return success
        with patch.object(service.phrase_validator, 'validate_copy', return_value=(True, "")):
            await service.generate_copy_phrase(
                original_phrase="happy birthday",
                prompt_round=mock_prompt_round,
            )

        # Check that metric was created (but not committed yet)
        metrics = db_session.new
        ai_metrics = [m for m in metrics if isinstance(m, AIMetric)]
        assert len(ai_metrics) == 1

        metric = ai_metrics[0]
        assert metric.operation_type == "copy_generation"
        assert metric.provider == "openai"
        assert metric.success is True
        assert metric.validation_passed is True

    @pytest.mark.asyncio
    @patch('backend.services.openai_api.generate_copy')
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
    @patch('backend.services.ai_vote_helper.generate_vote_choice')
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_vote_metrics_track_correctness(
            self, mock_vote, db_session, mock_validator, mock_phraseset
    ):
        """Should track whether AI vote was correct."""
        mock_vote.return_value = 0  # Correct choice

        service = AIService(db_session)
        await service.generate_vote_choice(mock_phraseset)

        metrics = db_session.new
        ai_metrics = [m for m in metrics if isinstance(m, AIMetric)]
        assert len(ai_metrics) == 1

        metric = ai_metrics[0]
        assert metric.operation_type == "vote_generation"
        assert metric.vote_correct is True


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

        with patch('backend.services.player_service.PlayerService.create_player') as mock_create:
            mock_player = Player(
                player_id=uuid.uuid4(),
                username="AI_BACKUP",
                email="ai@quipflip.internal",
                balance=1000,
            )
            mock_create.return_value = mock_player

            player = await service._get_or_create_ai_player()

            assert player.username == "AI_BACKUP"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test'})
    async def test_get_or_create_ai_player_reuses_existing(self, db_session):
        """Should reuse existing AI player."""
        # Create AI player first
        ai_player = Player(
            player_id=uuid.uuid4(),
            username="AI_BACKUP",
            username_canonical="ai_backup",
            pseudonym="AI Assistant",
            pseudonym_canonical="ai assistant",
            email="ai@quipflip.internal",
            password_hash="not-used",
            balance=1000,
        )
        db_session.add(ai_player)
        await db_session.commit()

        service = AIService(db_session)

        with patch('backend.services.player_service.PlayerService.create_player') as mock_create:
            player = await service._get_or_create_ai_player()

            assert player.username == "AI_BACKUP"
            assert player.player_id == ai_player.player_id
            mock_create.assert_not_called()
