"""Unit tests for the :mod:`backend.utils.cache` module."""
from uuid import UUID

import pytest

from backend.utils.cache import SimpleCache


def test_simple_cache_expires_items(monkeypatch):
    """Expired entries should be evicted on access."""

    from backend.utils import cache as cache_module

    current = 100.0

    def fake_time():
        return current

    monkeypatch.setattr(cache_module.time, "time", fake_time)

    cache = SimpleCache(default_ttl=5.0)

    cache.set("greeting", "hello")
    assert cache.get("greeting") == "hello"

    current = 200.0

    assert cache.get("greeting") is None


@pytest.mark.parametrize(
    "keys,should_remove",
    [
        ("dashboard:{pid}:summary", True),
        ("activity:{pid}:history", True),
        ("dashboard:someone_else", False),
    ],
)
def test_invalidate_player_data_removes_matching_keys(keys, should_remove):
    """Only cache entries containing the player id should be cleared."""

    player_id = UUID("12345678-1234-5678-1234-567812345678")
    cache = SimpleCache(default_ttl=60)

    formatted_key = keys.format(pid=player_id)
    cache.set(formatted_key, "value")

    cache.invalidate_player_data(player_id)

    expected = None if should_remove else "value"
    assert cache.get(formatted_key) == expected
