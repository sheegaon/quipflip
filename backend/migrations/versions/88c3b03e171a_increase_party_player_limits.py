"""increase party player limits

Revision ID: 88c3b03e171a
Revises: f9a1b2c3d4e5
Create Date: 2025-11-19 16:40:17.229621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88c3b03e171a'
down_revision: Union[str, None] = 'f9a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Increase party session min/max player defaults to 6-9."""
    with op.batch_alter_table('party_sessions') as batch_op:
        batch_op.alter_column(
            'min_players',
            existing_type=sa.Integer(),
            server_default='6',
        )
        batch_op.alter_column(
            'max_players',
            existing_type=sa.Integer(),
            server_default='9',
        )

    op.execute(sa.text("UPDATE party_sessions SET min_players = 6 WHERE min_players < 6"))
    op.execute(sa.text("UPDATE party_sessions SET max_players = 9 WHERE max_players < 9"))


def downgrade() -> None:
    with op.batch_alter_table('party_sessions') as batch_op:
        batch_op.alter_column(
            'min_players',
            existing_type=sa.Integer(),
            server_default='3',
        )
        batch_op.alter_column(
            'max_players',
            existing_type=sa.Integer(),
            server_default='8',
        )

    op.execute(sa.text("UPDATE party_sessions SET min_players = 3 WHERE min_players > 3"))
    op.execute(sa.text("UPDATE party_sessions SET max_players = 8 WHERE max_players > 8"))
