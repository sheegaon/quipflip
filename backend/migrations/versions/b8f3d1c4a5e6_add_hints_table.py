"""add hints table for AI-generated copy assistance

Revision ID: b8f3d1c4a5e6
Revises: e6b0d1f2c3a4
Create Date: 2025-11-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b8f3d1c4a5e6"
down_revision: Union[str, None] = "e6b0d1f2c3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_column():
    """Return a UUID-compatible column for the current database dialect."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"
    if dialect_name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def _json_column():
    """Return a JSON-capable column that works for SQLite and PostgreSQL."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"
    if dialect_name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON().with_variant(sa.Text(), "sqlite")


def upgrade() -> None:
    """Create hints table for caching AI-generated copy suggestions."""
    uuid = _uuid_column()
    json_type = _json_column()

    op.create_table(
        "hints",
        sa.Column("hint_id", uuid, nullable=False),
        sa.Column("prompt_round_id", uuid, nullable=False),
        sa.Column("hint_phrases", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generation_provider", sa.String(length=20), nullable=False),
        sa.Column("generation_model", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["prompt_round_id"],
            ["rounds.round_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("hint_id"),
        sa.UniqueConstraint("prompt_round_id", name="uq_hints_prompt_round"),
    )
    op.create_index(
        "ix_hints_prompt_round_id_created",
        "hints",
        ["prompt_round_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop hints table."""
    op.drop_index("ix_hints_prompt_round_id_created", table_name="hints")
    op.drop_table("hints")

