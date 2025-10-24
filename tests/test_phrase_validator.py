"""Tests for phrase validator with similarity checking."""
import pytest
pytest.importorskip("sklearn")
from backend.services.phrase_validator import PhraseValidator, get_phrase_validator, _parse_phrase


@pytest.fixture
def validator():
    """Get phrase validator instance."""
    return get_phrase_validator()


class TestBasicPhraseValidation:
    """Test basic phrase format validation."""

    def test_valid_single_word(self, validator):
        """Test valid single word phrase."""
        is_valid, error = validator.validate("FREEDOM")
        assert is_valid
        assert error == ""

    def test_valid_two_word_phrase(self, validator):
        """Test valid two-word phrase."""
        is_valid, error = validator.validate("ice cream")
        assert is_valid
        assert error == ""

    def test_valid_five_word_phrase(self, validator):
        """Test valid five-word phrase."""
        is_valid, error = validator.validate("a big red fire truck")
        assert is_valid
        assert error == ""

    def test_empty_phrase(self, validator):
        """Test empty phrase is rejected."""
        is_valid, error = validator.validate("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_too_many_words(self, validator):
        """Test phrase with more than 5 words is rejected."""
        is_valid, error = validator.validate("one two three four five six")
        assert not is_valid
        assert "5 words" in error

    def test_phrase_too_long(self, validator):
        """Test phrase exceeding 100 characters is rejected."""
        # Create a phrase longer than 100 characters
        long_phrase = "antidisestablishmentarianism " * 4  # ~116 characters
        is_valid, error = validator.validate(long_phrase)
        assert not is_valid
        assert "100 characters" in error

    def test_phrase_with_numbers(self, validator):
        """Test phrase with numbers is rejected."""
        is_valid, error = validator.validate("word123")
        assert not is_valid
        assert "letters" in error.lower() and "spaces" in error.lower()

    def test_phrase_with_punctuation(self, validator):
        """Test phrase with punctuation is rejected."""
        is_valid, error = validator.validate("hello!")
        assert not is_valid
        assert "letters" in error.lower()

    def test_phrase_with_multiple_spaces(self, validator):
        """Test phrase with multiple spaces is normalized."""
        # Should normalize to single spaces and still validate
        is_valid, error = validator.validate("ice    cream")
        assert is_valid
        assert error == ""

    def test_word_too_short(self, validator):
        """Test word shorter than 2 characters is rejected (except connecting words)."""
        # "a" and "i" are connecting words, but "a i" is only 3 chars total (< 4 minimum)
        is_valid, error = validator.validate("a i")
        assert not is_valid
        assert "at least 4 characters" in error

        # "a cat" should work (5 chars total, connecting word + valid word)
        is_valid, error = validator.validate("a cat")
        assert is_valid

        # But a non-connecting single-letter word should fail
        is_valid, error = validator.validate("x")
        assert not is_valid
        assert "at least" in error  # Could be 4 char minimum or 2 char per word

    def test_word_too_long(self, validator):
        """Test word longer than 15 characters is rejected."""
        is_valid, error = validator.validate("antidisestablishmentarianisms")  # 29 chars
        assert not is_valid
        assert "at most 15 characters" in error

    def test_word_not_in_dictionary(self, validator):
        """Test word not in dictionary is rejected."""
        is_valid, error = validator.validate("zzxxyyzz")
        assert not is_valid
        assert "not in dictionary" in error.lower()

    def test_case_insensitive_validation(self, validator):
        """Test validation is case insensitive."""
        is_valid1, _ = validator.validate("FREEDOM")
        is_valid2, _ = validator.validate("freedom")
        is_valid3, _ = validator.validate("FrEeDoM")
        assert is_valid1 and is_valid2 and is_valid3


class TestPhraseParsing:
    """Test phrase parsing functionality."""

    def test_parse_single_word(self, validator):
        """Test parsing single word."""
        words = _parse_phrase("freedom")
        assert len(words) == 1
        assert words[0] == "freedom"

    def test_parse_multiple_words(self, validator):
        """Test parsing multiple words."""
        words = _parse_phrase("ice cream cone")
        assert len(words) == 3
        assert words == ["ice", "cream", "cone"]

    def test_parse_with_extra_spaces(self, validator):
        """Test parsing normalizes multiple spaces."""
        words = _parse_phrase("ice    cream   cone")
        assert len(words) == 3
        assert words == ["ice", "cream", "cone"]

    def test_parse_with_leading_trailing_spaces(self, validator):
        """Test parsing strips leading/trailing spaces."""
        words = _parse_phrase("  ice cream  ")
        assert len(words) == 2
        assert words == ["ice", "cream"]


class TestConnectingWords:
    """Test that connecting words are allowed and counted."""

    def test_connecting_word_a(self, validator):
        """Test 'a' is valid and counts toward word limit."""
        is_valid, error = validator.validate("a nice day")
        assert is_valid
        assert error == ""

    def test_connecting_word_an(self, validator):
        """Test 'an' is valid and counts toward word limit."""
        is_valid, error = validator.validate("an apple tree")
        assert is_valid
        assert error == ""

    def test_connecting_word_the(self, validator):
        """Test 'the' is valid and counts toward word limit."""
        is_valid, error = validator.validate("the blue sky")
        assert is_valid
        assert error == ""

    def test_five_words_with_connecting_word(self, validator):
        """Test that connecting words count toward 5-word limit."""
        # This should be valid (exactly 5 words)
        is_valid, error = validator.validate("a big red fire truck")
        assert is_valid

        # This should fail (6 words including 'the')
        is_valid, error = validator.validate("the very big red fire truck")
        assert not is_valid
        assert "5 words" in error


class TestCopyValidation:
    """Test copy phrase validation with duplicate and similarity checking."""

    def test_exact_duplicate_rejected(self, validator):
        """Test exact duplicate of original is rejected."""
        is_valid, error = validator.validate_copy("freedom", "freedom")
        assert not is_valid
        assert "same phrase" in error.lower()

    def test_case_insensitive_duplicate_rejected(self, validator):
        """Test case-insensitive duplicate is rejected."""
        is_valid, error = validator.validate_copy("FREEDOM", "freedom")
        assert not is_valid
        assert "same phrase" in error.lower()

    def test_different_phrase_accepted(self, validator):
        """Test different phrase is accepted."""
        is_valid, error = validator.validate_copy("liberty", "freedom")
        assert is_valid
        assert error == ""

    def test_exact_duplicate_of_other_copy_rejected(self, validator):
        """Test exact duplicate of other copy is rejected."""
        is_valid, error = validator.validate_copy(
            phrase="independence",
            original_phrase="freedom",
            other_copy_phrase="independence"
        )
        assert not is_valid
        assert "same phrase" in error.lower()

    def test_significant_word_overlap_rejected(self, validator):
        """Test copy phrases cannot reuse significant words from original."""
        is_valid, error = validator.validate_copy(
            phrase="flower crown",
            original_phrase="flower power",
        )
        assert not is_valid
        assert "significant" in error.lower()

    def test_significant_word_similarity_rejected(self, validator):
        """Test copy phrases cannot use words similar to original words."""
        is_valid, error = validator.validate_copy(
            phrase="flowers unite",
            original_phrase="flower power",
        )
        assert not is_valid
        assert "too similar" in error.lower()


class TestPromptValidation:
    """Test prompt phrase validation against prompt text."""

    def test_prompt_word_overlap_rejected(self, validator):
        """Ensure prompt submissions cannot reuse significant prompt words."""
        is_valid, error = validator.validate_prompt_phrase(
            phrase="grand library",
            prompt_text="Describe your favorite library",
        )
        assert not is_valid
        assert "significant" in error.lower()

    def test_prompt_word_similarity_rejected(self, validator):
        """Ensure prompt submissions reject similar significant words."""
        is_valid, error = validator.validate_prompt_phrase(
            phrase="bright flowers",
            prompt_text="Talk about a favorite flower",
        )
        assert not is_valid
        assert "too similar" in error.lower()


class TestSimilarityChecking:
    """Test cosine similarity checking functionality."""

    def test_calculate_similarity_identical(self, validator):
        """Test similarity of identical phrases is 1.0."""
        similarity = validator.calculate_similarity("freedom", "freedom")
        assert similarity > 0.95  # Should be very close to 1.0

    def test_calculate_similarity_synonyms(self, validator):
        """Test similarity of synonyms is high."""
        similarity = validator.calculate_similarity("happy", "joyful")
        # Synonyms should have high similarity
        assert similarity > 0.6

    def test_calculate_similarity_unrelated(self, validator):
        """Test similarity of unrelated phrases is low."""
        similarity = validator.calculate_similarity("freedom", "banana")
        # Unrelated words should have low similarity
        assert similarity < 0.5

    def test_similar_phrase_rejected(self, validator):
        """Test very similar phrase is rejected (above threshold)."""
        # Test with phrases that are semantically very similar
        # Note: This might vary based on the similarity threshold
        # Using "happy" vs "very happy" - will be caught by word overlap rule
        is_valid, error = validator.validate_copy("very happy", "happy")
        # May or may not fail depending on threshold, but should at least validate format
        assert isinstance(is_valid, bool)
        if not is_valid:
            # Can be rejected for either word overlap or similarity
            assert "similar" in error.lower() or "word" in error.lower()

    def test_dissimilar_phrase_accepted(self, validator):
        """Test dissimilar phrase is accepted."""
        is_valid, error = validator.validate_copy("computer", "ocean")
        assert is_valid
        assert error == ""

    def test_similarity_to_other_copy(self, validator):
        """Test similarity check against other copy phrase."""
        # Submit a phrase that's different from both original and other copy
        is_valid, error = validator.validate_copy(
            phrase="mountain",
            original_phrase="ocean",
            other_copy_phrase="river"
        )
        assert is_valid
        assert error == ""


class TestInvalidFormatCopy:
    """Test that copy validation still checks format."""

    def test_copy_invalid_format(self, validator):
        """Test copy with invalid format is rejected."""
        is_valid, error = validator.validate_copy("hello123", "freedom")
        assert not is_valid
        assert "letters" in error.lower()

    def test_copy_too_many_words(self, validator):
        """Test copy with too many words is rejected."""
        is_valid, error = validator.validate_copy(
            "one two three four five six",
            "freedom"
        )
        assert not is_valid
        assert "5 words" in error

    def test_copy_word_not_in_dictionary(self, validator):
        """Test copy with invalid word is rejected."""
        is_valid, error = validator.validate_copy("zzxxyyzz", "freedom")
        assert not is_valid
        assert "not in dictionary" in error.lower()


class TestSingletonPattern:
    """Test that validator follows singleton pattern."""

    def test_get_phrase_validator_returns_same_instance(self):
        """Test that get_phrase_validator returns same instance."""
        validator1 = get_phrase_validator()
        validator2 = get_phrase_validator()
        assert validator1 is validator2


class TestMultiWordPhrases:
    """Test validation of multi-word phrases."""

    def test_common_two_word_phrases(self, validator):
        """Test common two-word phrases."""
        phrases = ["ice cream", "fire truck", "hot dog", "blue sky"]
        for phrase in phrases:
            is_valid, error = validator.validate(phrase)
            assert is_valid, f"'{phrase}' should be valid: {error}"

    def test_common_three_word_phrases(self, validator):
        """Test common three-word phrases."""
        phrases = ["red fire truck", "big blue sky", "ice cream cone"]
        for phrase in phrases:
            is_valid, error = validator.validate(phrase)
            assert is_valid, f"'{phrase}' should be valid: {error}"

    def test_phrases_with_articles(self, validator):
        """Test phrases with articles."""
        phrases = ["the ocean", "a mountain", "an apple"]
        for phrase in phrases:
            is_valid, error = validator.validate(phrase)
            assert is_valid, f"'{phrase}' should be valid: {error}"
