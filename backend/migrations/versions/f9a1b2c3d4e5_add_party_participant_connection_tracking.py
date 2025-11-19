"""add party participant connection tracking

This migration adds connection tracking fields to party_participants table:
- last_activity_at: Make non-nullable with default (was nullable)
- disconnected_at: Track when participant disconnected
- connection_status: Track connection state ('connected' or 'disconnected')

These fields enable inactive player detection and removal.

Revision ID: f9a1b2c3d4e5
Revises: e7f8a9b0c1d2
Create Date: 2025-11-19 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_timestamp_default


# revision identifiers, used by Alembic.
revision: str = 'f9a1b2c3d4e5'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add connection tracking columns to party_participants."""
    timestamp_default = get_timestamp_default()

    # Detect database dialect for SQLite-specific handling
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Add disconnected_at column (nullable)
    op.add_column(
        'party_participants',
        sa.Column('disconnected_at', sa.TIMESTAMP(timezone=True), nullable=True)
    )

    # Add connection_status column with default 'connected'
    op.add_column(
        'party_participants',
        sa.Column('connection_status', sa.String(length=20), nullable=False, server_default='connected')
    )

    # Update existing last_activity_at to be non-nullable with NOW() default
    # First, set a value for any NULL rows (use joined_at as fallback)
    op.execute("""
        UPDATE party_participants
        SET last_activity_at = joined_at
        WHERE last_activity_at IS NULL
    """)

    # For SQLite, use batch mode to handle column alteration
    # For PostgreSQL, use standard ALTER COLUMN
    if dialect_name == 'sqlite':
        # SQLite requires batch operations for column modifications
        with op.batch_alter_table('party_participants') as batch_op:
            batch_op.alter_column(
                'last_activity_at',
                existing_type=sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=timestamp_default
            )
    else:
        # PostgreSQL supports ALTER COLUMN directly
        op.alter_column(
            'party_participants',
            'last_activity_at',
            existing_type=sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=timestamp_default
        )

    # Create index for efficient inactive participant queries
    op.create_index(
        'idx_party_participants_inactive',
        'party_participants',
        ['session_id', 'connection_status', 'last_activity_at']
    )


def downgrade() -> None:
    """Remove connection tracking columns from party_participants."""

    # Detect database dialect for SQLite-specific handling
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Drop index
    op.drop_index('idx_party_participants_inactive', table_name='party_participants')

    # Revert last_activity_at to nullable (remove default)
    if dialect_name == 'sqlite':
        # SQLite requires batch operations for column modifications
        with op.batch_alter_table('party_participants') as batch_op:
            batch_op.alter_column(
                'last_activity_at',
                existing_type=sa.TIMESTAMP(timezone=True),
                nullable=True,
                server_default=None
            )
    else:
        # PostgreSQL supports ALTER COLUMN directly
        op.alter_column(
            'party_participants',
            'last_activity_at',
            existing_type=sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=None
        )

    # Drop new columns
    op.drop_column('party_participants', 'connection_status')
    op.drop_column('party_participants', 'disconnected_at')
