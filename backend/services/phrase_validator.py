"""Phrase validation service with similarity checking."""
import asyncio
import os
import re
import math
import logging
from difflib import SequenceMatcher
from typing import Set, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.phrase_embedding import PhraseEmbedding
from backend.services.tl.matching_service import TLMatchingService

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


class PhraseValidator:
    """Validates phrases against dictionary and similarity constraints."""

    # Common words that are allowed to be reused but don't count as significant
    COMMON_WORDS = {
        'A', 'I',
        'AN', 'IS', 'HE', 'IT', 'IF', 'IN', 'ON', 'AT', 'TO', 'OF', 'AS', 'OR', 'ME', 'MY', 'WE', 'US',
        'THE', 'SHE', 'HER', 'HIM', 'HIS', 'HERS', 'ITS', 'AND', 'BUT', 'FOR', 'NOR', 'YOU', 'ALL',
        'WHO', 'WHAT', 'WHEN', 'WHERE', 'WHY', 'HOW',
        'THIS', 'THAT', 'THEIR', 'THESE', 'THOSE', 'THEY',
        'YOUR', 'WITH', 'FROM', 'THEN', 'WHICH', 'WHILE'}

    # Significant words are those meeting the configured minimum length requirement
    # for overlap/similarity checks (default: 4 characters)

    def __init__(self):
        self.settings = get_settings()

        # Lazy-loaded matching service - only initialized when needed
        self._matching: Optional[TLMatchingService] = None

        self.dictionary: Set[str] = _load_dictionary()
        logger.info(f"Loaded dictionary with {len(self.dictionary)} words")

        logger.info(f"Using OpenAI embedding model: {self.settings.embedding_model}")

    @property
    def matching(self) -> TLMatchingService:
        """Lazy-load the TLMatchingService only when embeddings are needed."""
        if self._matching is None:
            self._matching = TLMatchingService()
        return self._matching

    def common_words(self) -> Set[str]:
        """Get set of common words allowed to be reused."""
        return self.COMMON_WORDS.copy()

    async def _get_cached_embedding(self, phrase: str, session: AsyncSession) -> list[float] | None:
        """Return a cached embedding for the phrase if it exists."""

        normalized_phrase = phrase.strip().lower()
        stmt = select(PhraseEmbedding).where(
            PhraseEmbedding.phrase == normalized_phrase,
            PhraseEmbedding.model == self.settings.embedding_model,
        )

        result = await session.execute(stmt)
        cached = result.scalar_one_or_none()
        if cached:
            return cached.embedding

        return None

    @staticmethod
    def _cosine_similarity(vector1: list[float], vector2: list[float]) -> float:
        """Compute cosine similarity between two vectors."""

        dot_product = sum(a * b for a, b in zip(vector1, vector2))
        norm1 = math.sqrt(sum(a * a for a in vector1))
        norm2 = math.sqrt(sum(b * b for b in vector2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def calculate_similarity(self, phrase1: str, phrase2: str) -> float:
        """Calculate similarity between two phrases using OpenAI embeddings with caching."""

        phrase1_normalized = phrase1.strip().lower()
        phrase2_normalized = phrase2.strip().lower()

        if not phrase1_normalized or not phrase2_normalized:
            return 0.0

        try:
            embedding1, embedding2 = await asyncio.gather(
                self._get_or_create_embedding(phrase1_normalized),
                self._get_or_create_embedding(phrase2_normalized),
            )

            similarity = self._cosine_similarity(embedding1, embedding2)
            logger.info(f"Similarity between '{phrase1_normalized}' and '{phrase2_normalized}': {similarity:.4f}")
            return float(similarity)
        except Exception as exc:
            logger.error(f"Unexpected error calculating similarity: {exc}")
            return 0.0

    async def _get_or_create_embedding(self, phrase: str) -> list[float]:
        """Return a cached embedding or generate and store a new one."""

        async with AsyncSessionLocal() as session:
            embedding = await self._get_cached_embedding(phrase, session)

            if embedding is None:
                logger.info(
                    f"Requesting embedding via matching service for '{phrase=}' using {self.settings.embedding_model=}")
                embedding = await self.matching.generate_embedding(phrase, db=session)

            return embedding

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

        # Check for valid characters (letters, spaces, and apostrophes)
        if not re.match(r"^[a-zA-Z\s']+$", phrase):
            return False, "Phrase must contain only letters A-Z, spaces, and apostrophes"

        # Parse into words
        words = _parse_phrase(phrase)

        # Check word count
        if len(words) < self.settings.phrase_min_words:
            return False, f"Phrase must contain at least {self.settings.phrase_min_words} words"

        if len(words) > self.settings.phrase_max_words:
            return False, f"Phrase must contain at most {self.settings.phrase_max_words} words"

        # Validate each word
        has_significant = False
        for word in words:
            cleaned_word = word.replace("'", "")
            word_upper = word.upper()

            # Allow common words regardless of length or dictionary
            if word_upper in self.COMMON_WORDS:
                continue

            # Check word length (skip for connecting words)
            if len(cleaned_word) < self.settings.phrase_min_char_per_word:
                return False, (f"Words must be at least {self.settings.phrase_min_char_per_word} characters "
                               f"(excluding 'A' and 'I')")

            if len(cleaned_word) > self.settings.phrase_max_char_per_word:
                return False, f"Each word must be at most {self.settings.phrase_max_char_per_word} characters"

            # Check dictionary (accept both contracted and stripped forms)
            dict_candidates = {word_upper, cleaned_word.upper()}

            if not any(candidate in self.dictionary for candidate in dict_candidates):
                # As a fallback, allow common inflections whose stem exists in the dictionary
                stemmed = self._remove_common_endings(cleaned_word.upper())
                if stemmed not in self.dictionary:
                    return False, f"Word '{word}' not in dictionary"

            has_significant = True

        if not has_significant:
            return False, "Phrase must contain at least one significant word"

        return True, ""

    def _extract_significant_words(self, phrase: str) -> Set[str]:
        """Extract significant (length-limited, uncommon) words from a phrase."""
        if not phrase:
            return set()

        words = re.findall(r"[a-zA-Z']+", phrase)
        min_length = self.settings.significant_word_min_length
        significant_words = set()

        for word in words:
            cleaned_word = word.replace("'", "")
            if len(cleaned_word) >= min_length:
                word_upper = cleaned_word.upper()
                # Exclude common words that are allowed to be reused
                if word_upper not in self.COMMON_WORDS:
                    significant_words.add(word.lower())

        return significant_words

    def _remove_common_endings(self, word: str) -> str:
        """Remove common English word endings for basic stemming."""
        endings = ['ING', 'ED', 'S', 'ES', 'LY', 'ER', 'EST', 'ION', 'TION', 'NESS', 'MENT', 'FUL', 'ABLE', 'IBLE']
        stemmed_word = word
        while True:
            original_word = stemmed_word
            for ending in endings:
                if (stemmed_word.endswith(ending) and len(stemmed_word) > len(ending) + 2 and
                        stemmed_word[:-len(ending)] in self.dictionary):
                    stemmed_word = stemmed_word[:-len(ending)]
                    break  # Restart the inner loop with the new stem
            if stemmed_word == original_word:
                # No ending was stripped in a full pass, so we're done
                break
        return stemmed_word

    def _are_words_too_similar(self, word1: str, word2: str) -> bool:
        """Determine if two words are too similar based on sequence matching."""
        # Remove common endings for basic stemming
        stem1 = self._remove_common_endings(word1)
        stem2 = self._remove_common_endings(word2)

        if stem1 == stem2:
            return True

        ratio = SequenceMatcher(None, stem1, stem2).ratio()
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
                        return False, f"Word '{phrase_word}' is too similar to the word {comparison_word} from {label}"

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

    async def validate_copy(self, phrase: str, original: str, other_copy: str | None = None, prompt: str | None = None
                            ) -> tuple[bool, str]:
        """
        Validate a copy phrase (includes duplicate and similarity checks).

        Args:
            phrase: The copy phrase to validate
            original: The original prompt phrase
            other_copy: The other copy phrase (if already submitted)
            prompt: The prompt text associated with the original submission

        Returns:
            (is_valid, error_message)
        """
        # First validate format and dictionary
        is_valid, error = self.validate(phrase)
        if not is_valid:
            return False, error

        # Normalize for comparison
        phrase_normalized = phrase.strip().upper()
        original_normalized = original.strip().upper()

        # Check for exact duplicate of original
        if phrase_normalized == original_normalized:
            return False, "Cannot submit the same phrase as original"

        # Check for exact duplicate of other copy
        if other_copy:
            other_copy_normalized = other_copy.strip().upper()
            if phrase_normalized == other_copy_normalized:
                return False, "Cannot submit the same phrase as other copy"

        # Ensure no significant word overlap with original, other copies, or prompt text
        comparisons: dict[str, str | None] = {"original phrase": original}
        if other_copy:
            comparisons["other copy"] = other_copy
        if prompt:
            comparisons["prompt"] = prompt

        is_valid, error = self._check_significant_word_conflicts(phrase, comparisons)
        if not is_valid:
            return False, error

        # Check similarity to original phrase
        try:
            similarity_to_original = await self.calculate_similarity(phrase, original)

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
        if other_copy:
            try:
                similarity_to_other = await self.calculate_similarity(phrase, other_copy)

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

    def validate_backronym_words(self, words: list[str], target_letter_count: int) -> tuple[bool, str]:
        """
        Validate backronym words for Initial Reaction game.

        Args:
            words: List of words forming the backronym
            target_letter_count: Expected number of words (should match word length)

        Returns:
            (is_valid, error_message)
        """
        # Check word count matches target
        if len(words) != target_letter_count:
            return (
                False,
                f"Expected {target_letter_count} words, got {len(words)}"
            )

        # Validate each word
        for i, word in enumerate(words):
            word_upper = word.strip().upper()

            # Check word length (2-15 characters)
            if not (2 <= len(word_upper) <= 15):
                return (
                    False,
                    f"Word '{word}' is {len(word_upper)} characters. "
                    f"Must be 2-15 characters."
                )

            # Check word contains only letters
            if not word_upper.isalpha():
                return (
                    False,
                    f"Word '{word}' contains non-letter characters"
                )

            # Check word exists in dictionary
            if word_upper not in self.dictionary:
                return (
                    False,
                    f"Word '{word}' is not in the dictionary"
                )

        logger.info(f"Backronym validated: {' '.join(words)}")
        return True, ""


# Singleton instance
_phrase_validator: PhraseValidator | None = None


def get_phrase_validator() -> PhraseValidator:
    """Get singleton phrase validator instance."""
    global _phrase_validator
    if _phrase_validator is None:
        _phrase_validator = PhraseValidator()
    return _phrase_validator
