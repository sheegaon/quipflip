"""Add notifications table

Revision ID: 001_add_notifications
Revises: 8c3d123b7f18
Create Date: 2025-01-15 10:00:00.000000

"""
from collections.abc import Sequence
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_add_notifications'
down_revision = '8c3d123b7f18'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _uuid_column() -> sa.types.TypeEngine[Any]:
    """Utility to create UUID column compatible with SQLite and Postgres."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"
    if dialect_name == "postgresql":
        return sa.UUID()
    return sa.String(length=36)


def upgrade() -> None:
    uuid_type = _uuid_column()

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('notification_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('phraseset_id', uuid_type, nullable=False),
        sa.Column('actor_player_id', uuid_type, nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['phraseset_id'], ['phrasesets.phraseset_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('notification_id')
    )

    # Create indexes
    op.create_index('ix_notifications_player_created', 'notifications', ['player_id', 'created_at'])
    op.create_index('ix_notifications_phraseset', 'notifications', ['phraseset_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_notifications_phraseset', table_name='notifications')
    op.drop_index('ix_notifications_player_created', table_name='notifications')

    # Drop table
    op.drop_table('notifications')
