"""Rename all Quipflip tables with qf_ prefix to prepare for Initial Reaction.

Revision ID: rename_qf_001
Revises: 001_add_notifications, guest_lockout_001
Create Date: 2025-01-15

This migration renames all existing Quipflip tables to use the qf_ prefix,
allowing Initial Reaction (IR) to use its own table namespace without conflicts.

This is a merge migration that combines two migration branches:
- The main 001_add_notifications branch
- The guest_lockout_001 branch (which includes post-lockout migrations)
"""
from typing import Sequence, Union
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "rename_qf_001"
down_revision: Union[str, Sequence[str]] = ("001_add_notifications", "guest_lockout_001")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename all QF tables with qf_ prefix."""
    # Core tables
    op.rename_table("players", "qf_players")
    op.rename_table("prompts", "qf_prompts")
    op.rename_table("rounds", "qf_rounds")
    op.rename_table("phrasesets", "qf_phrasesets")
    op.rename_table("votes", "qf_votes")
    op.rename_table("transactions", "qf_transactions")

    # Supporting tables
    op.rename_table("daily_bonuses", "qf_daily_bonuses")
    op.rename_table("result_views", "qf_result_views")
    op.rename_table("player_abandoned_prompts", "qf_player_abandoned_prompts")
    op.rename_table("prompt_feedback", "qf_prompt_feedback")
    op.rename_table("phraseset_activity", "qf_phraseset_activity")
    op.rename_table("refresh_tokens", "qf_refresh_tokens")
    op.rename_table("quests", "qf_quests")
    op.rename_table("quest_templates", "qf_quest_templates")
    op.rename_table("system_config", "qf_system_config")
    op.rename_table("flagged_prompts", "qf_flagged_prompts")
    op.rename_table("survey_responses", "qf_survey_responses")
    op.rename_table("hints", "qf_hints")
    op.rename_table("ai_phrase_cache", "qf_ai_phrase_cache")
    op.rename_table("ai_metrics", "qf_ai_metrics")
    op.rename_table("notifications", "qf_notifications")
    op.rename_table("user_activity", "qf_user_activity")


def downgrade() -> None:
    """Revert table renames (not recommended in production)."""
    # Supporting tables
    op.rename_table("qf_user_activity", "user_activity")
    op.rename_table("qf_notifications", "notifications")
    op.rename_table("qf_ai_metrics", "ai_metrics")
    op.rename_table("qf_ai_phrase_cache", "ai_phrase_cache")
    op.rename_table("qf_hints", "hints")
    op.rename_table("qf_survey_responses", "survey_responses")
    op.rename_table("qf_flagged_prompts", "flagged_prompts")
    op.rename_table("qf_system_config", "system_config")
    op.rename_table("qf_quest_templates", "quest_templates")
    op.rename_table("qf_quests", "quests")
    op.rename_table("qf_refresh_tokens", "refresh_tokens")
    op.rename_table("qf_phraseset_activity", "phraseset_activity")
    op.rename_table("qf_prompt_feedback", "prompt_feedback")
    op.rename_table("qf_player_abandoned_prompts", "player_abandoned_prompts")
    op.rename_table("qf_result_views", "result_views")
    op.rename_table("qf_daily_bonuses", "daily_bonuses")

    # Core tables
    op.rename_table("qf_transactions", "transactions")
    op.rename_table("qf_votes", "votes")
    op.rename_table("qf_phrasesets", "phrasesets")
    op.rename_table("qf_rounds", "rounds")
    op.rename_table("qf_prompts", "prompts")
    op.rename_table("qf_players", "players")
