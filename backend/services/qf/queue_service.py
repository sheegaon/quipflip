"""Queue management service."""
from uuid import UUID
import logging

from backend.utils import queue_client
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Queue names
PROMPT_QUEUE = "queue:prompts"
PHRASESET_QUEUE = "queue:phrasesets"


class QFQueueService:
    """Service for managing game queues."""

    @staticmethod
    def add_prompt_round_to_queue(prompt_round_id: UUID):
        """Add prompt to queue waiting for copy players."""
        queue_client.push(PROMPT_QUEUE, {"prompt_round_id": str(prompt_round_id)})
        new_length = queue_client.length(PROMPT_QUEUE)
        logger.info(f"[Queue Push] Added prompt to queue: {prompt_round_id} (queue now has {new_length} items)")

    @staticmethod
    def get_next_prompt_round() -> UUID | None:
        """Get next prompt from queue (FIFO)."""
        queue_length_before = queue_client.length(PROMPT_QUEUE)
        item = queue_client.pop(PROMPT_QUEUE)
        if item:
            logger.info(f"[Queue Pop] Retrieved prompt from queue: {item['prompt_round_id']} (queue had {queue_length_before} items)")
            return UUID(item["prompt_round_id"])
        logger.info(f"[Queue Pop] No items in queue (length was {queue_length_before})")
        return None

    @staticmethod
    def get_next_prompt_round_batch(count: int) -> list[UUID]:
        """Get up to ``count`` prompts from the queue preserving FIFO order."""
        if count <= 0:
            return []

        queue_length_before = queue_client.length(PROMPT_QUEUE)
        items = queue_client.pop_many(PROMPT_QUEUE, count)
        if not items:
            logger.info(
                f"[Queue Pop] Batch request for {count} prompts returned none (queue length was {queue_length_before})"
            )
            return []

        prompt_ids = [UUID(item["prompt_round_id"]) for item in items]
        logger.info(
            f"[Queue Pop] Retrieved {len(prompt_ids)} prompts from queue (requested {count}, queue had "
            f"{queue_length_before} items)"
        )
        return prompt_ids

    @staticmethod
    def remove_prompt_round_from_queue(prompt_round_id: UUID) -> bool:
        """Remove specific prompt from queue (for abandoned rounds)."""
        item = {"prompt_round_id": str(prompt_round_id)}
        removed = queue_client.remove(PROMPT_QUEUE, item)
        if removed:
            logger.info(f"Removed prompt from queue: {prompt_round_id}")
        return removed

    @staticmethod
    def remove_prompt_rounds_from_queue(prompt_round_ids: list[UUID]) -> int:
        """
        Remove multiple prompt rounds from queue in bulk.

        Args:
            prompt_round_ids: List of prompt round IDs to remove

        Returns:
            Number of prompts successfully removed
        """
        if not prompt_round_ids:
            return 0

        removed_count = 0
        for prompt_round_id in prompt_round_ids:
            item = {"prompt_round_id": str(prompt_round_id)}
            if queue_client.remove(PROMPT_QUEUE, item):
                removed_count += 1

        if removed_count > 0:
            logger.info(f"[Queue Cleanup] Removed {removed_count} prompts from queue")

        return removed_count

    @staticmethod
    def clear_prompt_queue() -> int:
        """
        Clear all items from the prompt queue.

        Returns:
            Number of items cleared
        """
        count = queue_client.length(PROMPT_QUEUE)
        if count > 0:
            queue_client.clear(PROMPT_QUEUE)
            logger.info(f"[Queue Clear] Cleared {count} items from prompt queue")
        return count

    @staticmethod
    def get_prompt_rounds_waiting() -> int:
        """Get count of prompt rounds waiting for copies."""
        return queue_client.length(PROMPT_QUEUE)

    @staticmethod
    def is_copy_discount_active() -> bool:
        """Check if copy discount should be applied."""
        waiting = QFQueueService.get_prompt_rounds_waiting()
        active = waiting > settings.copy_discount_threshold
        if active:
            logger.info(f"Copy discount active: {waiting} quips waiting")
        return active

    @staticmethod
    def get_copy_cost() -> int:
        """Get current copy cost (with discount if applicable)."""
        return (
            settings.copy_cost_discount
            if QFQueueService.is_copy_discount_active()
            else settings.copy_cost_normal
        )

    @staticmethod
    def add_phraseset_to_queue(phraseset_id: UUID):
        """Add phraseset to voting queue."""
        queue_client.push(PHRASESET_QUEUE, {"phraseset_id": str(phraseset_id)})
        logger.info(f"Added phraseset to queue: {phraseset_id}")

    @staticmethod
    def get_phrasesets_waiting() -> int:
        """Get count of phrasesets waiting for votes."""
        return queue_client.length(PHRASESET_QUEUE)

    @staticmethod
    def has_prompt_rounds_available() -> bool:
        """Check if prompt rounds available for copy rounds."""
        return QFQueueService.get_prompt_rounds_waiting() > 0

    @staticmethod
    def has_phrasesets_available() -> bool:
        """Check if phrasesets available for voting."""
        return QFQueueService.get_phrasesets_waiting() > 0
