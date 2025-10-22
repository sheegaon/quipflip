"""Standalone phrase validation worker package."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from .engine import PhraseValidator, get_phrase_validator

__all__ = ["PhraseValidator", "get_phrase_validator"]


def __getattr__(name: str) -> Any:
    """Lazily import heavy engine dependencies on first access."""

    if name in __all__:
        module = import_module(".engine", __name__)
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
