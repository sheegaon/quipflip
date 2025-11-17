"""Add timer columns to ir_backronym_sets table.

Revision ID: add_ir_005
Revises: add_ir_004
Create Date: 2025-11-17

This migration adds transitions_to_voting_at and voting_finalized_at columns
to the ir_backronym_sets table to support timer logic for Rapid and Standard modes.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_ir_005"
down_revision: Union[str, None] = "add_ir_004"
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
    """Add timer columns to ir_backronym_sets if they don't exist."""
    connection = op.get_context().connection

    # Add transitions_to_voting_at column if it doesn't exist
    if not column_exists(connection, 'ir_backronym_sets', 'transitions_to_voting_at'):
        op.add_column(
            'ir_backronym_sets',
            sa.Column('transitions_to_voting_at', sa.DateTime(timezone=True), nullable=True)
        )

    # Add voting_finalized_at column if it doesn't exist
    if not column_exists(connection, 'ir_backronym_sets', 'voting_finalized_at'):
        op.add_column(
            'ir_backronym_sets',
            sa.Column('voting_finalized_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    """Remove timer columns from ir_backronym_sets."""
    connection = op.get_context().connection

    # Drop voting_finalized_at column if it exists
    if column_exists(connection, 'ir_backronym_sets', 'voting_finalized_at'):
        op.drop_column('ir_backronym_sets', 'voting_finalized_at')

    # Drop transitions_to_voting_at column if it exists
    if column_exists(connection, 'ir_backronym_sets', 'transitions_to_voting_at'):
        op.drop_column('ir_backronym_sets', 'transitions_to_voting_at')
