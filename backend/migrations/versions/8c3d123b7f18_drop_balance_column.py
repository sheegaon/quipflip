"""drop_balance_column

Revision ID: 8c3d123b7f18
Revises: def456abc123
Create Date: 2025-11-13 08:17:06.537272

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c3d123b7f18'
down_revision: Union[str, None] = 'def456abc123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the legacy balance column from players table.

    The balance column is no longer used since we migrated to wallet/vault system.
    """
    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.drop_column('balance')


def downgrade() -> None:
    """Re-add the balance column if we need to roll back."""
    with op.batch_alter_table('players', schema=None) as batch_op:
        batch_op.add_column(sa.Column('balance', sa.Integer(), nullable=False, server_default='0'))
