"""
AI Metrics Service for tracking and analyzing AI usage.

Provides comprehensive tracking of AI operations including costs,
performance, and success rates.
"""

import time
import uuid
from datetime import datetime, UTC, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from backend.models.ai_metric import AIMetric


# Cost estimates per 1000 tokens (approximate)
COST_PER_1K_TOKENS = {
    "gpt-5-nano": {"input": 0.00005, "output": 0.00015},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gemini-2.5-flash-lite": {"input": 0.00001, "output": 0.00003},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
}


@dataclass
class AIMetricsStats:
    """Statistics for AI operations."""
    total_operations: int
    successful_operations: int
    failed_operations: int
    success_rate: float
    total_cost_usd: float
    avg_latency_ms: float
    operations_by_provider: Dict[str, int]
    operations_by_type: Dict[str, int]


class AIMetricsService:
    """
    Service for tracking and analyzing AI metrics.

    Provides methods to record AI operations and generate analytics
    about usage, costs, and performance.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize AI metrics service.

        Args:
            db: Database session
        """
        self.db = db

    def _estimate_cost(
            self,
            model: str,
            prompt_length: int,
            response_length: int,
    ) -> float:
        """
        Estimate cost for an AI operation.

        Args:
            model: Model name
            prompt_length: Prompt length in characters
            response_length: Response length in characters

        Returns:
            Estimated cost in USD
        """
        # Rough estimate: 4 characters per token
        prompt_tokens = prompt_length / 4
        response_tokens = response_length / 4

        costs = COST_PER_1K_TOKENS.get(model, {"input": 0.0001, "output": 0.0003})
        input_cost = (prompt_tokens / 1000) * costs["input"]
        output_cost = (response_tokens / 1000) * costs["output"]

        return input_cost + output_cost

    async def record_operation(
            self,
            operation_type: str,
            provider: str,
            model: str,
            success: bool,
            latency_ms: Optional[int] = None,
            error_message: Optional[str] = None,
            prompt_length: Optional[int] = None,
            response_length: Optional[int] = None,
            validation_passed: Optional[bool] = None,
            vote_correct: Optional[bool] = None,
    ) -> AIMetric:
        """
        Record an AI operation for tracking.

        Args:
            operation_type: "copy_generation" or "vote_generation"
            provider: "openai" or "gemini"
            model: Model name
            success: Whether operation succeeded
            latency_ms: Response time in milliseconds
            error_message: Error message if failed
            prompt_length: Length of prompt in characters
            response_length: Length of response in characters
            validation_passed: For copy generation, whether validation passed
            vote_correct: For vote generation, whether vote was correct

        Returns:
            Created AIMetric instance
        """
        # Calculate estimated cost
        estimated_cost = None
        if success and prompt_length and response_length:
            estimated_cost = self._estimate_cost(model, prompt_length, response_length)

        metric = AIMetric(
            metric_id=uuid.uuid4(),
            operation_type=operation_type,
            provider=provider,
            model=model,
            success=success,
            latency_ms=latency_ms,
            error_message=error_message[:500] if error_message else None,
            estimated_cost_usd=estimated_cost,
            prompt_length=prompt_length,
            response_length=response_length,
            validation_passed=validation_passed,
            vote_correct=vote_correct,
        )

        self.db.add(metric)
        # Note: Caller should commit
        return metric

    async def get_stats(
            self,
            since: Optional[datetime] = None,
            operation_type: Optional[str] = None,
            provider: Optional[str] = None,
    ) -> AIMetricsStats:
        """
        Get statistics for AI operations.

        Args:
            since: Only include operations after this time (default: last 24 hours)
            operation_type: Filter by operation type
            provider: Filter by provider

        Returns:
            AIMetricsStats with aggregated statistics
        """
        if since is None:
            since = datetime.now(UTC) - timedelta(days=1)

        # Build query filters
        filters = [AIMetric.created_at >= since]
        if operation_type:
            filters.append(AIMetric.operation_type == operation_type)
        if provider:
            filters.append(AIMetric.provider == provider)

        # Get total operations
        total_result = await self.db.execute(
            select(func.count(AIMetric.metric_id)).where(and_(*filters))
        )
        total_operations = total_result.scalar() or 0

        # Get successful operations
        success_result = await self.db.execute(
            select(func.count(AIMetric.metric_id)).where(
                and_(*filters, AIMetric.success == True)
            )
        )
        successful_operations = success_result.scalar() or 0

        # Get total cost
        cost_result = await self.db.execute(
            select(func.sum(AIMetric.estimated_cost_usd)).where(and_(*filters))
        )
        total_cost = cost_result.scalar() or 0.0

        # Get average latency
        latency_result = await self.db.execute(
            select(func.avg(AIMetric.latency_ms)).where(
                and_(*filters, AIMetric.success == True, AIMetric.latency_ms.isnot(None))
            )
        )
        avg_latency = latency_result.scalar() or 0.0

        # Get operations by provider
        provider_result = await self.db.execute(
            select(AIMetric.provider, func.count(AIMetric.metric_id))
            .where(and_(*filters))
            .group_by(AIMetric.provider)
        )
        operations_by_provider = {row[0]: row[1] for row in provider_result.all()}

        # Get operations by type
        type_result = await self.db.execute(
            select(AIMetric.operation_type, func.count(AIMetric.metric_id))
            .where(and_(*filters))
            .group_by(AIMetric.operation_type)
        )
        operations_by_type = {row[0]: row[1] for row in type_result.all()}

        failed_operations = total_operations - successful_operations
        success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0.0

        return AIMetricsStats(
            total_operations=total_operations,
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            success_rate=success_rate,
            total_cost_usd=float(total_cost),
            avg_latency_ms=float(avg_latency),
            operations_by_provider=operations_by_provider,
            operations_by_type=operations_by_type,
        )

    async def get_vote_accuracy(
            self,
            since: Optional[datetime] = None,
            provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get accuracy statistics for AI voting.

        Args:
            since: Only include votes after this time (default: last 24 hours)
            provider: Filter by provider

        Returns:
            Dictionary with accuracy statistics
        """
        if since is None:
            since = datetime.now(UTC) - timedelta(days=1)

        # Build query filters
        filters = [
            AIMetric.created_at >= since,
            AIMetric.operation_type == "vote_generation",
            AIMetric.vote_correct.isnot(None),
        ]
        if provider:
            filters.append(AIMetric.provider == provider)

        # Get total votes
        total_result = await self.db.execute(
            select(func.count(AIMetric.metric_id)).where(and_(*filters))
        )
        total_votes = total_result.scalar() or 0

        # Get correct votes
        correct_result = await self.db.execute(
            select(func.count(AIMetric.metric_id)).where(
                and_(*filters, AIMetric.vote_correct == True)
            )
        )
        correct_votes = correct_result.scalar() or 0

        accuracy = (correct_votes / total_votes * 100) if total_votes > 0 else 0.0

        return {
            "total_votes": total_votes,
            "correct_votes": correct_votes,
            "incorrect_votes": total_votes - correct_votes,
            "accuracy_percent": accuracy,
        }


class MetricsTracker:
    """
    Context manager for tracking AI operation metrics.

    Usage:
        async with MetricsTracker(
            metrics_service,
            operation_type="copy_generation",
            provider="openai",
            model="gpt-5-nano",
        ) as tracker:
            result = await ai_operation()
            tracker.set_result(result, success=True)
    """

    def __init__(
            self,
            metrics_service: AIMetricsService,
            operation_type: str,
            provider: str,
            model: str,
    ):
        self.metrics_service = metrics_service
        self.operation_type = operation_type
        self.provider = provider
        self.model = model
        self.start_time = None
        self.success = False
        self.error_message = None
        self.prompt_length = None
        self.response_length = None
        self.validation_passed = None
        self.vote_correct = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Calculate latency
        latency_ms = None
        if self.start_time:
            latency_ms = int((time.time() - self.start_time) * 1000)

        # Record error if exception occurred
        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)

        # Record the metric
        await self.metrics_service.record_operation(
            operation_type=self.operation_type,
            provider=self.provider,
            model=self.model,
            success=self.success,
            latency_ms=latency_ms,
            error_message=self.error_message,
            prompt_length=self.prompt_length,
            response_length=self.response_length,
            validation_passed=self.validation_passed,
            vote_correct=self.vote_correct,
        )

        # Don't suppress exceptions
        return False

    def set_result(
            self,
            result: Any,
            success: bool = True,
            prompt_length: Optional[int] = None,
            response_length: Optional[int] = None,
            validation_passed: Optional[bool] = None,
            vote_correct: Optional[bool] = None,
    ):
        """Set result information for the tracked operation."""
        self.success = success
        self.prompt_length = prompt_length
        self.response_length = response_length
        self.validation_passed = validation_passed
        self.vote_correct = vote_correct
