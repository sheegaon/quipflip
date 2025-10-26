"""add variable prize pool tracking

Revision ID: e9a8b7c6d5f4
Revises: f0703498ff94
Create Date: 2025-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9a8b7c6d5f4'
down_revision: Union[str, None] = 'f0703498ff94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add vote contribution tracking columns to phrasesets table
    op.add_column('phrasesets', sa.Column('vote_contributions', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('phrasesets', sa.Column('vote_payouts_paid', sa.Integer(), nullable=False, server_default='0'))

    # Update total_pool default to match new prize_pool_base
    # Note: Existing records will keep their current total_pool value
    # New records will use the updated default


def downgrade() -> None:
    # Remove vote contribution tracking columns
    op.drop_column('phrasesets', 'vote_payouts_paid')
    op.drop_column('phrasesets', 'vote_contributions')
