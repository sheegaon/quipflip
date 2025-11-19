"""merge balance migrations

This migration merges two parallel development branches:
- 37c3bd779d3e (make balance_after nullable)
- 8c3d123b7f18 (drop balance column)

Revision ID: d1e2f3g4h5i6
Revises: 37c3bd779d3e, 8c3d123b7f18
Create Date: 2025-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3g4h5i6'
down_revision: Union[str, Sequence[str], None] = ('37c3bd779d3e', '8c3d123b7f18')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no schema changes."""
    pass


def downgrade() -> None:
    """Merge migration - no schema changes."""
    pass
