"""Application configuration management."""
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from sqlalchemy.engine.url import make_url, URL
from typing import Optional
import logging
import os

SQLITE_LOCAL_URL = "sqlite+aiosqlite:///./crowdcraft.db"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = SQLITE_LOCAL_URL
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis (optional, falls back to in-memory)
    redis_url: str = ""

    # Application
    qf_frontend_url: str = "https://quipflip.xyz"
    mm_frontend_url: str = "https://meme-mint-game.vercel.app"
    github_images_base_url: str = "https://raw.githubusercontent.com/sheegaon/quipflip/main/backend/data"
    serve_images_from_github: bool = True  # Set to False for local development
    environment: str = "development"
    secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"  # Use HS256 for symmetric signing
    access_token_exp_minutes: int = 120  # Access tokens valid for 2 hours
    refresh_token_exp_days: int = 30  # Longer-lived refresh tokens
    access_token_cookie_name: str = "quipflip_access_token"
    refresh_token_cookie_name: str = "quipflip_refresh_token"

    # Admin access
    admin_emails: set[str] = {"tfishman@gmail.com", "x9@x.com"}
    guest_password: str = "QuipGuest"

    # Initial Reaction (IR) Game Settings
    ir_secret_key: str = ""  # Will default to secret_key if not set
    ir_access_token_expire_minutes: int = 120  # 2 hours
    ir_refresh_token_expire_days: int = 30
    ir_access_token_cookie_name: str = "ir_access_token"
    ir_refresh_token_cookie_name: str = "ir_refresh_token"
    ir_initial_balance: int = 1000  # Starting InitCoins for IR players
    ir_daily_bonus_amount: int = 100  # Daily login bonus in InitCoins
    ir_vault_rake_percent: int = 30  # Percentage of earnings going to vault
    ir_backronym_entry_cost: int = 100  # Cost to enter a backronym set in InitCoins
    ir_vote_cost: int = 10  # Cost for non-participants to vote in InitCoins
    ir_vote_reward_correct: int = 20  # Reward for non-participant voters who pick winning entry
    ir_non_participant_vote_cap: int = 10  # Max non-participant votes per guest player
    ir_non_participant_votes_per_set: int = 5  # Max non-participant votes per set
    ir_rapid_entry_timeout_minutes: int = 30  # Timeout before old sets are removed from available pool
    ir_ai_backup_delay_minutes: int = 2  # Delay before AI fills stalled backronym sets
    ir_rapid_entry_timer_minutes: int = 2  # Rapid mode: minutes after last entry before AI fills slots
    ir_rapid_voting_timer_minutes: int = 2  # Rapid mode: minutes for voting phase before AI fills votes
    ir_standard_voting_timer_minutes: int = 30  # Standard mode: minutes for voting phase before AI fills votes

    # ThinkLink (TL) Game Settings
    tl_starting_balance: int = 1000  # Starting ThinkCoins for TL players
    tl_entry_cost: int = 100  # Cost to enter a ThinkLink round
    tl_max_payout: int = 300  # Maximum gross payout per round
    tl_daily_bonus_amount: int = 100  # Daily login bonus
    tl_vault_rake_percent: int = 30  # Percentage of earnings going to vault

    # ThinkLink Semantic Matching
    tl_match_threshold: float = 0.55  # Cosine similarity threshold for answer matching
    tl_cluster_join_threshold: float = 0.75  # Threshold to join existing cluster
    tl_cluster_duplicate_threshold: float = 0.90  # Threshold for near-duplicate detection
    tl_topic_threshold: float = 0.40  # Threshold for on-topic validation
    tl_self_similarity_threshold: float = 0.80  # Threshold for rejecting self-similar guesses

    # ThinkLink Corpus Management
    tl_active_corpus_cap: int = 1000  # Maximum active answers per prompt

    # ThinkLink Scoring
    tl_payout_exponent: float = 1.5  # Exponent for convex payout curve
    tl_round_grace_period_seconds: int = 5  # Grace period for late submissions

    # Game Constants (all values in whole flipcoins/memecoins)
    qf_starting_wallet: int = 5000
    mm_starting_wallet: int = 500
    daily_bonus_amount: int = 100
    prompt_cost: int = 100
    copy_cost_normal: int = 50
    copy_cost_discount: int = 40
    vote_cost: int = 10
    hint_cost: int = 10  # Cost to request AI-generated copy hints
    vote_payout_correct: int = 20
    correct_vote_points: int = 1
    incorrect_vote_points: int = 2
    abandoned_penalty: int = 5
    abandoned_prompt_cooldown_hours: int = 24
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
    vote_minimum_threshold: int = 3  # Minimum votes to start timeout window
    vote_minimum_window_minutes: int = 60  # Minimum vote window duration
    vote_closing_threshold: int = 5  # Votes needed to enter closing window
    vote_closing_window_minutes: int = 5  # Closing window duration
    vote_finalization_refresh_interval_seconds: int = 30  # Throttle for in-request finalization checks

    # Phrase Validation
    use_phrase_validator_api: bool = False
    phrase_validator_url: str = "http://localhost:8001"  # Remote phrase validator base URL
    phrase_min_words: int = 2
    phrase_max_words: int = 5
    phrase_max_length: int = 100
    phrase_min_char_per_word: int = 2
    phrase_max_char_per_word: int = 15
    significant_word_min_length: int = 4

    # Similarity Checking
    embedding_model: str = 'text-embedding-3-small'  # OpenAI embedding model for similarity checks
    prompt_relevance_threshold: float = 0.0  # Cosine similarity threshold for prompt relevance
    similarity_threshold: float = 0.8  # Cosine similarity threshold for rejecting similar phrases
    word_similarity_threshold: float = 0.8  # Minimum ratio for considering words too similar

    # AI Service
    openai_api_key: str = ""
    gemini_api_key: str = ""
    ai_provider: str = "openai"  # Options: "openai" or "gemini"
    ai_openai_model: str = "gpt-5-nano"  # OpenAI model for copy generation
    ai_gemini_model: str = "gemini-2.5-flash-lite"  # Gemini model for copy generation
    ai_timeout_seconds: int = 90  # Timeout for AI API calls (increased for hint generation)
    ai_backup_delay_minutes: int = 30  # Delay before AI provides backup copies/votes
    ai_backup_batch_size: int = 10  # Maximum number of copy or vote rounds to process per backup cycle
    ai_backup_sleep_minutes: int = 30  # Sleep time between backup cycles
    ai_stale_handler_enabled: bool = True  # Feature flag for stale content handler
    ai_stale_threshold_days: int = 2  # Minimum age before content is treated as stale
    ai_stale_check_interval_hours: int = 6 # Interval between stale content sweeps

    # Round service tuning
    round_lock_timeout_seconds: int = 30  # Shared timeout for distributed locks in round flows
    copy_round_max_attempts: int = 10  # Attempts to find a valid prompt when starting copy rounds

    @field_validator("admin_emails", mode="before")
    @classmethod
    def parse_admin_emails(cls, value):
        """Parse comma-separated admin emails from environment variables."""
        if value is None:
            return cls.model_fields["admin_emails"].default
        if isinstance(value, str):
            items = [item.strip().lower() for item in value.split(",") if item.strip()]
        elif isinstance(value, (list, tuple, set)):
            items = [str(item).strip().lower() for item in value if str(item).strip()]
        else:
            raise TypeError("admin_emails must be provided as a string or sequence")
        # Return a set for efficient O(1) lookups.
        return set(items)

    def is_admin_email(self, email: str | None) -> bool:
        """Determine if the provided email belongs to an administrator."""
        if not email:
            return False
        normalized = email.strip().lower()
        return normalized in self.admin_emails

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
                        f"Converted legacy AI_BACKUP_SLEEP_SECONDS={legacy_seconds} to {converted_minutes} minutes"
                    )
                    self.ai_backup_sleep_minutes = converted_minutes
                except ValueError as exc:
                    raise ValueError(
                        "AI_BACKUP_SLEEP_SECONDS must be an integer value"
                    ) from exc

        # Set IR secret key to main secret key if not explicitly set
        if not self.ir_secret_key:
            self.ir_secret_key = self.secret_key

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

        # Validate stale AI configuration
        if self.ai_stale_threshold_days < 1:
            raise ValueError("ai_stale_threshold_days must be at least 1 day")

        if self.ai_stale_check_interval_hours < 1:
            raise ValueError("ai_stale_check_interval_hours must be at least 1 hour")

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
