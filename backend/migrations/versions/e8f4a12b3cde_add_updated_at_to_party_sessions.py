"""Add updated_at column to party_sessions.

Revision ID: e8f4a12b3cde
Revises: 001_add_notifications
Create Date: 2025-02-15 12:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8f4a12b3cde"
down_revision: Union[str, tuple[str, ...], None] = (
    "c8c6d5a2a7b0",
    "001_add_notifications",
)
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "party_sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE party_sessions SET updated_at = created_at WHERE updated_at IS NULL"
        )
    )
    op.alter_column(
        "party_sessions",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("party_sessions", "updated_at")
