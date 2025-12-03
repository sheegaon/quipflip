"""Add ThinkLink daily state and config tables.

Revision ID: tl_002
Revises: tl_001
Create Date: 2025-12-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_timestamp_default, get_uuid_type

# revision identifiers, used by Alembic.
revision: str = 'tl_002'
down_revision: Union[str, None] = 'tl_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = get_uuid_type()
    timestamp_default = get_timestamp_default()

    op.create_table(
        'tl_system_config',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column('updated_by', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    op.create_table(
        'tl_player_daily_states',
        sa.Column('player_id', uuid, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('free_captions_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('player_id', 'date')
    )
    op.create_index('ix_tl_player_daily_state_date', 'tl_player_daily_states', ['date'], unique=False)

    op.create_table(
        'tl_daily_bonuses',
        sa.Column('bonus_id', uuid, nullable=False),
        sa.Column('player_id', uuid, nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column('date', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('bonus_id'),
        sa.UniqueConstraint('player_id', 'date', name='uq_tl_player_daily_bonus'),
    )
    op.create_index('ix_tl_daily_bonuses_player_id', 'tl_daily_bonuses', ['player_id'], unique=False)
    op.create_index('ix_tl_daily_bonuses_date', 'tl_daily_bonuses', ['date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tl_daily_bonuses_date', table_name='tl_daily_bonuses')
    op.drop_index('ix_tl_daily_bonuses_player_id', table_name='tl_daily_bonuses')
    op.drop_table('tl_daily_bonuses')

    op.drop_index('ix_tl_player_daily_state_date', table_name='tl_player_daily_states')
    op.drop_table('tl_player_daily_states')

    op.drop_table('tl_system_config')
