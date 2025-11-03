"""Admin routes for administrative operations."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, constr
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from uuid import UUID
from backend.config import get_settings
from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.services.phrase_validator import get_phrase_validator
from backend.services.system_config_service import SystemConfigService
from backend.services.player_service import PlayerService
from backend.services.cleanup_service import CleanupService
from backend.services.flagged_prompt_service import FlaggedPromptService
from backend.services.transaction_service import TransactionService
from backend.schemas.auth import EmailLike
from backend.schemas.flagged_prompt import (
    FlaggedPromptListResponse,
    FlaggedPromptItem,
    ResolveFlaggedPromptRequest,
)
from typing import Annotated, Optional, Any

router = APIRouter(prefix="/admin", tags=["admin"])


class ValidatePasswordRequest(BaseModel):
    """Request model for admin password validation."""
    password: str


class ValidatePasswordResponse(BaseModel):
    """Response model for admin password validation."""
    valid: bool


class AdminPlayerSummary(BaseModel):
    """Summary information for a player returned in admin search."""

    player_id: UUID
    username: str
    email: EmailLike
    balance: int
    created_at: datetime
    outstanding_prompts: int


class AdminDeletePlayerRequest(BaseModel):
    """Request model for deleting a player via admin panel."""

    player_id: Optional[UUID] = None
    email: Optional[EmailLike] = None
    username: Optional[str] = None
    confirmation: constr(pattern=r"^DELETE$", min_length=6, max_length=6)


class AdminDeletePlayerResponse(BaseModel):
    """Response after deleting a player from admin panel."""

    deleted_player_id: UUID
    deleted_username: str
    deleted_email: EmailLike
    deletion_counts: dict[str, int]


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
    vote_closing_window_minutes: int
    vote_minimum_threshold: int
    vote_minimum_window_minutes: int

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
    ai_backup_batch_size: int
    ai_backup_sleep_minutes: int
    ai_stale_handler_enabled: bool
    ai_stale_threshold_days: int
    ai_stale_check_interval_hours: int


@router.get("/config", response_model=GameConfigResponse)
async def get_game_config(
    player: Annotated[Player, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_db)]
) -> GameConfigResponse:
    """
    Get current game configuration values (from database overrides or environment defaults).

    Args:
        player: Current authenticated player (required to access this endpoint)
        session: Database session

    Returns:
        GameConfigResponse with all configuration values
    """
    service = SystemConfigService(session)
    config = await service.get_all_config()

    return GameConfigResponse(
        # Game Constants
        starting_balance=config.get("starting_balance", 5000),
        daily_bonus_amount=config.get("daily_bonus_amount", 100),
        prompt_cost=config.get("prompt_cost", 100),
        copy_cost_normal=config.get("copy_cost_normal", 50),
        copy_cost_discount=config.get("copy_cost_discount", 40),
        vote_cost=config.get("vote_cost", 10),
        vote_payout_correct=config.get("vote_payout_correct", 20),
        abandoned_penalty=config.get("abandoned_penalty", 5),
        prize_pool_base=config.get("prize_pool_base", 200),
        max_outstanding_quips=config.get("max_outstanding_quips", 10),
        copy_discount_threshold=config.get("copy_discount_threshold", 10),

        # Timing
        prompt_round_seconds=config.get("prompt_round_seconds", 180),
        copy_round_seconds=config.get("copy_round_seconds", 180),
        vote_round_seconds=config.get("vote_round_seconds", 60),
        grace_period_seconds=config.get("grace_period_seconds", 5),

        # Vote finalization
        vote_max_votes=config.get("vote_max_votes", 20),
        vote_closing_threshold=config.get("vote_closing_threshold", 5),
        vote_closing_window_minutes=config.get("vote_closing_window_minutes", 1),
        vote_minimum_threshold=config.get("vote_minimum_threshold", 3),
        vote_minimum_window_minutes=config.get("vote_minimum_window_minutes", 10),

        # Phrase Validation
        phrase_min_words=config.get("phrase_min_words", 2),
        phrase_max_words=config.get("phrase_max_words", 5),
        phrase_max_length=config.get("phrase_max_length", 100),
        phrase_min_char_per_word=config.get("phrase_min_char_per_word", 2),
        phrase_max_char_per_word=config.get("phrase_max_char_per_word", 15),
        significant_word_min_length=config.get("significant_word_min_length", 4),

        # AI Service
        ai_provider=config.get("ai_provider", "openai"),
        ai_openai_model=config.get("ai_openai_model", "gpt-5-nano"),
        ai_gemini_model=config.get("ai_gemini_model", "gemini-2.5-flash-lite"),
        ai_timeout_seconds=config.get("ai_timeout_seconds", 30),
        ai_backup_delay_minutes=config.get("ai_backup_delay_minutes", 15),
        ai_backup_batch_size=config.get("ai_backup_batch_size", 3),
        ai_backup_sleep_minutes=config.get("ai_backup_sleep_minutes", 60),
        ai_stale_handler_enabled=config.get("ai_stale_handler_enabled", True),
        ai_stale_threshold_days=config.get("ai_stale_threshold_days", 3),
        ai_stale_check_interval_hours=config.get("ai_stale_check_interval_hours", 12),
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


@router.get("/players/search", response_model=AdminPlayerSummary)
async def search_player(
    player: Annotated[Player, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_db)],
    email: Optional[EmailLike] = Query(None),
    username: Optional[str] = Query(None),
) -> AdminPlayerSummary:
    """Search for a player by email or username."""

    if not player.is_admin:
        raise HTTPException(status_code=403, detail="admin_only")

    if not email and not username:
        raise HTTPException(status_code=400, detail="missing_identifier")

    player_service = PlayerService(session)
    target_player: Player | None = None

    if email:
        target_player = await player_service.get_player_by_email(email)
    elif username:
        target_player = await player_service.get_player_by_username(username)

    if not target_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    outstanding = await player_service.get_outstanding_prompts_count(target_player.player_id)

    return AdminPlayerSummary(
        player_id=target_player.player_id,
        username=target_player.username,
        email=target_player.email,
        balance=target_player.balance,
        created_at=target_player.created_at,
        outstanding_prompts=outstanding,
    )


@router.delete("/players", response_model=AdminDeletePlayerResponse)
async def delete_player_admin(
    request: AdminDeletePlayerRequest,
    player: Annotated[Player, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_db)]
) -> AdminDeletePlayerResponse:
    """Delete a player account and associated data via admin panel."""

    if not player.is_admin:
        raise HTTPException(status_code=403, detail="admin_only")

    identifier = request.player_id or request.email or request.username
    if not identifier:
        raise HTTPException(status_code=400, detail="missing_identifier")

    player_service = PlayerService(session)
    target_player: Player | None = None

    if request.player_id:
        target_player = await player_service.get_player_by_id(request.player_id)
    elif request.email:
        target_player = await player_service.get_player_by_email(request.email)
    elif request.username:
        target_player = await player_service.get_player_by_username(request.username)

    if not target_player:
        raise HTTPException(status_code=404, detail="player_not_found")

    cleanup_service = CleanupService(session)
    deletion_counts = await cleanup_service.delete_player(target_player.player_id)

    return AdminDeletePlayerResponse(
        deleted_player_id=target_player.player_id,
        deleted_username=target_player.username,
        deleted_email=target_player.email,
        deletion_counts=deletion_counts,
    )


@router.get("/flags", response_model=FlaggedPromptListResponse)
async def list_flagged_prompts(
    player: Annotated[Player, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_db)],
    status: Optional[str] = Query("pending"),
) -> FlaggedPromptListResponse:
    """Retrieve flagged prompt phrases for review."""

    if not player.is_admin:
        raise HTTPException(status_code=403, detail="admin_only")

    normalized_status = status if status not in {None, "all", ""} else None
    service = FlaggedPromptService(session)
    records = await service.list_flags(normalized_status)

    flags = [FlaggedPromptItem.from_record(record) for record in records]

    return FlaggedPromptListResponse(flags=flags)


@router.post("/flags/{flag_id}/resolve", response_model=FlaggedPromptItem)
async def resolve_flagged_prompt(
    flag_id: UUID,
    request: ResolveFlaggedPromptRequest,
    player: Annotated[Player, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FlaggedPromptItem:
    """Resolve a flagged prompt by confirming or dismissing it."""

    if not player.is_admin:
        raise HTTPException(status_code=403, detail="admin_only")

    service = FlaggedPromptService(session)
    transaction_service = TransactionService(session)

    try:
        record = await service.resolve_flag(flag_id, request.action, player, transaction_service)
    except ValueError as exc:
        detail = str(exc)
        if detail in {"flag_already_resolved", "invalid_action"}:
            raise HTTPException(status_code=400, detail=detail) from exc
        raise

    if not record:
        raise HTTPException(status_code=404, detail="flag_not_found")

    return FlaggedPromptItem.from_record(record)


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
    format_valid, format_error = validator.validate(phrase)

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


class UpdateConfigRequest(BaseModel):
    """Request model for updating configuration."""
    key: str
    value: Any


class UpdateConfigResponse(BaseModel):
    """Response model for configuration update."""
    success: bool
    key: str
    value: Any
    message: Optional[str] = None


@router.patch("/config", response_model=UpdateConfigResponse)
async def update_config(
    request: UpdateConfigRequest,
    player: Annotated[Player, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_db)]
) -> UpdateConfigResponse:
    """
    Update a configuration value.

    Args:
        request: Configuration update request
        player: Current authenticated player (required to access this endpoint)
        session: Database session

    Returns:
        UpdateConfigResponse with the updated value

    Raises:
        HTTPException: If configuration key is invalid or value is out of range
    """
    try:
        service = SystemConfigService(session)

        # Update the configuration
        config_entry = await service.set_config_value(
            request.key,
            request.value,
            updated_by=str(player.player_id)
        )

        # Get the deserialized value to return
        deserialized_value = service._deserialize_value(
            config_entry.value,
            config_entry.value_type
        )

        return UpdateConfigResponse(
            success=True,
            key=request.key,
            value=deserialized_value,
            message=f"Configuration '{request.key}' updated successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")
