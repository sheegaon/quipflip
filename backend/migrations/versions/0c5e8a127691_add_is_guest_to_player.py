"""add_is_guest_to_player

Revision ID: 0c5e8a127691
Revises: 9d0b8cb0461d
Create Date: 2025-10-29 23:48:38.157764

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c5e8a127691'
down_revision: Union[str, None] = '9d0b8cb0461d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_guest column to players table
    # Use server_default for compatibility with both PostgreSQL and SQLite
    op.add_column('players', sa.Column('is_guest', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    # Remove is_guest column from players table
    op.drop_column('players', 'is_guest')
