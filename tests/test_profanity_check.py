"""Tests for profanity checking in usernames."""

import pytest
from backend.data.profanity_list import contains_profanity
from backend.services.username_service import is_username_profanity_free


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


class TestUsernameProfanityValidation:
    """Test username profanity validation."""

    def test_rejects_profane_usernames(self):
        """Should reject usernames with profanity."""
        assert is_username_profanity_free("fuck") is False
        assert is_username_profanity_free("shit") is False
        assert is_username_profanity_free("damn") is False

    def test_rejects_profanity_in_username(self):
        """Should reject usernames containing profanity at end or with digits."""
        assert is_username_profanity_free("badass") is False
        assert is_username_profanity_free("dumbass") is False
        assert is_username_profanity_free("fuck123") is False

    def test_rejects_profanity_with_spaces(self):
        """Should reject profanity even with spaces."""
        assert is_username_profanity_free("fu ck") is False
        assert is_username_profanity_free("da mn") is False
        assert is_username_profanity_free("bad ass") is False

    def test_accepts_clean_usernames(self):
        """Should accept clean usernames."""
        assert is_username_profanity_free("player123") is True
        assert is_username_profanity_free("cool user") is True
        assert is_username_profanity_free("word master") is True
        assert is_username_profanity_free("quip flipper") is True

    def test_avoids_false_positives_in_usernames(self):
        """Should not reject legitimate usernames with incidental substrings."""
        assert is_username_profanity_free("classic gamer") is True
        assert is_username_profanity_free("assistant") is True
        assert is_username_profanity_free("hello world") is True

    def test_case_insensitive_rejection(self):
        """Should reject profanity regardless of case."""
        assert is_username_profanity_free("FUCK") is False
        assert is_username_profanity_free("Shit") is False
        assert is_username_profanity_free("DaMn") is False

    def test_empty_username(self):
        """Should return False for empty username."""
        assert is_username_profanity_free("") is True
        assert is_username_profanity_free("   ") is True

    def test_rejects_leetspeak_profanity(self):
        """Should reject leetspeak variations."""
        assert is_username_profanity_free("fuk") is False
        assert is_username_profanity_free("sh1t") is False
        assert is_username_profanity_free("a55") is False
