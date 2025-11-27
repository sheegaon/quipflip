"""System configuration service for Meme Mint."""

from typing import Any
from backend.services.system_config_service import SystemConfigService
from backend.utils.model_registry import GameType


class MMSystemConfigService(SystemConfigService):
    """Expose Meme Mint specific config schema and helpers."""

    CONFIG_SCHEMA = {
        "mm_round_entry_cost": {
            "type": "int",
            "category": "economics",
            "description": "Wallet cost to enter a Meme Mint voting round",
            "min": 0,
            "max": 1000,
        },
        "mm_captions_per_round": {
            "type": "int",
            "category": "economics",
            "description": "Number of captions shown per round",
            "min": 1,
            "max": 10,
        },
        "mm_free_captions_per_day": {
            "type": "int",
            "category": "economics",
            "description": "Daily free caption submissions per player",
            "min": 0,
            "max": 10,
        },
        "mm_caption_submission_cost": {
            "type": "int",
            "category": "economics",
            "description": "Wallet cost for paid caption submissions",
            "min": 0,
            "max": 1000,
        },
        "mm_house_rake_vault_pct": {
            "type": "float",
            "category": "economics",
            "description": "Portion of caption earnings routed to the vault",
            "min": 0.0,
            "max": 1.0,
        },
        "mm_min_quality_score_active": {
            "type": "float",
            "category": "validation",
            "description": "Quality threshold below which captions are retired",
            "min": 0.0,
            "max": 1.0,
        },
        "mm_retire_after_shows": {
            "type": "int",
            "category": "validation",
            "description": "Auto-retire captions after this many shows",
            "min": 0,
            "max": 100000,
        },
        "mm_max_captions_per_image": {
            "type": "int",
            "category": "validation",
            "description": "Soft cap on captions per image",
            "min": 0,
            "max": 1000,
        },
        "mm_starting_wallet_override": {
            "type": "int",
            "category": "economics",
            "description": "Optional override for starting wallet balance",
            "min": 0,
            "max": 100000,
        },
        "mm_daily_bonus_amount": {
            "type": "int",
            "category": "economics",
            "description": "Optional Meme Mint specific daily bonus",
            "min": 0,
            "max": 10000,
        },
        "mm_lcf_bonus_wallet": {
            "type": "int",
            "category": "economics",
            "description": "Wallet payout for local crowd favorite bonus",
            "min": 0,
            "max": 10000,
        },
        "mm_lcf_bonus_vault": {
            "type": "int",
            "category": "economics",
            "description": "Vault payout for local crowd favorite bonus",
            "min": 0,
            "max": 10000,
        },
        "mm_first_vote_bonus_amount": {
            "type": "int",
            "category": "economics",
            "description": "Wallet bonus for first vote on a caption",
            "min": 0,
            "max": 10000,
        },
    }

    DEFAULTS = {
        "mm_round_entry_cost": 5,
        "mm_captions_per_round": 5,
        "mm_free_captions_per_day": 1,
        "mm_caption_submission_cost": 10,
        "mm_house_rake_vault_pct": 0.5,
        "mm_daily_bonus_amount": 100,
        "mm_lcf_bonus_wallet": 2,
        "mm_lcf_bonus_vault": 1,
        "mm_first_vote_bonus_amount": 2,
    }

    def __init__(self, session, game_type: GameType = GameType.MM):
        super().__init__(session, game_type=game_type)
        self._cache: dict[str, Any] = {}

    async def get_config_value(self, key: str, default: Any = None) -> Any:
        """Return a cached config value, falling back to defaults or env settings."""
        if key in self._cache:
            return self._cache[key]

        value = await super().get_config_value(key)
        if value is None:
            value = self.DEFAULTS.get(key, default)
        if value is None:
            value = default

        self._cache[key] = value
        return value
