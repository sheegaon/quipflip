"""add is_admin field to players

Revision ID: 588e85813c74
Revises: 8f4f4c1b7d92
Create Date: 2025-10-30 23:20:00.801977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '588e85813c74'
down_revision: Union[str, None] = '8f4f4c1b7d92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check if we're using SQLite or PostgreSQL
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # Add is_admin column with appropriate server_default
    if dialect_name == 'sqlite':
        # SQLite: Use string literal for server_default
        op.add_column(
            'players',
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0')
        )
    else:
        # PostgreSQL: Use text() for server_default
        op.add_column(
            'players',
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false'))
        )


def downgrade() -> None:
    op.drop_column('players', 'is_admin')
