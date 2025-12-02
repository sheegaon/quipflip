"""Tests for profanity checking in usernames."""

import pytest

from backend.data.profanity_list import contains_profanity
from backend.services import is_username_allowed
from backend.services.ai.openai_api import OpenAIAPIError


class TestProfanityDetection:
    """Test profanity detection logic."""

    def test_detects_profanity(self):
        """Should detect profanity in text."""
        assert contains_profanity("fuck") is True
        assert contains_profanity("shit") is True
        assert contains_profanity("damn") is True

    def test_case_insensitive(self):
        """Should detect profanity regardless of case."""
        assert contains_profanity("FUCK") is True
        assert contains_profanity("Shit") is True
        assert contains_profanity("DaMn") is True

    def test_detects_profanity_at_end_of_words(self):
        """Should detect profanity at the end of compound words."""
        assert contains_profanity("badass") is True
        assert contains_profanity("dumbass") is True
        assert contains_profanity("classass") is True  # Multiple occurrences - catches the last one

    def test_detects_profanity_with_spaces(self):
        """Should detect profanity even with spaces."""
        assert contains_profanity("fu ck") is True
        assert contains_profanity("shi t") is True
        assert contains_profanity("da mn") is True

    def test_clean_text(self):
        """Should return False for clean text."""
        assert contains_profanity("hello") is False
        assert contains_profanity("world") is False
        assert contains_profanity("player") is False
        assert contains_profanity("username") is False

    def test_avoids_false_positives(self):
        """Should not flag legitimate words that contain profanity substrings."""
        assert contains_profanity("classic") is False  # contains "ass"
        assert contains_profanity("assistant") is False  # contains "ass"
        assert contains_profanity("shitake") is False  # contains "shit"
        assert contains_profanity("hello") is False  # contains "hell"
        assert contains_profanity("document") is False  # contains "cum"

    def test_empty_text(self):
        """Should handle empty text."""
        assert contains_profanity("") is False
        assert contains_profanity("   ") is False

    def test_detects_leetspeak(self):
        """Should detect leetspeak variations."""
        assert contains_profanity("fuk") is True
        assert contains_profanity("sh1t") is True
        assert contains_profanity("a55") is True

    def test_detects_profanity_with_digits(self):
        """Should detect profanity adjacent to numbers."""
        assert contains_profanity("fuck123") is True
        assert contains_profanity("123fuck") is True
        assert contains_profanity("shit456") is True


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
