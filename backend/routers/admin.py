"""Admin routes for administrative operations."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.config import get_settings
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.services.phrase_validator import get_phrase_validator
from typing import Annotated, Optional

router = APIRouter(prefix="/admin", tags=["admin"])


class ValidatePasswordRequest(BaseModel):
    """Request model for admin password validation."""
    password: str


class ValidatePasswordResponse(BaseModel):
    """Response model for admin password validation."""
    valid: bool


class TestPhraseValidationRequest(BaseModel):
    """Request model for testing phrase validation."""
    phrase: str
    validation_type: str  # "basic", "prompt", or "copy"
    prompt_text: Optional[str] = None
    original_phrase: Optional[str] = None
    other_copy_phrase: Optional[str] = None


class TestPhraseValidationResponse(BaseModel):
    """Response model for phrase validation testing."""
    is_valid: bool
    error_message: Optional[str] = None

    # Basic validation details
    word_count: int
    phrase_length: int
    words: list[str]

    # Similarity scores (when applicable)
    prompt_relevance_score: Optional[float] = None
    similarity_to_original: Optional[float] = None
    similarity_to_other_copy: Optional[float] = None

    # Thresholds from config
    prompt_relevance_threshold: Optional[float] = None
    similarity_threshold: Optional[float] = None

    # Detailed validation checks
    format_check_passed: bool
    dictionary_check_passed: bool
    word_conflicts: list[str] = []


class GameConfigResponse(BaseModel):
    """Response model for game configuration."""
    # Game Constants
    starting_balance: int
    daily_bonus_amount: int
    prompt_cost: int
    copy_cost_normal: int
    copy_cost_discount: int
    vote_cost: int
    vote_payout_correct: int
    abandoned_penalty: int
    prize_pool_base: int
    max_outstanding_quips: int
    copy_discount_threshold: int

    # Timing
    prompt_round_seconds: int
    copy_round_seconds: int
    vote_round_seconds: int
    grace_period_seconds: int

    # Vote finalization thresholds
    vote_max_votes: int
    vote_closing_threshold: int
    vote_closing_window_seconds: int
    vote_minimum_threshold: int
    vote_minimum_window_seconds: int

    # Phrase Validation
    phrase_min_words: int
    phrase_max_words: int
    phrase_max_length: int
    phrase_min_char_per_word: int
    phrase_max_char_per_word: int
    significant_word_min_length: int

    # AI Service
    ai_provider: str
    ai_openai_model: str
    ai_gemini_model: str
    ai_timeout_seconds: int
    ai_backup_delay_minutes: int


@router.get("/config", response_model=GameConfigResponse)
async def get_game_config(
    player: Annotated[Player, Depends(get_current_player)]
) -> GameConfigResponse:
    """
    Get current game configuration values.

    Args:
        player: Current authenticated player (required to access this endpoint)

    Returns:
        GameConfigResponse with all configuration values
    """
    settings = get_settings()

    return GameConfigResponse(
        # Game Constants
        starting_balance=settings.starting_balance,
        daily_bonus_amount=settings.daily_bonus_amount,
        prompt_cost=settings.prompt_cost,
        copy_cost_normal=settings.copy_cost_normal,
        copy_cost_discount=settings.copy_cost_discount,
        vote_cost=settings.vote_cost,
        vote_payout_correct=settings.vote_payout_correct,
        abandoned_penalty=settings.abandoned_penalty,
        prize_pool_base=settings.prize_pool_base,
        max_outstanding_quips=settings.max_outstanding_quips,
        copy_discount_threshold=settings.copy_discount_threshold,

        # Timing
        prompt_round_seconds=settings.prompt_round_seconds,
        copy_round_seconds=settings.copy_round_seconds,
        vote_round_seconds=settings.vote_round_seconds,
        grace_period_seconds=settings.grace_period_seconds,

        # Vote finalization
        vote_max_votes=settings.vote_max_votes,
        vote_closing_threshold=settings.vote_closing_threshold,
        vote_closing_window_seconds=settings.vote_closing_window_seconds,
        vote_minimum_threshold=settings.vote_minimum_threshold,
        vote_minimum_window_seconds=settings.vote_minimum_window_seconds,

        # Phrase Validation
        phrase_min_words=settings.phrase_min_words,
        phrase_max_words=settings.phrase_max_words,
        phrase_max_length=settings.phrase_max_length,
        phrase_min_char_per_word=settings.phrase_min_char_per_word,
        phrase_max_char_per_word=settings.phrase_max_char_per_word,
        significant_word_min_length=settings.significant_word_min_length,

        # AI Service
        ai_provider=settings.ai_provider,
        ai_openai_model=settings.ai_openai_model,
        ai_gemini_model=settings.ai_gemini_model,
        ai_timeout_seconds=settings.ai_timeout_seconds,
        ai_backup_delay_minutes=settings.ai_backup_delay_minutes,
    )


@router.post("/validate-password", response_model=ValidatePasswordResponse)
async def validate_admin_password(
    request: ValidatePasswordRequest,
    player: Annotated[Player, Depends(get_current_player)]
) -> ValidatePasswordResponse:
    """
    Validate admin password against the application secret key.

    Args:
        request: Password validation request
        player: Current authenticated player (required to access this endpoint)

    Returns:
        ValidatePasswordResponse with valid=True if password matches secret_key
    """
    settings = get_settings()

    # Compare the provided password with the secret_key
    is_valid = request.password == settings.secret_key

    return ValidatePasswordResponse(valid=is_valid)


@router.post("/test-phrase-validation", response_model=TestPhraseValidationResponse)
async def test_phrase_validation(
    request: TestPhraseValidationRequest,
    player: Annotated[Player, Depends(get_current_player)]
) -> TestPhraseValidationResponse:
    """
    Test phrase validation for admin testing purposes.

    Args:
        request: Phrase validation test request
        player: Current authenticated player (required to access this endpoint)

    Returns:
        Detailed validation results including similarity scores
    """
    settings = get_settings()
    validator = get_phrase_validator()

    # Parse phrase details
    phrase = request.phrase.strip()
    words = phrase.split()
    word_count = len(words)
    phrase_length = len(phrase)

    # Start with basic validation
    format_valid, format_error = await validator.validate(phrase)

    # Initialize response fields
    is_valid = False
    error_message = None
    prompt_relevance_score = None
    similarity_to_original = None
    similarity_to_other_copy = None
    word_conflicts = []

    # Perform type-specific validation
    if request.validation_type == "basic":
        is_valid = format_valid
        error_message = format_error if not format_valid else None

    elif request.validation_type == "prompt":
        is_valid, error_message = await validator.validate_prompt_phrase(
            phrase,
            request.prompt_text
        )

        # Calculate prompt relevance score if prompt provided
        if request.prompt_text:
            prompt_relevance_score = validator.calculate_similarity(
                phrase,
                request.prompt_text
            )

        # Extract word conflicts from error message
        if error_message and "Cannot reuse" in error_message:
            # Extract the word from error like "Cannot reuse 'WORD' from prompt"
            word_conflicts.append(error_message.split("'")[1])

    elif request.validation_type == "copy":
        is_valid, error_message = await validator.validate_copy(
            phrase,
            request.original_phrase or "",
            request.other_copy_phrase,
            request.prompt_text
        )

        # Calculate similarity scores
        if request.original_phrase:
            similarity_to_original = validator.calculate_similarity(
                phrase,
                request.original_phrase
            )

        if request.other_copy_phrase:
            similarity_to_other_copy = validator.calculate_similarity(
                phrase,
                request.other_copy_phrase
            )

        # Extract word conflicts from error message
        if error_message:
            if "Cannot reuse" in error_message:
                word_conflicts.append(error_message.split("'")[1])
            elif "too similar to a word" in error_message:
                # Extract from "Word 'xyz' is too similar to a word from..."
                word_conflicts.append(error_message.split("'")[1])

    return TestPhraseValidationResponse(
        is_valid=is_valid,
        error_message=error_message,
        word_count=word_count,
        phrase_length=phrase_length,
        words=words,
        prompt_relevance_score=prompt_relevance_score,
        similarity_to_original=similarity_to_original,
        similarity_to_other_copy=similarity_to_other_copy,
        prompt_relevance_threshold=settings.prompt_relevance_threshold,
        similarity_threshold=settings.similarity_threshold,
        format_check_passed=format_valid,
        dictionary_check_passed=format_valid,  # If format passed, dictionary passed
        word_conflicts=word_conflicts
    )
