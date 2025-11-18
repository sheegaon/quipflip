"""Initial Reaction enums."""
from enum import Enum


class SetStatus(str, Enum):
    """Status of a backronym set."""

    OPEN = "open"
    VOTING = "voting"
    FINALIZED = "finalized"


class Mode(str, Enum):
    """Game mode for Initial Reaction."""

    STANDARD = "standard"
    RAPID = "rapid"
