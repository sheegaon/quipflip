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


class QueueService:
    """Service for managing game queues."""

    @staticmethod
    def add_prompt_to_queue(prompt_round_id: UUID):
        """Add prompt to queue waiting for copy players."""
        queue_client.push(PROMPT_QUEUE, {"prompt_round_id": str(prompt_round_id)})
        logger.info(f"Added prompt to queue: {prompt_round_id}")

    @staticmethod
    def get_next_prompt() -> UUID | None:
        """Get next prompt from queue (FIFO)."""
        item = queue_client.pop(PROMPT_QUEUE)
        if item:
            logger.info(f"Retrieved prompt from queue: {item['prompt_round_id']}")
            return UUID(item["prompt_round_id"])
        return None

    @staticmethod
    def remove_prompt_from_queue(prompt_round_id: UUID) -> bool:
        """Remove specific prompt from queue (for abandoned rounds)."""
        item = {"prompt_round_id": str(prompt_round_id)}
        removed = queue_client.remove(PROMPT_QUEUE, item)
        if removed:
            logger.info(f"Removed prompt from queue: {prompt_round_id}")
        return removed

    @staticmethod
    def get_prompts_waiting() -> int:
        """Get count of prompts waiting for copies."""
        return queue_client.length(PROMPT_QUEUE)

    @staticmethod
    def is_copy_discount_active() -> bool:
        """Check if copy discount should be applied."""
        waiting = QueueService.get_prompts_waiting()
        active = waiting > settings.copy_discount_threshold
        if active:
            logger.debug(f"Copy discount active: {waiting} quips waiting")
        return active

    @staticmethod
    def get_copy_cost() -> int:
        """Get current copy cost (with discount if applicable)."""
        return (
            settings.copy_cost_discount
            if QueueService.is_copy_discount_active()
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
    def has_prompts_available() -> bool:
        """Check if prompts available for copy rounds."""
        return QueueService.get_prompts_waiting() > 0

    @staticmethod
    def has_phrasesets_available() -> bool:
        """Check if phrasesets available for voting."""
        return QueueService.get_phrasesets_waiting() > 0
