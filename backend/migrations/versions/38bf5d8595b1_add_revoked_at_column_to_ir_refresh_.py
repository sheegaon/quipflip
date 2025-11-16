"""Add revoked_at column to ir_refresh_tokens

Revision ID: 38bf5d8595b1
Revises: add_ir_002
Create Date: 2025-11-16 17:03:56.129751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38bf5d8595b1'
down_revision: Union[str, None] = 'add_ir_002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add revoked_at column to ir_refresh_tokens table
    op.add_column('ir_refresh_tokens',
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    # Remove revoked_at column from ir_refresh_tokens table
    op.drop_column('ir_refresh_tokens', 'revoked_at')
