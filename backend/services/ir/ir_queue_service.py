"""IR Queue Service - Queue management for entry and voting phases."""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.models.ir.ir_backronym_set import IRBackronymSet
from backend.models.ir.enums import IRSetStatus
from backend.utils import queue_client

logger = logging.getLogger(__name__)


ENTRY_QUEUE = "queue:ir:entry_sets"
VOTING_QUEUE = "queue:ir:voting_sets"


class IRQueueError(RuntimeError):
    """Raised when queue service fails."""


class IRQueueService:
    """Service for managing queues of sets needing entries or votes."""

    def __init__(self, db: AsyncSession):
        """Initialize IR queue service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_next_open_set(self) -> Optional[str]:
        """Get next set from entry queue (FIFO).

        Returns oldest enqueued open set with capacity < 5.
        Uses the shared queue infrastructure for FIFO ordering; falls back to
        database query if queue is empty.

        Returns:
            str: Set ID or None if no open sets

        Raises:
            IRQueueError: If queue operation fails
        """
        try:
            queued = await self._get_next_from_queue(
                queue_name=ENTRY_QUEUE,
                required_status=IRSetStatus.OPEN,
                count_attr=IRBackronymSet.entry_count,
                max_count=5,
            )
            if queued:
                return queued

            # Fallback: Query database if queue empty
            stmt = (
                select(IRBackronymSet)
                .where(
                    and_(
                        IRBackronymSet.status == IRSetStatus.OPEN,
                        IRBackronymSet.entry_count < 5,
                    )
                )
                .order_by(IRBackronymSet.created_at.asc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            set_obj = result.scalars().first()

            if set_obj:
                await self.enqueue_entry_set(str(set_obj.set_id))
                return str(set_obj.set_id)

            return None

        except Exception as e:
            raise IRQueueError(f"Failed to get next open set: {str(e)}") from e

    async def get_next_voting_set(self) -> Optional[str]:
        """Get next set from voting queue (FIFO priority).

        Returns oldest enqueued set in voting phase with vote count < 5.
        Uses the shared queue infrastructure for FIFO ordering; falls back to
        database query if queue is empty.

        Returns:
            str: Set ID or None if no voting sets

        Raises:
            IRQueueError: If queue operation fails
        """
        try:
            queued = await self._get_next_from_queue(
                queue_name=VOTING_QUEUE,
                required_status=IRSetStatus.VOTING,
                count_attr=IRBackronymSet.vote_count,
                max_count=5,
            )
            if queued:
                return queued

            # Fallback: Query database if queue empty
            stmt = (
                select(IRBackronymSet)
                .where(
                    and_(
                        IRBackronymSet.status == IRSetStatus.VOTING,
                        IRBackronymSet.vote_count < 5,
                    )
                )
                .order_by(IRBackronymSet.created_at.asc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            set_obj = result.scalars().first()

            if set_obj:
                await self.enqueue_voting_set(str(set_obj.set_id))
                return str(set_obj.set_id)

            return None

        except Exception as e:
            raise IRQueueError(f"Failed to get next voting set: {str(e)}") from e

    async def enqueue_entry_set(self, set_id: str) -> None:
        """Add set to entry queue.

        Args:
            set_id: Set UUID

        Raises:
            IRQueueError: If enqueue fails
        """
        try:
            item = {"set_id": set_id}
            queue_client.remove(ENTRY_QUEUE, item)
            queue_client.push(ENTRY_QUEUE, item)
            logger.debug(f"Enqueued set {set_id} for entries")

        except Exception as e:
            raise IRQueueError(f"Failed to enqueue entry set: {str(e)}") from e

    async def enqueue_voting_set(self, set_id: str) -> None:
        """Add set to voting queue.

        Args:
            set_id: Set UUID

        Raises:
            IRQueueError: If enqueue fails
        """
        try:
            item = {"set_id": set_id}
            queue_client.remove(VOTING_QUEUE, item)
            queue_client.push(VOTING_QUEUE, item)
            logger.debug(f"Enqueued set {set_id} for voting")

        except Exception as e:
            raise IRQueueError(f"Failed to enqueue voting set: {str(e)}") from e

    async def dequeue_entry_set(self, set_id: str) -> None:
        """Remove set from entry queue (after filled to 5).

        Args:
            set_id: Set UUID

        Raises:
            IRQueueError: If dequeue fails
        """
        try:
            removed = queue_client.remove(ENTRY_QUEUE, {"set_id": set_id})
            if removed:
                logger.debug(f"Dequeued set {set_id} from entries")

        except Exception as e:
            raise IRQueueError(f"Failed to dequeue entry set: {str(e)}") from e

    async def dequeue_voting_set(self, set_id: str) -> None:
        """Remove set from voting queue (after finalized).

        Args:
            set_id: Set UUID

        Raises:
            IRQueueError: If dequeue fails
        """
        try:
            removed = queue_client.remove(VOTING_QUEUE, {"set_id": set_id})
            if removed:
                logger.debug(f"Dequeued set {set_id} from voting")

        except Exception as e:
            raise IRQueueError(f"Failed to dequeue voting set: {str(e)}") from e

    async def get_queue_stats(self) -> dict:
        """Get current queue statistics.

        Returns:
            dict: Queue stats
        """
        try:
            # Count sets in each status
            open_stmt = select(IRBackronymSet).where(
                IRBackronymSet.status == IRSetStatus.OPEN
            )
            open_result = await self.db.execute(open_stmt)
            open_sets = len(open_result.scalars().all())

            voting_stmt = select(IRBackronymSet).where(
                IRBackronymSet.status == IRSetStatus.VOTING
            )
            voting_result = await self.db.execute(voting_stmt)
            voting_sets = len(voting_result.scalars().all())

            finalized_stmt = select(IRBackronymSet).where(
                IRBackronymSet.status == IRSetStatus.FINALIZED
            )
            finalized_result = await self.db.execute(finalized_stmt)
            finalized_sets = len(finalized_result.scalars().all())

            return {
                "open_sets": open_sets,
                "voting_sets": voting_sets,
                "finalized_sets": finalized_sets,
                "total_sets": open_sets + voting_sets + finalized_sets,
            }

        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {}

    def get_entry_queue_length(self) -> int:
        """Get length of the distributed entry queue.

        Returns:
            int: Queue length
        """
        return queue_client.length(ENTRY_QUEUE)

    def get_voting_queue_length(self) -> int:
        """Get length of the distributed voting queue.

        Returns:
            int: Queue length
        """
        return queue_client.length(VOTING_QUEUE)

    async def _get_next_from_queue(
        self,
        queue_name: str,
        required_status: str,
        count_attr,
        max_count: int,
    ) -> Optional[str]:
        """Return the next queued set that still satisfies eligibility checks."""

        # Allow a few stale removals each call to avoid tight loops
        max_attempts = 10
        attempts = 0
        column_name = getattr(count_attr, "key", count_attr)
        while attempts < max_attempts:
            queued_item = queue_client.peek(queue_name)
            if not queued_item:
                return None

            set_id = queued_item.get("set_id")
            stmt = select(IRBackronymSet).where(IRBackronymSet.set_id == set_id)
            result = await self.db.execute(stmt)
            set_obj = result.scalars().first()

            if (
                set_obj
                and set_obj.status == required_status
                and getattr(set_obj, column_name) < max_count
            ):
                return str(set_id)

            # Drop stale head item and keep scanning
            queue_client.pop(queue_name)
            attempts += 1

        return None
