"""Configuration for the standalone phrase validation worker service."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DICTIONARY_PATH = Path(__file__).resolve().parent / "data" / "dictionary.txt"


class Settings(BaseSettings):
    """Settings controlling phrase validation behaviour."""

    environment: str = Field(default="development", description="Runtime environment name")

    # Phrase limits
    phrase_min_words: int = Field(default=1, description="Minimum words in a valid phrase")
    phrase_max_words: int = Field(default=5, description="Maximum words in a valid phrase")
    phrase_max_length: int = Field(default=100, description="Maximum total characters in a phrase")
    phrase_min_char_per_word: int = Field(default=2, description="Minimum letters per non-connector word")
    phrase_max_char_per_word: int = Field(default=15, description="Maximum letters per word")
    significant_word_min_length: int = Field(default=4, description="Minimum length for words used in overlap checks")

    # Similarity configuration
    use_sentence_transformers: bool = Field(
        default=True,
        description="Whether to load the sentence-transformers model for similarity checks",
    )
    similarity_model: str = Field(
        default="paraphrase-MiniLM-L6-v2",
        description="Sentence-transformers model name",
    )
    similarity_threshold: float = Field(
        default=0.8, description="Maximum similarity allowed between copy phrases"
    )
    prompt_relevance_threshold: float = Field(
        default=0.1, description="Minimum similarity required between prompt and phrase"
    )
    word_similarity_threshold: float = Field(
        default=0.8, description="Threshold for individual word similarity rejection"
    )

    # Data paths
    dictionary_path: Path = Field(
        default=DEFAULT_DICTIONARY_PATH,
        description="Path to the dictionary file used for validation",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
