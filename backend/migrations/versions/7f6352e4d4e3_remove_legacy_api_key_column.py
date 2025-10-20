"""remove_legacy_api_key_column

Revision ID: 7f6352e4d4e3
Revises: 37c3bd779d3d
Create Date: 2025-10-19 22:36:41.582820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid


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
    # Populate with UUIDs for existing players using Python for cross-database compatibility
    conn = op.get_bind()
    metadata = sa.MetaData()
    players = sa.Table('players', metadata,
                       sa.Column('player_id', sa.String(36), primary_key=True),
                       sa.Column('api_key', sa.String(36)))

    player_ids = conn.execute(sa.select(players.c.player_id).where(players.c.api_key.is_(None))).scalars().all()
    for player_id in player_ids:
        conn.execute(
            sa.update(players)
            .where(players.c.player_id == player_id)
            .values(api_key=str(uuid.uuid4()))
        )
    # Make it non-nullable after populating
    op.alter_column('players', 'api_key', nullable=False)
    op.create_index('ix_players_api_key', 'players', ['api_key'], unique=True)
