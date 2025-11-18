"""make_balance_after_nullable

Revision ID: 37c3bd779d3e
Revises: add_ir_006
Create Date: 2025-11-18 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37c3bd779d3e'
down_revision: Union[str, None] = 'add_ir_006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make balance_after column nullable in qf_transactions
    # This column is deprecated and no longer populated by the code
    op.alter_column('qf_transactions', 'balance_after',
               existing_type=sa.Integer(),
               nullable=True)


def downgrade() -> None:
    # Restore balance_after as NOT NULL (would need default value)
    op.alter_column('qf_transactions', 'balance_after',
               existing_type=sa.Integer(),
               nullable=False)
