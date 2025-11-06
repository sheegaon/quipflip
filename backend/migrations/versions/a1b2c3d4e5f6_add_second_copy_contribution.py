"""add second_copy_contribution

This migration also merges two parallel development branches from debug-1105.

Revision ID: a1b2c3d4e5f6
Revises: e9a8b7c6d5f4, e6b0d1f2c3a4
Create Date: 2025-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = ('e9a8b7c6d5f4', 'e6b0d1f2c3a4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add second_copy_contribution column to phrasesets table
    # This tracks additional flipcoins contributed when a player submits both copies
    # Value is 0 for normal case (2 different players) or 50 when same player submits both copies
    op.add_column('phrasesets', sa.Column('second_copy_contribution', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove second_copy_contribution column
    op.drop_column('phrasesets', 'second_copy_contribution')
