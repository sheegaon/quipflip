"""remove_legacy_api_key_column

Revision ID: 7f6352e4d4e3
Revises: 37c3bd779d3d
Create Date: 2025-10-19 22:36:41.582820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f6352e4d4e3'
down_revision: Union[str, None] = '37c3bd779d3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove legacy api_key column - JWT authentication is now used exclusively
    op.drop_index('ix_players_api_key', table_name='players')
    op.drop_column('players', 'api_key')


def downgrade() -> None:
    # Restore api_key column for rollback
    op.add_column('players', sa.Column('api_key', sa.String(36), nullable=True, unique=True))
    # Populate with UUIDs for existing players
    op.execute("UPDATE players SET api_key = lower(hex(randomblob(16))) WHERE api_key IS NULL")
    # Make it non-nullable after populating
    op.alter_column('players', 'api_key', nullable=False)
    op.create_index('ix_players_api_key', 'players', ['api_key'], unique=True)
