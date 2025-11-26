"""Admin routes for administrative operations."""
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging
from typing import Annotated, Optional, Type

from backend.config import get_settings
from backend.database import get_db
from backend.dependencies import get_admin_player
from backend.models.qf.player import QFPlayer
from backend.services import SystemConfigService, TransactionService, GameType
from backend.services.qf import (
    get_phrase_validator,
    QFPlayerService,
    QFCleanupService,
    FlaggedPromptService,
)
from backend.schemas.flagged_prompt import (
    FlaggedPromptListResponse,
    FlaggedPromptItem,
    ResolveFlaggedPromptRequest,
)
from backend.routers.admin_router_base import AdminRouterBase

logger = logging.getLogger(__name__)


class GameConfigResponse(BaseModel):
    """Response model for QuipFlip game configuration."""
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


async def _test_phrase_validation(
        request: TestPhraseValidationRequest, player: QFPlayer
) -> TestPhraseValidationResponse:
    """Test phrase validation for admin testing purposes."""
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


class QFAdminRouter(AdminRouterBase):
    """Quipflip admin router with game-specific administrative functionality."""

    def __init__(self):
        """Initialize the QF admin router."""
        super().__init__(GameType.QF)
        self._add_qf_specific_routes()

    @property
    def player_service_class(self) -> Type[QFPlayerService]:
        """Return the QF player service class."""
        return QFPlayerService

    @property
    def cleanup_service_class(self) -> Type[QFCleanupService]:
        """Return the QF cleanup service class."""
        return QFCleanupService

    @property
    def admin_player_dependency(self):
        """Return the QF admin player dependency."""
        return get_admin_player

    def get_game_config_response_model(self) -> Type[GameConfigResponse]:
        """Return the QF game config response model."""
        return GameConfigResponse

    async def get_game_config(self, player: QFPlayer, session: AsyncSession) -> GameConfigResponse:
        """Get QuipFlip-specific configuration."""
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
            ai_backup_sleep_minutes=config.get("ai_backup_sleep_minutes", 30),
            ai_stale_handler_enabled=config.get("ai_stale_handler_enabled", True),
            ai_stale_threshold_days=config.get("ai_stale_threshold_days", 2),
            ai_stale_check_interval_hours=config.get("ai_stale_check_interval_hours", 6),
        )

    def _add_qf_specific_routes(self):
        """Add QuipFlip-specific admin routes."""

        @self.router.get("/config", response_model=GameConfigResponse)
        async def get_config(
            player: Annotated[QFPlayer, Depends(get_admin_player)],
            session: Annotated[AsyncSession, Depends(get_db)]
        ):
            """Get current QuipFlip game configuration values."""
            return await self.get_game_config(player, session)

        @self.router.get("/flags", response_model=FlaggedPromptListResponse)
        async def list_flagged_prompts(
            player: Annotated[QFPlayer, Depends(get_admin_player)],
            session: Annotated[AsyncSession, Depends(get_db)],
            status: Optional[str] = Query("pending"),
        ):
            """Retrieve flagged prompt phrases for review."""
            normalized_status = status if status not in {None, "all", ""} else None
            service = FlaggedPromptService(session)
            records = await service.list_flags(normalized_status)

            flags = [FlaggedPromptItem.from_record(record) for record in records]
            return FlaggedPromptListResponse(flags=flags)

        @self.router.post("/flags/{flag_id}/resolve", response_model=FlaggedPromptItem)
        async def resolve_flagged_prompt(
            flag_id: UUID,
            request: ResolveFlaggedPromptRequest,
            player: Annotated[QFPlayer, Depends(get_admin_player)],
            session: Annotated[AsyncSession, Depends(get_db)],
        ):
            """Resolve a flagged prompt by confirming or dismissing it."""
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

        @self.router.post("/test-phrase-validation", response_model=TestPhraseValidationResponse)
        async def test_phrase_validation(
            request: TestPhraseValidationRequest,
            player: Annotated[QFPlayer, Depends(get_admin_player)]
        ):
            """Test phrase validation for admin testing purposes."""
            return await _test_phrase_validation(request, player)


# Create and expose the router instance
qf_admin_router = QFAdminRouter()
router = qf_admin_router.router
