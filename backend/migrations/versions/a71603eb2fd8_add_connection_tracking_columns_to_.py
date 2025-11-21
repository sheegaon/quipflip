"""add connection tracking columns to party participants

This migration adds connection tracking fields that were missing from the table restoration:
- disconnected_at: Track when participant disconnected
- connection_status: Track connection state ('connected' or 'disconnected')

These columns were originally added in f9a1b2c3d4e5 but were lost when tables
were dropped and restored.

Revision ID: a71603eb2fd8
Revises: c1d2e3f4a5b6
Create Date: 2025-11-20 19:42:17.440489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a71603eb2fd8'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    try:
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade() -> None:
    """Add connection tracking columns to party_participants if they don't exist."""

    # Add disconnected_at column (nullable) if it doesn't exist
    if not _column_exists('party_participants', 'disconnected_at'):
        op.add_column(
            'party_participants',
            sa.Column('disconnected_at', sa.TIMESTAMP(timezone=True), nullable=True)
        )

    # Add connection_status column with default 'connected' if it doesn't exist
    if not _column_exists('party_participants', 'connection_status'):
        op.add_column(
            'party_participants',
            sa.Column('connection_status', sa.String(length=20), nullable=False, server_default='connected')
        )

    # Create index for efficient inactive participant queries if it doesn't exist
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('party_participants')]

    if 'idx_party_participants_inactive' not in existing_indexes:
        op.create_index(
            'idx_party_participants_inactive',
            'party_participants',
            ['session_id', 'connection_status', 'last_activity_at']
        )


def downgrade() -> None:
    """Remove connection tracking columns from party_participants."""

    # Drop index if it exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('party_participants')]

    if 'idx_party_participants_inactive' in existing_indexes:
        op.drop_index('idx_party_participants_inactive', table_name='party_participants')

    # Drop columns if they exist
    if _column_exists('party_participants', 'connection_status'):
        op.drop_column('party_participants', 'connection_status')

    if _column_exists('party_participants', 'disconnected_at'):
        op.drop_column('party_participants', 'disconnected_at')
