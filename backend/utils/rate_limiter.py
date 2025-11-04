"""Rate limiting utilities with Redis or in-memory storage."""
from __future__ import annotations

import asyncio
import logging
import math
import time
from collections import deque
from threading import Lock
from typing import Optional, Tuple


logger = logging.getLogger(__name__)


class RateLimiter:
    """Track request counts in a rolling window per identifier."""

    def __init__(self, redis_url: Optional[str] = None, namespace: str = "rate_limit"):
        self.namespace = namespace
        self.backend = "memory"
        self._memory_lock = Lock()
        self._memory_hits: dict[str, deque[float]] = {}
        self._tracked_keys: set[str] = set()
        self._tracked_keys_lock = Lock()

        if redis_url:
            try:
                import redis  # type: ignore

                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                self.backend = "redis"
                logger.info("Using Redis for rate limiting")
            except Exception as exc:  # pragma: no cover - fallback path
                logger.warning(
                    f"Redis unavailable for rate limiting, using in-memory fallback: {exc}",
                )
                self.redis = None
        else:
            logger.info("Using in-memory rate limiting (Redis URL not provided)")

    def _full_key(self, identifier: str) -> str:
        return f"{self.namespace}:{identifier}"

    async def check(
        self, identifier: str, limit: int, window_seconds: int
    ) -> Tuple[bool, Optional[int]]:
        """Check whether an identifier is within the allowed rate limit."""

        if limit <= 0:
            return True, None

        key = self._full_key(identifier)

        if self.backend == "redis" and getattr(self, "redis", None) is not None:
            loop = asyncio.get_running_loop()

            def _redis_update() -> Tuple[int, int]:
                count = self.redis.incr(key)
                if count == 1:
                    self.redis.expire(key, window_seconds)
                ttl = self.redis.ttl(key)
                return count, ttl

            count, ttl = await loop.run_in_executor(None, _redis_update)
            retry_after = None
            if count > limit:
                retry_after = window_seconds if ttl is None or ttl < 0 else ttl
            with self._tracked_keys_lock:
                self._tracked_keys.add(key)
            return count <= limit, retry_after

        now = time.monotonic()
        cutoff = now - window_seconds
        retry_after = None

        with self._memory_lock:
            bucket = self._memory_hits.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            allowed = len(bucket) < limit
            if allowed:
                bucket.append(now)
            else:
                earliest = bucket[0]
                elapsed = now - earliest
                remaining = max(0.0, window_seconds - elapsed)
                retry_after = math.ceil(remaining)

            with self._tracked_keys_lock:
                self._tracked_keys.add(key)

            return allowed, retry_after

    def reset(self, prefix: Optional[str] = None) -> None:
        """Reset tracked counters. Used primarily for testing."""

        full_prefix = self._full_key(prefix) if prefix else None

        if self.backend == "redis" and getattr(self, "redis", None) is not None:
            with self._tracked_keys_lock:
                if full_prefix:
                    keys = [k for k in self._tracked_keys if k.startswith(full_prefix)]
                else:
                    keys = list(self._tracked_keys)

            if keys:
                self.redis.delete(*keys)

            with self._tracked_keys_lock:
                if full_prefix:
                    for key in keys:
                        self._tracked_keys.discard(key)
                else:
                    self._tracked_keys.clear()
            return

        with self._memory_lock:
            if full_prefix:
                to_remove = [k for k in self._memory_hits if k.startswith(full_prefix)]
                for key in to_remove:
                    self._memory_hits.pop(key, None)
                with self._tracked_keys_lock:
                    for key in list(self._tracked_keys):
                        if key.startswith(full_prefix):
                            self._tracked_keys.remove(key)
            else:
                self._memory_hits.clear()
                with self._tracked_keys_lock:
                    self._tracked_keys.clear()
