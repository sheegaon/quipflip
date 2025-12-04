"""Tests for profanity checking in usernames."""

import pytest

from backend.services import is_username_allowed
from backend.services.ai.openai_api import OpenAIAPIError


class TestUsernameModeration:
    """Test moderation-aware username validation."""

    @pytest.mark.asyncio
    async def test_allows_when_moderation_passes(self, monkeypatch):
        """Should allow usernames when moderation approves."""

        async def passing_moderation(_: str, timeout: int = 10) -> bool:  # noqa: ARG001
            return True

        monkeypatch.setattr(
            "backend.services.username_service.moderate_text", passing_moderation
        )

        assert await is_username_allowed("friendly user") is True

    @pytest.mark.asyncio
    async def test_rejects_when_moderation_flags(self, monkeypatch):
        """Should reject usernames that moderation marks as flagged."""

        async def fake_moderation(_: str, timeout: int = 10) -> bool:  # noqa: ARG001
            return False

        monkeypatch.setattr(
            "backend.services.username_service.moderate_text", fake_moderation
        )

        assert await is_username_allowed("harmless") is False

    @pytest.mark.asyncio
    async def test_errors_when_moderation_unavailable(self, monkeypatch):
        """Should surface moderation failures when moderation cannot run."""

        async def broken_moderation(_: str, timeout: int = 10) -> bool:  # noqa: ARG001
            raise OpenAIAPIError("network down")

        monkeypatch.setattr(
            "backend.services.username_service.moderate_text", broken_moderation
        )

        with pytest.raises(OpenAIAPIError):
            await is_username_allowed("friendly user")
