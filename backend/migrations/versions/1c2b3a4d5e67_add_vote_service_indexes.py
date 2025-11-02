"""add vote availability indexes

Revision ID: 1c2b3a4d5e67
Revises: 9f2d8a3b1c4e
Create Date: 2025-11-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c2b3a4d5e67'
down_revision: Union[str, None] = '9f2d8a3b1c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes to speed up vote availability queries."""
    op.create_index(
        'ix_votes_phraseset_player',
        'votes',
        ['phraseset_id', 'player_id'],
        unique=False,
    )
    op.create_index(
        'ix_phrasesets_status_fifth_vote_at',
        'phrasesets',
        ['status', 'fifth_vote_at'],
        unique=False,
    )
    op.create_index(
        'ix_phrasesets_status_third_vote_at',
        'phrasesets',
        ['status', 'third_vote_at'],
        unique=False,
    )
    op.create_index(
        'ix_phrasesets_status_created_at',
        'phrasesets',
        ['status', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite indexes for vote availability queries."""
    op.drop_index('ix_votes_phraseset_player', table_name='votes')
    op.drop_index('ix_phrasesets_status_fifth_vote_at', table_name='phrasesets')
    op.drop_index('ix_phrasesets_status_third_vote_at', table_name='phrasesets')
    op.drop_index('ix_phrasesets_status_created_at', table_name='phrasesets')
