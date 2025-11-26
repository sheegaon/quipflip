"""Add Meme Mint game tables.

Revision ID: a0b1c2d3e4f5
Revises: f0f0d0b1c2a3
Create Date: 2026-01-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_uuid_type, get_timestamp_default

# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "f0f0d0b1c2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = get_uuid_type()
    timestamp_default = get_timestamp_default()

    # mm_players table - Meme Mint player accounts
    op.create_table(
        "mm_players",
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False, unique=True),
        sa.Column("username_canonical", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("wallet", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("vault", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("last_login_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_incorrect_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vote_lockout_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tutorial_completed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("tutorial_progress", sa.String(length=20), nullable=False, server_default="not_started"),
        sa.Column("tutorial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tutorial_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("player_id"),
        sa.UniqueConstraint("username_canonical", name="uq_mm_players_username_canonical"),
    )
    op.create_index("ix_mm_players_username", "mm_players", ["username"])

    # mm_transactions table - Ledger entries
    op.create_table(
        "mm_transactions",
        sa.Column("transaction_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("reference_id", uuid, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("wallet_type", sa.String(length=20), nullable=False, server_default="wallet"),
        sa.Column("wallet_balance_after", sa.Integer(), nullable=True),
        sa.Column("vault_balance_after", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("transaction_id"),
    )
    op.create_index("ix_mm_transactions_player_created", "mm_transactions", ["player_id", "created_at"])
    op.create_index("ix_mm_transactions_type", "mm_transactions", ["type"])
    op.create_index("ix_mm_transactions_reference", "mm_transactions", ["reference_id"])

    # mm_refresh_tokens table - Stored refresh tokens
    op.create_table(
        "mm_refresh_tokens",
        sa.Column("token_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_id"),
    )
    op.create_index("ix_mm_refresh_tokens_player_id", "mm_refresh_tokens", ["player_id"])
    op.create_index("ix_mm_refresh_tokens_token_hash", "mm_refresh_tokens", ["token_hash"])

    # mm_daily_bonuses table - Daily bonuses
    op.create_table(
        "mm_daily_bonuses",
        sa.Column("bonus_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bonus_id"),
        sa.UniqueConstraint("player_id", "date", name="uq_mm_player_daily_bonus"),
    )
    op.create_index("ix_mm_daily_bonuses_player_id", "mm_daily_bonuses", ["player_id"])
    op.create_index("ix_mm_daily_bonuses_date", "mm_daily_bonuses", ["date"])

    # mm_images table - Meme images catalog
    op.create_table(
        "mm_images",
        sa.Column("image_id", uuid, nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("attribution_text", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("created_by_player_id", uuid, nullable=True),
        sa.ForeignKeyConstraint(["created_by_player_id"], ["mm_players.player_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("image_id"),
    )
    op.create_index("ix_mm_images_status", "mm_images", ["status"])

    # mm_captions table - Captions for images
    op.create_table(
        "mm_captions",
        sa.Column("caption_id", uuid, nullable=False),
        sa.Column("image_id", uuid, nullable=False),
        sa.Column("author_player_id", uuid, nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("parent_caption_id", uuid, nullable=True),
        sa.Column("text", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("shows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("picks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_vote_awarded", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("lifetime_earnings_gross", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_to_wallet", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_to_vault", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["image_id"], ["mm_images.image_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_player_id"], ["mm_players.player_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_caption_id"], ["mm_captions.caption_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("caption_id"),
    )
    op.create_index("ix_mm_captions_image_status", "mm_captions", ["image_id", "status"])
    op.create_index("ix_mm_captions_author", "mm_captions", ["author_player_id"])
    op.create_index("ix_mm_captions_parent", "mm_captions", ["parent_caption_id"])
    op.create_index("ix_mm_captions_status_quality", "mm_captions", ["status", "quality_score"])

    # mm_vote_rounds table - Voting rounds
    op.create_table(
        "mm_vote_rounds",
        sa.Column("round_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("image_id", uuid, nullable=False),
        sa.Column("caption_ids_shown", sa.JSON(), nullable=False),
        sa.Column("chosen_caption_id", uuid, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("entry_cost", sa.Integer(), nullable=False),
        sa.Column("payout_to_wallet", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payout_to_vault", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_vote_bonus_applied", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("result_finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["mm_images.image_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chosen_caption_id"], ["mm_captions.caption_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("round_id"),
    )
    op.create_index("ix_mm_vote_round_player_created", "mm_vote_rounds", ["player_id", "created_at"])
    op.create_index("ix_mm_vote_round_image_created", "mm_vote_rounds", ["image_id", "created_at"])
    op.create_index("ix_mm_vote_round_chosen_caption", "mm_vote_rounds", ["chosen_caption_id"])

    # mm_captions_seen table - Caption history
    op.create_table(
        "mm_captions_seen",
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("caption_id", uuid, nullable=False),
        sa.Column("image_id", uuid, nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["caption_id"], ["mm_captions.caption_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["mm_images.image_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "caption_id"),
    )
    op.create_index("ix_mm_caption_seen_player_image", "mm_captions_seen", ["player_id", "image_id"])
    op.create_index("ix_mm_caption_seen_caption", "mm_captions_seen", ["caption_id"])

    # mm_caption_submissions table - Submission log
    op.create_table(
        "mm_caption_submissions",
        sa.Column("submission_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("image_id", uuid, nullable=False),
        sa.Column("caption_id", uuid, nullable=True),
        sa.Column("submission_text", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("rejection_reason", sa.String(length=100), nullable=True),
        sa.Column("used_free_slot", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["mm_images.image_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["caption_id"], ["mm_captions.caption_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("submission_id"),
    )
    op.create_index("ix_mm_caption_submission_status_created", "mm_caption_submissions", ["status", "created_at"])
    op.create_index("ix_mm_caption_submission_player", "mm_caption_submissions", ["player_id"])
    op.create_index("ix_mm_caption_submission_image", "mm_caption_submissions", ["image_id"])
    op.create_index("ix_mm_caption_submission_caption", "mm_caption_submissions", ["caption_id"])

    # mm_player_daily_states table - Daily free caption quotas
    op.create_table(
        "mm_player_daily_states",
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("free_captions_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "date"),
    )
    op.create_index("ix_mm_player_daily_state_date", "mm_player_daily_states", ["date"])

    # mm_system_config table - Configured settings
    op.create_table(
        "mm_system_config",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("mm_system_config")
    op.drop_index("ix_mm_player_daily_state_date", table_name="mm_player_daily_states")
    op.drop_table("mm_player_daily_states")
    op.drop_index("ix_mm_caption_submission_caption", table_name="mm_caption_submissions")
    op.drop_index("ix_mm_caption_submission_image", table_name="mm_caption_submissions")
    op.drop_index("ix_mm_caption_submission_player", table_name="mm_caption_submissions")
    op.drop_index("ix_mm_caption_submission_status_created", table_name="mm_caption_submissions")
    op.drop_table("mm_caption_submissions")
    op.drop_index("ix_mm_caption_seen_caption", table_name="mm_captions_seen")
    op.drop_index("ix_mm_caption_seen_player_image", table_name="mm_captions_seen")
    op.drop_table("mm_captions_seen")
    op.drop_index("ix_mm_vote_round_chosen_caption", table_name="mm_vote_rounds")
    op.drop_index("ix_mm_vote_round_image_created", table_name="mm_vote_rounds")
    op.drop_index("ix_mm_vote_round_player_created", table_name="mm_vote_rounds")
    op.drop_table("mm_vote_rounds")
    op.drop_index("ix_mm_captions_status_quality", table_name="mm_captions")
    op.drop_index("ix_mm_captions_parent", table_name="mm_captions")
    op.drop_index("ix_mm_captions_author", table_name="mm_captions")
    op.drop_index("ix_mm_captions_image_status", table_name="mm_captions")
    op.drop_table("mm_captions")
    op.drop_index("ix_mm_images_status", table_name="mm_images")
    op.drop_table("mm_images")
    op.drop_index("ix_mm_daily_bonuses_date", table_name="mm_daily_bonuses")
    op.drop_index("ix_mm_daily_bonuses_player_id", table_name="mm_daily_bonuses")
    op.drop_table("mm_daily_bonuses")
    op.drop_index("ix_mm_refresh_tokens_token_hash", table_name="mm_refresh_tokens")
    op.drop_index("ix_mm_refresh_tokens_player_id", table_name="mm_refresh_tokens")
    op.drop_table("mm_refresh_tokens")
    op.drop_index("ix_mm_transactions_reference", table_name="mm_transactions")
    op.drop_index("ix_mm_transactions_type", table_name="mm_transactions")
    op.drop_index("ix_mm_transactions_player_created", table_name="mm_transactions")
    op.drop_table("mm_transactions")
    op.drop_index("ix_mm_players_username", table_name="mm_players")
    op.drop_table("mm_players")
