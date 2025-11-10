"""remove pseudonym fields

Revision ID: a1b2c3d4e5f7
Revises: 3b9164a1de94
Create Date: 2025-11-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = '3b9164a1de94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the pseudonym index first
    op.drop_index('ix_players_pseudonym', table_name='players')

    # Drop the pseudonym columns
    op.drop_column('players', 'pseudonym_canonical')
    op.drop_column('players', 'pseudonym')


def downgrade() -> None:
    # Re-add pseudonym columns
    op.add_column('players', sa.Column('pseudonym', sa.String(length=80), nullable=False, server_default=''))
    op.add_column('players', sa.Column('pseudonym_canonical', sa.String(length=80), nullable=False, server_default=''))

    # Recreate the index
    op.create_index('ix_players_pseudonym', 'players', ['pseudonym'], unique=False)

    # Populate pseudonyms from usernames for any existing players
    op.execute("""
        UPDATE players
        SET pseudonym = username,
            pseudonym_canonical = username_canonical
        WHERE pseudonym = '' OR pseudonym_canonical = ''
    """)
