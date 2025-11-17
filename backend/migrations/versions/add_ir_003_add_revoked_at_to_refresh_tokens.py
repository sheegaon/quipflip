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


def column_exists(connection, table_name, column_name):
    """Check if a column exists in a table (works for both PostgreSQL and SQLite)."""
    # Get the database dialect
    dialect = connection.dialect.name

    if dialect == 'postgresql':
        # Use information_schema for PostgreSQL
        result = connection.execute(
            sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = :table_name AND column_name = :column_name
                )
            """),
            {"table_name": table_name, "column_name": column_name}
        )
        return result.scalar()
    elif dialect == 'sqlite':
        # Use PRAGMA for SQLite
        result = connection.execute(
            sa.text(f"PRAGMA table_info({table_name})")
        )
        columns = [row[1] for row in result.fetchall()]
        return column_name in columns
    else:
        # For other databases, assume column doesn't exist to be safe
        return False


def upgrade() -> None:
    """Add revoked_at column to ir_refresh_tokens if it doesn't exist."""
    connection = op.get_context().connection

    # Check if column already exists before attempting to add it
    if not column_exists(connection, 'ir_refresh_tokens', 'revoked_at'):
        op.add_column(
            'ir_refresh_tokens',
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    """Remove revoked_at column from ir_refresh_tokens."""
    connection = op.get_context().connection

    # Only drop if column exists
    if column_exists(connection, 'ir_refresh_tokens', 'revoked_at'):
        op.drop_column('ir_refresh_tokens', 'revoked_at')
