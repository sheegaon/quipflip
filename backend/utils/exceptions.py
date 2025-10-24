"""Custom exceptions for the application."""


class QuipflipException(Exception):
    """Base exception for Quipflip application."""
    pass


class InsufficientBalanceError(QuipflipException):
    """Player does not have enough balance for operation."""
    pass


class AlreadyInRoundError(QuipflipException):
    """Player is already in an active round."""
    pass


class RoundNotFoundError(QuipflipException):
    """Round does not exist or player doesn't have access."""
    pass


class RoundExpiredError(QuipflipException):
    """Round has expired past grace period."""
    pass


class InvalidWordError(QuipflipException):
    """Word is invalid (not in dictionary, wrong format, etc.)."""
    pass


class InvalidPhraseError(QuipflipException):
    """Phrase is invalid (format, length, word count, etc.)."""
    pass


class DuplicateWordError(QuipflipException):
    """Copy word matches original phrase."""
    pass


class DuplicatePhraseError(QuipflipException):
    """Copy phrase matches original phrase."""
    pass


class PhraseTooSimilarError(QuipflipException):
    """Copy phrase is too similar to original or other copy phrase."""
    pass


class MaxOutstandingPromptsError(QuipflipException):
    """Player has reached maximum outstanding prompts."""
    pass


class NoPromptsAvailableError(QuipflipException):
    """No prompts waiting in queue for copy round."""
    pass


class NoPhrasesetsAvailableError(QuipflipException):
    """No phrasesets waiting in queue for voting."""
    pass


class AlreadyVotedError(QuipflipException):
    """Player has already voted on this phraseset."""
    pass


class DailyBonusNotAvailableError(QuipflipException):
    """Daily bonus has already been claimed today."""
    pass


class SelfVotingError(QuipflipException):
    """Cannot vote on own phraseset."""
    pass
