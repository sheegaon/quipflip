"""merge hints and second copy branches

This migration merges two parallel development branches:
- b8f3d1c4a5e6 (add hints table)
- a1b2c3d4e5f6 (add second_copy_contribution)

Revision ID: c7d8e9f0a1b2
Revises: b8f3d1c4a5e6, a1b2c3d4e5f6
Create Date: 2025-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = ('b8f3d1c4a5e6', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration - no schema changes."""
    pass


def downgrade() -> None:
    """Merge migration - no schema changes."""
    pass
