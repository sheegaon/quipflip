"""Add recoverable accounts and magic-link support.

Revision ID: b9c8d7e6f5a4
Revises: f2a3b4c5d6e7
Create Date: 2026-06-24 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_uuid_type


revision: str = "b9c8d7e6f5a4"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = get_uuid_type()

    op.create_table(
        "accounts",
        sa.Column("account_id", uuid_type, nullable=False),
        sa.Column("primary_email", sa.String(length=255), nullable=False),
        sa.Column("primary_player_id", uuid_type, nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["primary_player_id"], ["players.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("primary_email", name="uq_accounts_primary_email"),
        sa.UniqueConstraint("primary_player_id", name="uq_accounts_primary_player_id"),
    )

    op.create_table(
        "magic_links",
        sa.Column("magic_link_id", uuid_type, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("guest_player_id", uuid_type, nullable=True),
        sa.Column("account_id", uuid_type, nullable=True),
        sa.Column("redirect_path", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guest_player_id"], ["players.player_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.account_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("magic_link_id"),
        sa.UniqueConstraint("token_hash", name="uq_magic_links_token_hash"),
    )

    op.create_index("ix_magic_links_email", "magic_links", ["email"], unique=False)
    op.create_index("ix_magic_links_guest_player_id", "magic_links", ["guest_player_id"], unique=False)
    op.create_index("ix_magic_links_account_id", "magic_links", ["account_id"], unique=False)

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("account_id", uuid_type, nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_players_account_id_accounts",
            "accounts",
            ["account_id"],
            ["account_id"],
            ondelete="SET NULL",
        )

    op.create_index("ix_players_account_id", "players", ["account_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_constraint("fk_players_account_id_accounts", type_="foreignkey")
        batch_op.drop_column("account_id")

    op.drop_index("ix_players_account_id", table_name="players")
    op.drop_index("ix_magic_links_account_id", table_name="magic_links")
    op.drop_index("ix_magic_links_guest_player_id", table_name="magic_links")
    op.drop_index("ix_magic_links_email", table_name="magic_links")
    op.drop_table("magic_links")

    op.drop_table("accounts")
