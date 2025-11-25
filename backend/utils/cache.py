"""Simple in-memory cache for frequently accessed data."""
import time
from typing import Any, Dict, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """
    A simple in-memory cache with TTL (time-to-live) support.
    
    This helps reduce database load for frequently accessed data like
    dashboard information that doesn't change frequently.
    """

    def __init__(self, default_ttl: float = 30.0):
        self.default_ttl = default_ttl
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 60.0  # Clean up every 60 seconds

    def _cleanup_expired(self):
        """Remove expired entries from cache."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = []
        for key, (value, expires_at) in self._cache.items():
            if current_time > expires_at:
                expired_keys.append(key)

        for key in expired_keys:
            self._cache.pop(key, None)

        self._last_cleanup = current_time

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        self._cleanup_expired()

        if key not in self._cache:
            return None

        value, expires_at = self._cache[key]
        if time.time() > expires_at:
            self._cache.pop(key, None)
            return None

        return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache with TTL."""
        if ttl is None:
            ttl = self.default_ttl

        expires_at = time.time() + ttl
        self._cache[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """Remove key from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def invalidate_player_data(self, player_id: UUID) -> None:
        """Invalidate all cached data for a specific player."""
        player_str = str(player_id)
        keys_to_delete = []

        for key in self._cache.keys():
            if player_str in key:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            self._cache.pop(key, None)

        if keys_to_delete:
            logger.debug(f"Invalidated {len(keys_to_delete)} cache entries for {player_id=}")


# Global cache instance
dashboard_cache = SimpleCache(default_ttl=15.0)  # Cache dashboard data for 15 seconds
