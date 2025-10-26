"""Add system_config table for dynamic configuration

Revision ID: fc8705dc196e
Revises: e9a8b7c6d5f4
Create Date: 2025-10-26 15:54:20.359962

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc8705dc196e'
down_revision: Union[str, None] = 'e9a8b7c6d5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_config',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_by', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('system_config')
