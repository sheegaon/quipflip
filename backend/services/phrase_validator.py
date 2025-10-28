"""Phrase validation service with similarity checking."""
import os
import re
import logging
from difflib import SequenceMatcher
from typing import Set

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _parse_phrase(phrase: str) -> list[str]:
    """Parse phrase into individual words."""
    # Strip and normalize whitespace
    phrase = phrase.strip()
    phrase = re.sub(r'\s+', ' ', phrase)  # Replace multiple spaces with single space

    # Split into words
    words = phrase.split()
    return words


def _load_dictionary() -> Set[str]:
    """Load word list from file."""
    # Path relative to this file
    data_path = os.path.join(os.path.dirname(__file__), "../data/dictionary.txt")

    if not os.path.exists(data_path):
        logger.error(f"Dictionary file not found at: {data_path}")
        logger.error("Run: python scripts/download_dictionary.py")
        raise FileNotFoundError(f"Dictionary file not found: {data_path}")

    with open(data_path, "r") as f:
        return {line.strip().upper() for line in f if line.strip()}


class LightweightSimilarityCalculator:
    """Lightweight similarity calculator using TF-IDF and string matching."""
    
    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),  # Use unigrams and bigrams
            lowercase=True,
            stop_words=None,  # Don't remove stop words for short phrases
            max_features=1000   # Limit features for efficiency
        )
    
    def calculate_similarity(self, phrase1: str, phrase2: str) -> float:
        """
        Calculate similarity using a combination of TF-IDF cosine similarity,
        Jaccard similarity, and string similarity.
        """
        from sklearn.metrics.pairwise import cosine_similarity

        try:
            # Normalize phrases
            phrase1 = phrase1.strip().lower()
            phrase2 = phrase2.strip().lower()
            
            if phrase1 == phrase2:
                return 1.0
            
            # TF-IDF cosine similarity
            tfidf_matrix = self.vectorizer.fit_transform([phrase1, phrase2])
            tfidf_similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            # Jaccard similarity (word overlap)
            words1 = set(phrase1.split())
            words2 = set(phrase2.split())
            jaccard_similarity = len(words1 & words2) / len(words1 | words2) if words1 | words2 else 0
            
            # String similarity using difflib
            string_similarity = SequenceMatcher(None, phrase1, phrase2).ratio()
            
            # Weighted combination (can be tuned)
            combined_similarity = (
                0.5 * tfidf_similarity +
                0.3 * jaccard_similarity +
                0.2 * string_similarity
            )
            
            logger.debug(f"Similarity between '{phrase1}' and '{phrase2}': {combined_similarity:.4f}")
            return float(combined_similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            # If similarity check fails, be conservative and allow the phrase
            logger.warning("Similarity check failed, allowing phrase")
            return 0.0


class PhraseValidator:
    """Validates phrases against dictionary and similarity constraints."""

    # Common connecting words that are allowed even if short or not in dictionary
    CONNECTING_WORDS = {'A', 'I'}
    # Common 4+ letter words that are allowed to be reused
    COMMON_WORDS = {'THIS', 'THAT', 'YOUR', 'WITH', 'FROM', 'THEIR', 'THESE', 'THOSE', 'WHAT', 'WHEN', 'WHERE',
                    'WHICH', 'WHILE', 'BECAUSE'}

    # Significant words are those meeting the configured minimum length requirement
    # for overlap/similarity checks (default: 4 characters)

    def __init__(self):
        self.settings = get_settings()

        self.dictionary: Set[str] = _load_dictionary()
        logger.info(f"Loaded dictionary with {len(self.dictionary)} words")

        self._similarity_calculator = LightweightSimilarityCalculator()
        logger.info("Lightweight similarity calculator initialized")

    async def common_words(self) -> Set[str]:
        """Get set of common words allowed to be reused."""
        return self.COMMON_WORDS.copy()

    def calculate_similarity(self, phrase1: str, phrase2: str) -> float:
        """
        Calculate similarity between two phrases using configured method.

        Args:
            phrase1: First phrase
            phrase2: Second phrase

        Returns:
            Similarity score between 0.0 and 1.0
        """
        return self._similarity_calculator.calculate_similarity(phrase1, phrase2)

    def validate(self, phrase: str) -> tuple[bool, str]:
        """
        Validate a phrase for format and dictionary compliance.

        Args:
            phrase: The phrase to validate

        Returns:
            (is_valid, error_message)
        """
        # Normalize
        phrase = phrase.strip()

        # Check basic format
        if not phrase:
            return False, "Phrase cannot be empty"

        # Check minimum overall length (including spaces)
        if len(phrase) < 4:
            return False, "Phrase must be at least 4 characters"

        # Check overall length
        if len(phrase) > self.settings.phrase_max_length:
            return False, f"Phrase must be {self.settings.phrase_max_length} characters or less"

        # Check for valid characters (letters and spaces only)
        if not re.match(r'^[a-zA-Z\s]+$', phrase):
            return False, "Phrase must contain only letters A-Z and spaces"

        # Parse into words
        words = _parse_phrase(phrase)

        # Check word count
        if len(words) < self.settings.phrase_min_words:
            return False, f"Phrase must contain at least {self.settings.phrase_min_words} words"

        if len(words) > self.settings.phrase_max_words:
            return False, f"Phrase must contain at most {self.settings.phrase_max_words} words"

        # Validate each word
        for word in words:
            word_upper = word.upper()

            # Allow common connecting words regardless of length or dictionary
            if word_upper in self.CONNECTING_WORDS:
                continue

            # Check word length (skip for connecting words)
            if len(word) < self.settings.phrase_min_char_per_word:
                return False, f"Each word must be at least {self.settings.phrase_min_char_per_word} characters"

            if len(word) > self.settings.phrase_max_char_per_word:
                return False, f"Each word must be at most {self.settings.phrase_max_char_per_word} characters"

            # Check dictionary
            if word_upper not in self.dictionary:
                return False, f"Word '{word}' not in dictionary"

        return True, ""

    def _extract_significant_words(self, phrase: str) -> Set[str]:
        """Extract significant (length-limited) words from a phrase, excluding common words."""
        if not phrase:
            return set()

        words = re.findall(r"[a-zA-Z]+", phrase)
        min_length = self.settings.significant_word_min_length
        significant_words = set()

        for word in words:
            if len(word) >= min_length:
                word_upper = word.upper()
                # Exclude common words that are allowed to be reused
                if word_upper not in self.COMMON_WORDS:
                    significant_words.add(word.lower())

        return significant_words

    def _are_words_too_similar(self, word1: str, word2: str) -> bool:
        """Determine if two words are too similar based on sequence matching."""
        if word1 == word2:
            return True

        ratio = SequenceMatcher(None, word1, word2).ratio()
        return ratio >= self.settings.word_similarity_threshold

    def _check_significant_word_conflicts(self, phrase: str, comparisons: dict[str, str | None]) -> tuple[bool, str]:
        """Ensure phrase does not reuse or closely match significant words."""

        phrase_words = self._extract_significant_words(phrase)
        if not phrase_words:
            return True, ""

        for label, comparison_phrase in comparisons.items():
            if not comparison_phrase:
                continue

            comparison_words = self._extract_significant_words(comparison_phrase)
            if not comparison_words:
                continue

            overlap = phrase_words & comparison_words
            if overlap:
                word = next(iter(overlap)).upper()
                return False, f"Cannot reuse '{word}' from {label}"

            for phrase_word in phrase_words:
                for comparison_word in comparison_words:
                    if self._are_words_too_similar(phrase_word, comparison_word):
                        return False, f"Word '{phrase_word.upper()}' is too similar to a word from {label}"

        return True, ""

    async def validate_prompt_phrase(self, phrase: str, prompt_text: str | None) -> tuple[bool, str]:
        """Validate a prompt submission against the originating prompt text."""

        is_valid, error = self.validate(phrase)
        if not is_valid:
            return False, error

        comparisons = {"prompt": prompt_text}
        is_valid, error = self._check_significant_word_conflicts(phrase, comparisons)
        if not is_valid:
            return False, error

        return True, ""

    async def validate_copy(
        self,
        phrase: str,
        original_phrase: str,
        other_copy_phrase: str | None = None,
        prompt_text: str | None = None,
    ) -> tuple[bool, str]:
        """
        Validate a copy phrase (includes duplicate and similarity checks).

        Args:
            phrase: The copy phrase to validate
            original_phrase: The original prompt phrase
            other_copy_phrase: The other copy phrase (if already submitted)
            prompt_text: The prompt text associated with the original submission

        Returns:
            (is_valid, error_message)
        """
        # First validate format and dictionary
        is_valid, error = self.validate(phrase)
        if not is_valid:
            return False, error

        # Normalize for comparison
        phrase_normalized = phrase.strip().upper()
        original_normalized = original_phrase.strip().upper()

        # Check for exact duplicate of original
        if phrase_normalized == original_normalized:
            return False, "Cannot submit the same phrase as original"

        # Check for exact duplicate of other copy
        if other_copy_phrase:
            other_copy_normalized = other_copy_phrase.strip().upper()
            if phrase_normalized == other_copy_normalized:
                return False, "Cannot submit the same phrase as other copy"

        # Ensure no significant word overlap with original, other copies, or prompt text
        comparisons: dict[str, str | None] = {"original phrase": original_phrase}
        if other_copy_phrase:
            comparisons["other copy"] = other_copy_phrase
        if prompt_text:
            comparisons["prompt"] = prompt_text

        is_valid, error = self._check_significant_word_conflicts(phrase, comparisons)
        if not is_valid:
            return False, error

        # Check similarity to original phrase
        try:
            similarity_to_original = self.calculate_similarity(phrase, original_phrase)

            if similarity_to_original >= self.settings.similarity_threshold:
                return False, (
                    f"Phrase too similar to original "
                    f"(similarity: {similarity_to_original:.2f}, "
                    f"threshold: {self.settings.similarity_threshold})"
                )
        except Exception as e:
            logger.error(f"Similarity check to original failed: {e}")
            # If similarity check fails, be conservative and reject
            return False, "Unable to verify phrase uniqueness, please try a different phrase"

        # Check similarity to other copy if it exists
        if other_copy_phrase:
            try:
                similarity_to_other = self.calculate_similarity(phrase, other_copy_phrase)

                if similarity_to_other >= self.settings.similarity_threshold:
                    return False, (
                        f"Phrase too similar to other copy "
                        f"(similarity: {similarity_to_other:.2f}, "
                        f"threshold: {self.settings.similarity_threshold})"
                    )
            except Exception as e:
                logger.error(f"Similarity check to other copy failed: {e}")
                # If similarity check fails, be conservative and reject
                return False, "Unable to verify phrase uniqueness, please try a different phrase"

        return True, ""


# Singleton instance
_phrase_validator: PhraseValidator | None = None


def get_phrase_validator() -> PhraseValidator:
    """Get singleton phrase validator instance."""
    global _phrase_validator
    if _phrase_validator is None:
        _phrase_validator = PhraseValidator()
    return _phrase_validator
