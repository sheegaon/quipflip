"""Application configuration management."""
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from sqlalchemy.engine.url import make_url, URL
from typing import Optional
import logging
import os

SQLITE_LOCAL_URL = "sqlite+aiosqlite:///./quipflip.db"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = SQLITE_LOCAL_URL

    # Redis (optional, falls back to in-memory)
    redis_url: str = ""

    # Application
    frontend_url: str = "https://quipflip.xyz"
    phrase_validator_url: str = "https://quipflip-pvw-f508f6eb7783.herokuapp.com"
    environment: str = "development"
    secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"  # Use HS256 for symmetric signing
    access_token_exp_minutes: int = 120  # Access tokens valid for 2 hours
    refresh_token_exp_days: int = 30  # Longer-lived refresh tokens
    refresh_token_cookie_name: str = "quipflip_refresh_token"

    # Game Constants (all values in whole flipcoins)
    starting_balance: int = 5000
    daily_bonus_amount: int = 100
    prompt_cost: int = 100
    copy_cost_normal: int = 50
    copy_cost_discount: int = 40
    vote_cost: int = 10
    vote_payout_correct: int = 20
    correct_vote_points: int = 1
    incorrect_vote_points: int = 2
    abandoned_penalty: int = 5
    prize_pool_base: int = 200  # Base prize pool (prompt + 2 copies contribution)
    max_outstanding_quips: int = 10
    guest_max_outstanding_quips: int = 3
    guest_vote_lockout_threshold: int = 3
    guest_vote_lockout_hours: int = 24
    copy_discount_threshold: int = 10  # quips waiting to trigger discount

    # Timing
    prompt_round_seconds: int = 180
    copy_round_seconds: int = 180
    vote_round_seconds: int = 60
    grace_period_seconds: int = 5

    # Vote finalization thresholds
    vote_max_votes: int = 20  # Maximum votes before auto-finalization
    vote_closing_threshold: int = 5  # Votes needed to enter closing window
    vote_closing_window_minutes: int = 1  # Closing window duration (1 minute)
    vote_minimum_threshold: int = 3  # Minimum votes to start timeout window
    vote_minimum_window_minutes: int = 10  # Minimum vote window duration (10 minutes)

    # Phrase Validation
    use_phrase_validator_api: bool = True
    phrase_min_words: int = 2
    phrase_max_words: int = 5
    phrase_max_length: int = 100
    phrase_min_char_per_word: int = 2
    phrase_max_char_per_word: int = 15
    significant_word_min_length: int = 4

    # Similarity Checking
    prompt_relevance_threshold: float = 0.0  # Cosine similarity threshold for prompt relevance
    similarity_threshold: float = 0.8  # Cosine similarity threshold for rejecting similar phrases
    word_similarity_threshold: float = 0.8  # Minimum ratio for considering words too similar

    # AI Service
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ai_provider: str = "openai"  # Options: "openai" or "gemini"
    ai_openai_model: str = "gpt-5-nano"  # OpenAI model for copy generation
    ai_gemini_model: str = "gemini-2.5-flash-lite"  # Gemini model for copy generation
    ai_timeout_seconds: int = 60  # Timeout for AI API calls
    ai_backup_delay_minutes: int = 15  # Delay before AI provides backup copies/votes
    ai_backup_batch_size: int = 3  # Maximum number of copy or vote rounds to process per backup cycle
    ai_backup_sleep_minutes: int = 60  # Sleep time between backup cycles (1 hour)

    @model_validator(mode="after")
    def validate_all_config(self):
        """Validate security configuration and normalize Postgres URLs."""
        logger = logging.getLogger(__name__)
        
        logger.info("=== CONFIG VALIDATION DEBUG ===")
        
        # Legacy support for AI backup sleep environment variables
        if not os.getenv("AI_BACKUP_SLEEP_MINUTES"):
            legacy_seconds = os.getenv("AI_BACKUP_SLEEP_SECONDS")
            if legacy_seconds:
                try:
                    seconds_value = int(legacy_seconds)
                    converted_minutes = max(1, int(round(seconds_value / 60)))
                    logger.info(
                        "Converted legacy AI_BACKUP_SLEEP_SECONDS=%s to %s minutes",
                        legacy_seconds,
                        converted_minutes,
                    )
                    self.ai_backup_sleep_minutes = converted_minutes
                except ValueError as exc:
                    raise ValueError(
                        "AI_BACKUP_SLEEP_SECONDS must be an integer value"
                    ) from exc

        # Security validation
        if self.environment == "production":
            if self.secret_key == "dev-secret-key-change-in-production":
                raise ValueError("secret_key must be changed from default value in production")

        # Validate JWT algorithm
        if self.jwt_algorithm not in ["HS256", "HS384", "HS512"]:
            raise ValueError(f"Unsupported JWT algorithm: {self.jwt_algorithm}. Use HS256, HS384, or HS512.")

        # Validate token expiration times
        if self.access_token_exp_minutes < 1 or self.access_token_exp_minutes > 1440:  # 1 min to 24 hours
            raise ValueError("access_token_exp_minutes must be between 1 and 1440 (24 hours)")

        if self.refresh_token_exp_days < 1 or self.refresh_token_exp_days > 365:
            raise ValueError("refresh_token_exp_days must be between 1 and 365 days")

        # Database URL normalization
        url = self.database_url
        logger.info(f"Original DATABASE_URL length: {len(url)}")
        logger.info(f"Original URL starts with: {url[:30]}...")
        
        if not url:
            logger.warning("Empty DATABASE_URL, using SQLite fallback")
            self.database_url = SQLITE_LOCAL_URL
            return self

        parsed: Optional[URL] = None
        try:
            parsed = make_url(url)
            logger.info(f"URL parsed successfully")
            logger.info(f"Original drivername: {parsed.drivername}")
            
            # Log password details for debugging
            if parsed.password:
                logger.info(f"Original password length: {len(parsed.password)}")
                # Check for URL encoding issues
                import urllib.parse
                if '%' in parsed.password:
                    logger.info("Password appears to be URL-encoded")
                    decoded = urllib.parse.unquote(parsed.password)
                    logger.info(f"Decoded password length: {len(decoded)}")
                
        except Exception as e:  # pragma: no cover - defensive fallback
            logger.error(f"Failed to parse DATABASE_URL: {e}")
            logging.warning(f"Invalid DATABASE_URL '{url}'; falling back to default sqlite database.")
            self.database_url = SQLITE_LOCAL_URL
            return self

        drivername = parsed.drivername
        if drivername.startswith("postgres") and "+asyncpg" not in drivername:
            old_drivername = drivername
            parsed = parsed.set(drivername="postgresql+asyncpg")
            logger.info(f"Driver normalized: {old_drivername} -> {parsed.drivername}")
            # Use render_as_string to properly re-encode special characters in password
            self.database_url = parsed.render_as_string(hide_password=False)
            logger.info(f"Final DATABASE_URL length: {len(self.database_url)}")
        else:
            # Keep the original value when no normalization is required.
            # Use render_as_string to properly re-encode special characters in password
            self.database_url = parsed.render_as_string(hide_password=False)
            logger.info(f"No driver normalization needed")

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
