"""add composite index for ai_metrics analytics

Revision ID: f0703498ff94
Revises: 7f6352e4d4e3
Create Date: 2025-10-22 20:30:41.348861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0703498ff94'
down_revision: Union[str, None] = '7f6352e4d4e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add composite index for operation_type + created_at for analytics queries
    op.create_index(
        'ix_ai_metrics_op_created',
        'ai_metrics',
        ['operation_type', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    # Remove composite index
    op.drop_index('ix_ai_metrics_op_created', table_name='ai_metrics')
