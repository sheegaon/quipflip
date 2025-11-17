"""Add revoked_at column to ir_refresh_tokens table.

Revision ID: add_ir_003
Revises: add_ir_002
Create Date: 2025-11-17

This migration adds the missing revoked_at column to the ir_refresh_tokens table.
This column is required for token revocation tracking in the JWT authentication system.

Note: The 002_add_ir_tables migration was updated in commit dc81959 to include
revoked_at in the initial table creation. This migration handles the case where
production databases were created with the older version of 002_add_ir_tables
(before revoked_at was added).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_ir_003"
down_revision: Union[str, None] = "add_ir_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add revoked_at column to ir_refresh_tokens if it doesn't exist."""
    # Check if column already exists (for environments that have the updated 002_add_ir_tables)
    inspector = sa.inspect(op.get_context().bind)
    columns = [col['name'] for col in inspector.get_columns('ir_refresh_tokens')]

    if 'revoked_at' not in columns:
        op.add_column(
            'ir_refresh_tokens',
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    """Remove revoked_at column from ir_refresh_tokens."""
    inspector = sa.inspect(op.get_context().bind)
    columns = [col['name'] for col in inspector.get_columns('ir_refresh_tokens')]

    if 'revoked_at' in columns:
        op.drop_column('ir_refresh_tokens', 'revoked_at')
