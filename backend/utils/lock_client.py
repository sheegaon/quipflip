"""Lock client abstraction - Redis or threading fallback."""
from typing import Optional
from threading import Lock as ThreadLock
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class LockClient:
    """Abstraction for distributed locks - uses Redis if available, else threading."""

    def __init__(self, redis_url: Optional[str] = None):
        self.backend = "memory"
        self._memory_locks: dict[str, ThreadLock] = {}
        self._memory_locks_lock = ThreadLock()

        if redis_url:
            try:
                import redis
                self.redis = redis.from_url(redis_url, decode_responses=True)
                self.redis.ping()
                self.backend = "redis"
                logger.info("Using Redis for distributed locks")
            except Exception as e:
                logger.warning(f"Redis not available, using threading locks: {e}")
        else:
            logger.info("Using threading locks (Redis URL not provided)")

    @contextmanager
    def lock(self, lock_name: str, timeout: int = 10):
        """
        Acquire lock, execute code, then release.

        Usage:
            with lock_client.lock("my_lock"):
                # critical section
                pass
        """
        if self.backend == "redis":
            lock = self.redis.lock(lock_name, timeout=timeout)
            acquired = lock.acquire(blocking=True, blocking_timeout=timeout)
            if not acquired:
                raise TimeoutError(f"Could not acquire lock: {lock_name}")
            try:
                yield
            finally:
                try:
                    lock.release()
                except Exception:
                    pass  # Lock may have expired
        else:
            # Get or create thread lock
            with self._memory_locks_lock:
                if lock_name not in self._memory_locks:
                    self._memory_locks[lock_name] = ThreadLock()
                lock = self._memory_locks[lock_name]

            # Acquire lock
            acquired = lock.acquire(blocking=True, timeout=timeout)
            if not acquired:
                raise TimeoutError(f"Could not acquire lock: {lock_name}")
            try:
                yield
            finally:
                lock.release()
