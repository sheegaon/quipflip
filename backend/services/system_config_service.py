"""Service for managing dynamic system configuration."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.system_config_base import SystemConfigBase
from backend.utils.model_registry import GameType
from backend.utils.model_registry import get_system_config_model
from backend.config import get_settings
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class SystemConfigService:
    """Service for managing system configuration values."""

    # Define all configurable keys with their metadata
    CONFIG_SCHEMA: Dict[str, Dict[str, Any]] = {
        # Economics - Game Constants
        "starting_balance": {
            "type": "int",
            "category": "economics",
            "description": "Initial balance for new players",
            "min": 1000,
            "max": 10000,
        },
        "daily_bonus_amount": {
            "type": "int",
            "category": "economics",
            "description": "Daily login bonus reward",
            "min": 50,
            "max": 500,
        },
        "prompt_cost": {
            "type": "int",
            "category": "economics",
            "description": "Cost to start a prompt round",
            "min": 10,
            "max": 500,
        },
        "copy_cost_normal": {
            "type": "int",
            "category": "economics",
            "description": "Standard cost to start a copy round",
            "min": 5,
            "max": 500,
        },
        "copy_cost_discount": {
            "type": "int",
            "category": "economics",
            "description": "Discounted cost when many prompts waiting",
            "min": 5,
            "max": 500,
        },
        "vote_cost": {
            "type": "int",
            "category": "economics",
            "description": "Cost to start a vote round",
            "min": 1,
            "max": 50,
        },
        "vote_payout_correct": {
            "type": "int",
            "category": "economics",
            "description": "Reward for voting correctly",
            "min": 1,
            "max": 100,
        },
        "abandoned_penalty": {
            "type": "int",
            "category": "economics",
            "description": "Penalty for abandoned rounds",
            "min": 0,
            "max": 50,
        },
        "prize_pool_base": {
            "type": "int",
            "category": "economics",
            "description": "Base prize pool for phrasesets",
            "min": 50,
            "max": 1000,
        },
        "max_outstanding_quips": {
            "type": "int",
            "category": "economics",
            "description": "Maximum concurrent prompts per player",
            "min": 3,
            "max": 50,
        },
        "copy_discount_threshold": {
            "type": "int",
            "category": "economics",
            "description": "Prompts needed to activate discount",
            "min": 5,
            "max": 30,
        },

        # Timing
        "prompt_round_seconds": {
            "type": "int",
            "category": "timing",
            "description": "Time to submit a prompt",
            "min": 60,
            "max": 600,
        },
        "copy_round_seconds": {
            "type": "int",
            "category": "timing",
            "description": "Time to submit a copy",
            "min": 60,
            "max": 600,
        },
        "vote_round_seconds": {
            "type": "int",
            "category": "timing",
            "description": "Time to submit a vote",
            "min": 30,
            "max": 300,
        },
        "grace_period_seconds": {
            "type": "int",
            "category": "timing",
            "description": "Extra time after expiration",
            "min": 0,
            "max": 30,
        },

        # Vote finalization
        "vote_max_votes": {
            "type": "int",
            "category": "timing",
            "description": "Auto-finalize after this many votes",
            "min": 10,
            "max": 100,
        },
        "vote_closing_threshold": {
            "type": "int",
            "category": "timing",
            "description": "Votes to enter closing window",
            "min": 3,
            "max": 20,
        },
        "vote_closing_window_minutes": {
            "type": "int",
            "category": "timing",
            "description": "Time to get more votes before closing",
            "min": 1,
            "max": 10,
        },
        "vote_minimum_threshold": {
            "type": "int",
            "category": "timing",
            "description": "Minimum votes to start timeout",
            "min": 2,
            "max": 10,
        },
        "vote_minimum_window_minutes": {
            "type": "int",
            "category": "timing",
            "description": "Max time before auto-finalizing",
            "min": 5,
            "max": 60,
        },

        # Phrase Validation
        "phrase_min_words": {
            "type": "int",
            "category": "validation",
            "description": "Fewest words allowed in a phrase",
            "min": 1,
            "max": 5,
        },
        "phrase_max_words": {
            "type": "int",
            "category": "validation",
            "description": "Most words allowed in a phrase",
            "min": 3,
            "max": 10,
        },
        "phrase_max_length": {
            "type": "int",
            "category": "validation",
            "description": "Total character limit",
            "min": 50,
            "max": 250,
        },
        "phrase_min_char_per_word": {
            "type": "int",
            "category": "validation",
            "description": "Minimum characters per word",
            "min": 1,
            "max": 5,
        },
        "phrase_max_char_per_word": {
            "type": "int",
            "category": "validation",
            "description": "Maximum characters per word",
            "min": 10,
            "max": 30,
        },
        "significant_word_min_length": {
            "type": "int",
            "category": "validation",
            "description": "Min chars for content words",
            "min": 2,
            "max": 7,
        },
        "use_phrase_validator_api": {
            "type": "bool",
            "category": "validation",
            "description": "Use external phrase validator API service",
        },
        "prompt_relevance_threshold": {
            "type": "float",
            "category": "validation",
            "description": "Cosine similarity threshold for prompt relevance",
            "min": 0.0,
            "max": 1.0,
        },
        "similarity_threshold": {
            "type": "float",
            "category": "validation",
            "description": "Cosine similarity threshold for rejecting similar phrases",
            "min": -1.0,
            "max": 1.0,
        },
        "word_similarity_threshold": {
            "type": "float",
            "category": "validation",
            "description": "Minimum ratio for considering words too similar",
            "min": -1.0,
            "max": 1.0,
        },

        # AI Service
        "ai_provider": {
            "type": "string",
            "category": "ai",
            "description": "Current AI service provider",
            "options": ["openai", "gemini"],
        },
        "ai_openai_model": {
            "type": "string",
            "category": "ai",
            "description": "Model used for OpenAI requests",
        },
        "ai_gemini_model": {
            "type": "string",
            "category": "ai",
            "description": "Model used for Gemini requests",
        },
        "ai_timeout_seconds": {
            "type": "int",
            "category": "ai",
            "description": "Timeout for AI API calls",
            "min": 10,
            "max": 120,
        },
        "ai_backup_delay_minutes": {
            "type": "int",
            "category": "ai",
            "description": "Wait time before AI provides backups",
            "min": 5,
            "max": 60,
        },
        "ai_backup_batch_size": {
            "type": "int",
            "category": "ai",
            "description": "Maximum rounds to process per backup cycle",
            "min": 1,
            "max": 50,
        },
        "ai_backup_sleep_minutes": {
            "type": "int",
            "category": "ai",
            "description": "Sleep time between backup cycles (minutes)",
            "min": 5,
            "max": 120,
        },
        "ai_stale_handler_enabled": {
            "type": "bool",
            "category": "ai",
            "description": "Enable stale AI handler for 3+ day old content",
        },
        "ai_stale_threshold_days": {
            "type": "int",
            "category": "ai",
            "description": "Days before content is considered stale (minimum 3)",
            "min": 3,
        },
        "ai_stale_check_interval_hours": {
            "type": "int",
            "category": "ai",
            "description": "Hours between stale AI handler cycles",
            "min": 1,
        },
    }

    def __init__(self, session: AsyncSession, game_type: GameType = GameType.QF):
        """Initialize the service with a database session."""
        self.session = session
        self.game_type = game_type
        self.config_model = get_system_config_model(game_type)

    async def get_config_value(self, key: str) -> Optional[Any]:
        """
        Get a configuration value from the database, falling back to environment settings.

        Args:
            key: Configuration key

        Returns:
            Configuration value, or None if not found
        """
        result = await self.session.execute(
            select(self.config_model).where(self.config_model.key == key)
        )
        config_entry = result.scalar_one_or_none()

        if config_entry:
            # Convert string value to appropriate type
            return self.deserialize_value(config_entry.value, config_entry.value_type)

        # Fall back to environment settings
        settings = get_settings()
        return getattr(settings, key, None)

    async def set_config_value(
        self,
        key: str,
        value: Any,
        updated_by: Optional[str] = None
    ) -> SystemConfigBase:
        """
        Set a configuration value in the database.

        Args:
            key: Configuration key
            value: New value
            updated_by: Player ID of the admin making the change

        Returns:
            Updated SystemConfigBase entry

        Raises:
            ValueError: If key is not in schema or value is invalid
        """
        if key not in self.CONFIG_SCHEMA:
            raise ValueError(f"Unknown configuration key: {key}")

        schema = self.CONFIG_SCHEMA[key]
        value_type = schema["type"]

        # Validate value
        validated_value = self._validate_value(key, value, schema)

        # Serialize value to string for storage
        serialized_value = self._serialize_value(validated_value, value_type)

        # Check if config entry exists
        result = await self.session.execute(
            select(self.config_model).where(self.config_model.key == key)
        )
        config_entry = result.scalar_one_or_none()

        if config_entry:
            # Update existing entry
            config_entry.value = serialized_value
            config_entry.value_type = value_type
            config_entry.updated_at = datetime.now(timezone.utc)
            config_entry.updated_by = updated_by
        else:
            # Create new entry
            config_entry = self.config_model(
                key=key,
                value=serialized_value,
                value_type=value_type,
                description=schema.get("description"),
                category=schema.get("category"),
                updated_at=datetime.now(timezone.utc),
                updated_by=updated_by
            )
            self.session.add(config_entry)

        await self.session.commit()
        await self.session.refresh(config_entry)

        # Clear settings cache to force reload
        get_settings.cache_clear()

        logger.info(f"Config updated: {key} = {validated_value} by {updated_by or 'system'}")

        return config_entry

    async def get_all_config(self) -> Dict[str, Any]:
        """
        Get all configuration values as a dictionary.

        Returns:
            Dictionary of all config values
        """
        # Start with environment settings
        settings = get_settings()
        config_dict = {}

        for key in self.CONFIG_SCHEMA:
            config_dict[key] = getattr(settings, key, None)

        # Override with database values
        result = await self.session.execute(select(self.config_model))
        db_configs = result.scalars().all()

        legacy_sleep_key = "ai_backup_sleep_seconds"

        for config_entry in db_configs:
            if config_entry.key in self.CONFIG_SCHEMA:
                config_dict[config_entry.key] = self.deserialize_value(
                    config_entry.value,
                    config_entry.value_type
                )
            elif config_entry.key == legacy_sleep_key:
                legacy_value = self.deserialize_value(
                    config_entry.value,
                    config_entry.value_type,
                )
                migrated_minutes = max(1, int(round(legacy_value / 60)))
                logger.info(
                    f"Migrated legacy {legacy_sleep_key}={legacy_value} to ai_backup_sleep_minutes={migrated_minutes}"
                )
                config_dict["ai_backup_sleep_minutes"] = migrated_minutes

        return config_dict

    @staticmethod
    def _validate_value(key: str, value: Any, schema: Dict[str, Any]) -> Any:
        """Validate and convert a configuration value."""
        value_type = schema["type"]

        # Type conversion and validation
        if value_type == "int":
            try:
                validated = int(value)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid integer value for {key}: {value}")

            # Check min/max constraints
            if "min" in schema and validated < schema["min"]:
                raise ValueError(f"{key} must be >= {schema['min']}, got {validated}")
            if "max" in schema and validated > schema["max"]:
                raise ValueError(f"{key} must be <= {schema['max']}, got {validated}")

        elif value_type == "float":
            try:
                validated = float(value)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid float value for {key}: {value}")

            if "min" in schema and validated < schema["min"]:
                raise ValueError(f"{key} must be >= {schema['min']}, got {validated}")
            if "max" in schema and validated > schema["max"]:
                raise ValueError(f"{key} must be <= {schema['max']}, got {validated}")

        elif value_type == "string":
            validated = str(value)

            # Check allowed options
            if "options" in schema and validated not in schema["options"]:
                raise ValueError(
                    f"{key} must be one of {schema['options']}, got {validated}"
                )

        elif value_type == "bool":
            if isinstance(value, bool):
                validated = value
            elif isinstance(value, str):
                validated = value.lower() in ("true", "1", "yes")
            else:
                validated = bool(value)
        else:
            raise ValueError(f"Unknown value type: {value_type}")

        return validated

    @staticmethod
    def _serialize_value(value: Any, value_type: str) -> str:
        """Convert a value to string for database storage."""
        if value_type == "bool":
            return "true" if value else "false"
        return str(value)

    @staticmethod
    def deserialize_value(value: str, value_type: str) -> Any:
        """Convert a string value from database to proper Python type."""
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "string":
            return value
        return value


async def get_system_config_service(session: AsyncSession) -> SystemConfigService:
    """Dependency for getting SystemConfigService."""
    return SystemConfigService(session)
