"""
Tests for QueueService.

Tests cover:
- Adding prompt rounds to queue
- Getting next prompt round (FIFO)
- Removing specific prompt rounds
- Getting prompt rounds waiting count
- Copy discount activation logic
- Dynamic copy cost calculation
- Adding phrasesets to queue
- Getting phrasesets waiting count
- Availability checks for prompts and phrasesets
"""

import pytest
from unittest.mock import patch
from uuid import UUID, uuid4

from backend.services import QueueService, PROMPT_QUEUE, PHRASESET_QUEUE
from backend.config import get_settings


@pytest.fixture
def mock_queue_client():
    """Mock queue client for testing."""
    with patch("backend.services.queue_service.queue_client") as mock_client:
        # Default mock behavior - empty queue
        mock_client.length.return_value = 0
        mock_client.pop.return_value = None
        mock_client.push.return_value = None
        mock_client.remove.return_value = False
        yield mock_client


@pytest.fixture
def sample_prompt_round_id():
    """Sample UUID for testing."""
    return uuid4()


@pytest.fixture
def sample_phraseset_id():
    """Sample UUID for testing."""
    return uuid4()


class TestPromptQueueOperations:
    """Test prompt queue operations."""

    def test_add_prompt_round_to_queue(self, mock_queue_client, sample_prompt_round_id):
        """Should add prompt round to queue and log new length."""
        mock_queue_client.length.return_value = 5

        QueueService.add_prompt_round_to_queue(sample_prompt_round_id)

        mock_queue_client.push.assert_called_once_with(
            PROMPT_QUEUE, {"prompt_round_id": str(sample_prompt_round_id)}
        )
        mock_queue_client.length.assert_called_once_with(PROMPT_QUEUE)

    def test_get_next_prompt_round_success(self, mock_queue_client, sample_prompt_round_id):
        """Should retrieve next prompt round from queue (FIFO)."""
        mock_queue_client.length.return_value = 3
        mock_queue_client.pop.return_value = {"prompt_round_id": str(sample_prompt_round_id)}

        result = QueueService.get_next_prompt_round()

        assert isinstance(result, UUID)
        assert result == sample_prompt_round_id
        mock_queue_client.length.assert_called_once_with(PROMPT_QUEUE)
        mock_queue_client.pop.assert_called_once_with(PROMPT_QUEUE)

    def test_get_next_prompt_round_empty_queue(self, mock_queue_client):
        """Should return None when queue is empty."""
        mock_queue_client.length.return_value = 0
        mock_queue_client.pop.return_value = None

        result = QueueService.get_next_prompt_round()

        assert result is None
        mock_queue_client.pop.assert_called_once_with(PROMPT_QUEUE)

    def test_remove_prompt_round_from_queue_success(
        self, mock_queue_client, sample_prompt_round_id
    ):
        """Should remove specific prompt round from queue."""
        mock_queue_client.remove.return_value = True

        result = QueueService.remove_prompt_round_from_queue(sample_prompt_round_id)

        assert result is True
        mock_queue_client.remove.assert_called_once_with(
            PROMPT_QUEUE, {"prompt_round_id": str(sample_prompt_round_id)}
        )

    def test_remove_prompt_round_from_queue_not_found(
        self, mock_queue_client, sample_prompt_round_id
    ):
        """Should return False when prompt round not in queue."""
        mock_queue_client.remove.return_value = False

        result = QueueService.remove_prompt_round_from_queue(sample_prompt_round_id)

        assert result is False
        mock_queue_client.remove.assert_called_once()

    def test_get_prompt_rounds_waiting(self, mock_queue_client):
        """Should return count of prompt rounds waiting."""
        mock_queue_client.length.return_value = 7

        result = QueueService.get_prompt_rounds_waiting()

        assert result == 7
        mock_queue_client.length.assert_called_once_with(PROMPT_QUEUE)

    def test_has_prompt_rounds_available_true(self, mock_queue_client):
        """Should return True when prompt rounds are available."""
        mock_queue_client.length.return_value = 5

        result = QueueService.has_prompt_rounds_available()

        assert result is True

    def test_has_prompt_rounds_available_false(self, mock_queue_client):
        """Should return False when no prompt rounds available."""
        mock_queue_client.length.return_value = 0

        result = QueueService.has_prompt_rounds_available()

        assert result is False


class TestCopyDiscountLogic:
    """Test copy discount activation and cost calculation."""

    def test_is_copy_discount_active_above_threshold(self, mock_queue_client):
        """Should activate discount when queue exceeds threshold."""
        settings = get_settings()
        mock_queue_client.length.return_value = settings.copy_discount_threshold + 1

        result = QueueService.is_copy_discount_active()

        assert result is True

    def test_is_copy_discount_active_at_threshold(self, mock_queue_client):
        """Should not activate discount at exact threshold."""
        settings = get_settings()
        mock_queue_client.length.return_value = settings.copy_discount_threshold

        result = QueueService.is_copy_discount_active()

        assert result is False

    def test_is_copy_discount_active_below_threshold(self, mock_queue_client):
        """Should not activate discount below threshold."""
        settings = get_settings()
        mock_queue_client.length.return_value = settings.copy_discount_threshold - 1

        result = QueueService.is_copy_discount_active()

        assert result is False

    def test_is_copy_discount_active_empty_queue(self, mock_queue_client):
        """Should not activate discount with empty queue."""
        mock_queue_client.length.return_value = 0

        result = QueueService.is_copy_discount_active()

        assert result is False

    def test_get_copy_cost_with_discount(self, mock_queue_client):
        """Should return discounted cost when discount is active."""
        settings = get_settings()
        mock_queue_client.length.return_value = settings.copy_discount_threshold + 5

        result = QueueService.get_copy_cost()

        assert result == settings.copy_cost_discount

    def test_get_copy_cost_without_discount(self, mock_queue_client):
        """Should return normal cost when discount is not active."""
        settings = get_settings()
        mock_queue_client.length.return_value = settings.copy_discount_threshold - 1

        result = QueueService.get_copy_cost()

        assert result == settings.copy_cost_normal

    def test_get_copy_cost_boundary_condition(self, mock_queue_client):
        """Should return normal cost exactly at threshold."""
        settings = get_settings()
        mock_queue_client.length.return_value = settings.copy_discount_threshold

        result = QueueService.get_copy_cost()

        assert result == settings.copy_cost_normal


class TestPhrasesetQueueOperations:
    """Test phraseset queue operations."""

    def test_add_phraseset_to_queue(self, mock_queue_client, sample_phraseset_id):
        """Should add phraseset to voting queue."""
        QueueService.add_phraseset_to_queue(sample_phraseset_id)

        mock_queue_client.push.assert_called_once_with(
            PHRASESET_QUEUE, {"phraseset_id": str(sample_phraseset_id)}
        )

    def test_get_phrasesets_waiting(self, mock_queue_client):
        """Should return count of phrasesets waiting for votes."""
        mock_queue_client.length.return_value = 12

        result = QueueService.get_phrasesets_waiting()

        assert result == 12
        mock_queue_client.length.assert_called_once_with(PHRASESET_QUEUE)

    def test_has_phrasesets_available_true(self, mock_queue_client):
        """Should return True when phrasesets are available."""
        mock_queue_client.length.return_value = 3

        result = QueueService.has_phrasesets_available()

        assert result is True

    def test_has_phrasesets_available_false(self, mock_queue_client):
        """Should return False when no phrasesets available."""
        mock_queue_client.length.return_value = 0

        result = QueueService.has_phrasesets_available()

        assert result is False


class TestQueueIntegration:
    """Test integration scenarios with multiple queue operations."""

    def test_fifo_order_simulation(self, mock_queue_client):
        """Should maintain FIFO order for prompt rounds."""
        prompt_ids = [uuid4(), uuid4(), uuid4()]

        # Simulate adding three prompts
        for prompt_id in prompt_ids:
            QueueService.add_prompt_round_to_queue(prompt_id)

        # Verify all three were pushed
        assert mock_queue_client.push.call_count == 3

        # Simulate retrieving in FIFO order
        for i, prompt_id in enumerate(prompt_ids):
            mock_queue_client.pop.return_value = {"prompt_round_id": str(prompt_id)}
            result = QueueService.get_next_prompt_round()
            assert result == prompt_id

    def test_discount_threshold_transition(self, mock_queue_client):
        """Should properly transition discount state at threshold."""
        settings = get_settings()

        # Below threshold - no discount
        mock_queue_client.length.return_value = settings.copy_discount_threshold - 1
        assert QueueService.is_copy_discount_active() is False
        assert QueueService.get_copy_cost() == settings.copy_cost_normal

        # At threshold - no discount
        mock_queue_client.length.return_value = settings.copy_discount_threshold
        assert QueueService.is_copy_discount_active() is False
        assert QueueService.get_copy_cost() == settings.copy_cost_normal

        # Above threshold - discount active
        mock_queue_client.length.return_value = settings.copy_discount_threshold + 1
        assert QueueService.is_copy_discount_active() is True
        assert QueueService.get_copy_cost() == settings.copy_cost_discount

    def test_remove_specific_prompt_from_full_queue(self, mock_queue_client, sample_prompt_round_id):
        """Should remove specific prompt even when queue has multiple items."""
        mock_queue_client.length.return_value = 15
        mock_queue_client.remove.return_value = True

        result = QueueService.remove_prompt_round_from_queue(sample_prompt_round_id)

        assert result is True
        mock_queue_client.remove.assert_called_once_with(
            PROMPT_QUEUE, {"prompt_round_id": str(sample_prompt_round_id)}
        )

    def test_both_queues_independent(self, mock_queue_client, sample_prompt_round_id, sample_phraseset_id):
        """Should manage prompt and phraseset queues independently."""
        # Add to both queues
        QueueService.add_prompt_round_to_queue(sample_prompt_round_id)
        QueueService.add_phraseset_to_queue(sample_phraseset_id)

        # Verify separate queue names used
        calls = mock_queue_client.push.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == PROMPT_QUEUE
        assert calls[1][0][0] == PHRASESET_QUEUE

    def test_empty_queues_initial_state(self, mock_queue_client):
        """Should handle empty queues correctly in initial state."""
        mock_queue_client.length.return_value = 0

        assert QueueService.get_prompt_rounds_waiting() == 0
        assert QueueService.get_phrasesets_waiting() == 0
        assert QueueService.has_prompt_rounds_available() is False
        assert QueueService.has_phrasesets_available() is False
        assert QueueService.get_next_prompt_round() is None
        assert QueueService.is_copy_discount_active() is False


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_multiple_identical_prompt_ids(self, mock_queue_client, sample_prompt_round_id):
        """Should handle adding same prompt ID multiple times."""
        # In practice this shouldn't happen, but testing the behavior
        QueueService.add_prompt_round_to_queue(sample_prompt_round_id)
        QueueService.add_prompt_round_to_queue(sample_prompt_round_id)

        assert mock_queue_client.push.call_count == 2

    def test_remove_from_empty_queue(self, mock_queue_client, sample_prompt_round_id):
        """Should handle removing from empty queue gracefully."""
        mock_queue_client.remove.return_value = False

        result = QueueService.remove_prompt_round_from_queue(sample_prompt_round_id)

        assert result is False

    def test_large_queue_count(self, mock_queue_client):
        """Should handle large queue counts correctly."""
        mock_queue_client.length.return_value = 999

        assert QueueService.get_prompt_rounds_waiting() == 999
        assert QueueService.is_copy_discount_active() is True

    def test_uuid_string_conversion_consistency(self, mock_queue_client):
        """Should maintain UUID string conversion consistency."""
        original_uuid = uuid4()

        QueueService.add_prompt_round_to_queue(original_uuid)

        # Verify UUID was converted to string for storage
        call_args = mock_queue_client.push.call_args[0][1]
        assert isinstance(call_args["prompt_round_id"], str)
        assert call_args["prompt_round_id"] == str(original_uuid)

    def test_get_next_prompt_round_uuid_parsing(self, mock_queue_client):
        """Should correctly parse UUID from queue response."""
        test_uuid = uuid4()
        mock_queue_client.pop.return_value = {"prompt_round_id": str(test_uuid)}

        result = QueueService.get_next_prompt_round()

        assert isinstance(result, UUID)
        assert result == test_uuid
