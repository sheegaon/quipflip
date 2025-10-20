"""add_tutorial_fields_to_players

Revision ID: 37c3bd779d3d
Revises: 5c2dbcd09a92
Create Date: 2025-10-19 17:22:14.093135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37c3bd779d3d'
down_revision: Union[str, None] = '5c2dbcd09a92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tutorial tracking columns to players table
    # Use sa.text('false') for PostgreSQL compatibility instead of '0'
    op.add_column('players', sa.Column('tutorial_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('players', sa.Column('tutorial_progress', sa.String(length=20), nullable=False, server_default='not_started'))
    op.add_column('players', sa.Column('tutorial_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('players', sa.Column('tutorial_completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove tutorial columns
    op.drop_column('players', 'tutorial_completed_at')
    op.drop_column('players', 'tutorial_started_at')
    op.drop_column('players', 'tutorial_progress')
    op.drop_column('players', 'tutorial_completed')
