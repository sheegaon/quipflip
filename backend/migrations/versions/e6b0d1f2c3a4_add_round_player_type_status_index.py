"""add composite index for round player/type/status lookups

Revision ID: e6b0d1f2c3a4
Revises: 1c2b3a4d5e67
Create Date: 2025-11-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e6b0d1f2c3a4"
down_revision: Union[str, None] = "1c2b3a4d5e67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite index to accelerate per-player round lookups."""
    op.create_index(
        "ix_rounds_player_type_status",
        "rounds",
        ["player_id", "round_type", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite index for player/type/status lookups."""
    op.drop_index("ix_rounds_player_type_status", table_name="rounds")
