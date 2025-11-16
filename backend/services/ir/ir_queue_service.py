"""IR Queue Service - Queue management for entry and voting phases."""

import logging
from typing import Optional
from datetime import datetime, UTC, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.models.ir.ir_backronym_set import IRBackronymSet
from backend.models.ir.enums import IRSetStatus

logger = logging.getLogger(__name__)


class IRQueueError(RuntimeError):
    """Raised when queue service fails."""


class IRQueueService:
    """Service for managing queues of sets needing entries or votes."""

    _entry_queue: list[str] = []
    _voting_queue: list[str] = []

    def __init__(self, db: AsyncSession):
        """Initialize IR queue service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_next_open_set(self) -> Optional[str]:
        """Get next set from entry queue (FIFO).

        Returns oldest enqueued open set with capacity < 5.
        Uses in-memory queue for FIFO ordering; falls back to database query if queue is empty.

        Returns:
            str: Set ID or None if no open sets

        Raises:
            IRQueueError: If queue operation fails
        """
        try:
            # Check in-memory queue first (FIFO)
            while self._entry_queue:
                set_id = self._entry_queue[0]

                # Verify set still exists and is eligible
                stmt = select(IRBackronymSet).where(
                    and_(
                        IRBackronymSet.set_id == set_id,
                        IRBackronymSet.status == IRSetStatus.OPEN,
                        IRBackronymSet.entry_count < 5,
                    )
                )
                result = await self.db.execute(stmt)
                set_obj = result.scalars().first()

                if set_obj:
                    return str(set_id)
                else:
                    # Set is no longer eligible, remove from queue
                    self._entry_queue.pop(0)

            # Fallback: Query database if in-memory queue is empty
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

            return str(set_obj.set_id) if set_obj else None

        except Exception as e:
            raise IRQueueError(f"Failed to get next open set: {str(e)}") from e

    async def get_next_voting_set(self) -> Optional[str]:
        """Get next set from voting queue (FIFO priority).

        Returns oldest enqueued set in voting phase with vote count < 5.
        Uses in-memory queue for FIFO ordering; falls back to database query if queue is empty.

        Returns:
            str: Set ID or None if no voting sets

        Raises:
            IRQueueError: If queue operation fails
        """
        try:
            # Check in-memory queue first (FIFO)
            while self._voting_queue:
                set_id = self._voting_queue[0]

                # Verify set still exists and is eligible
                stmt = select(IRBackronymSet).where(
                    and_(
                        IRBackronymSet.set_id == set_id,
                        IRBackronymSet.status == IRSetStatus.VOTING,
                        IRBackronymSet.vote_count < 5,
                    )
                )
                result = await self.db.execute(stmt)
                set_obj = result.scalars().first()

                if set_obj:
                    return str(set_id)
                else:
                    # Set is no longer eligible, remove from queue
                    self._voting_queue.pop(0)

            # Fallback: Query database if in-memory queue is empty
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

            return str(set_obj.set_id) if set_obj else None

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
            if set_id not in self._entry_queue:
                self._entry_queue.append(set_id)
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
            if set_id not in self._voting_queue:
                self._voting_queue.append(set_id)
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
            if set_id in self._entry_queue:
                self._entry_queue.remove(set_id)
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
            if set_id in self._voting_queue:
                self._voting_queue.remove(set_id)
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
        """Get length of in-memory entry queue.

        Returns:
            int: Queue length
        """
        return len(self._entry_queue)

    def get_voting_queue_length(self) -> int:
        """Get length of in-memory voting queue.

        Returns:
            int: Queue length
        """
        return len(self._voting_queue)
