"""Add original_phrase column to ir_ai_phrase_cache table.

Revision ID: add_ir_004
Revises: add_ir_003
Create Date: 2025-11-17

This migration adds the missing original_phrase column to the ir_ai_phrase_cache table.
This column is required for caching word usage and preventing duplicate word selection.

Note: The 002_add_ir_tables migration was updated to include original_phrase in the
initial table creation. This migration handles the case where production databases
were created with the older version of 002_add_ir_tables (before original_phrase was added).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_ir_004"
down_revision: Union[str, None] = "add_ir_003"
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
    """Add original_phrase column to ir_ai_phrase_cache if it doesn't exist."""
    connection = op.get_context().connection

    # Check if column already exists before attempting to add it
    if not column_exists(connection, 'ir_ai_phrase_cache', 'original_phrase'):
        # Add the column as nullable first to handle existing data
        op.add_column(
            'ir_ai_phrase_cache',
            sa.Column('original_phrase', sa.String(5), nullable=True)
        )

        # Update existing rows with a placeholder value (if any exist)
        # Since this is a cache table, old entries without original_phrase can be left as NULL
        # New entries will always have original_phrase populated by the application code


def downgrade() -> None:
    """Remove original_phrase column from ir_ai_phrase_cache."""
    connection = op.get_context().connection

    # Only drop if column exists
    if column_exists(connection, 'ir_ai_phrase_cache', 'original_phrase'):
        op.drop_column('ir_ai_phrase_cache', 'original_phrase')
