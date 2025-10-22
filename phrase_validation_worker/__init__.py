"""Standalone phrase validation worker package."""

from .engine import PhraseValidator, get_phrase_validator

__all__ = [
    "PhraseValidator",
    "get_phrase_validator",
]
