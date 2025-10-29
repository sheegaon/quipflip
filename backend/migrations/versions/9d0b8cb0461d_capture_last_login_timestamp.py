"""Capture precise last login timestamps

Revision ID: 9d0b8cb0461d
Revises: 810c1bfc5a57
Create Date: 2025-11-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d0b8cb0461d'
down_revision: Union[str, None] = '810c1bfc5a57'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to store timezone-aware login timestamps."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.alter_column(
            'players',
            'last_login_date',
            existing_type=sa.Date(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
            postgresql_using="timezone('UTC', last_login_date::timestamp)",
        )
    else:
        with op.batch_alter_table('players', schema=None) as batch_op:
            batch_op.alter_column(
                'last_login_date',
                existing_type=sa.Date(),
                type_=sa.DateTime(timezone=True),
                existing_nullable=True,
            )


def downgrade() -> None:
    """Revert login timestamps back to date-only storage."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'postgresql':
        op.alter_column(
            'players',
            'last_login_date',
            existing_type=sa.DateTime(timezone=True),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using='last_login_date::date',
        )
    else:
        with op.batch_alter_table('players', schema=None) as batch_op:
            batch_op.alter_column(
                'last_login_date',
                existing_type=sa.DateTime(timezone=True),
                type_=sa.Date(),
                existing_nullable=True,
            )
