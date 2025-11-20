"""Restore party mode tables for active party feature

Revision ID: c1d2e3f4a5b6
Revises: 6f3b07d822b9
Create Date: 2025-11-20 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_uuid_default, get_uuid_type, get_timestamp_default

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = '6f3b07d822b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    """Check if table exists in database."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    if not _table_exists(table_name):
        return False
        
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Restore party mode tables that were previously removed."""
    uuid = get_uuid_type()
    uuid_default = get_uuid_default()
    timestamp_default = get_timestamp_default()

    # Create party_sessions table
    if not _table_exists('party_sessions'):
        op.create_table(
            'party_sessions',
            sa.Column('session_id', uuid, primary_key=True, server_default=uuid_default),
            sa.Column('party_code', sa.String(length=8), unique=True, nullable=False),
            sa.Column('host_player_id', uuid, sa.ForeignKey('qf_players.player_id', ondelete='CASCADE'), nullable=False),
            sa.Column('min_players', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('max_players', sa.Integer(), nullable=False, server_default='8'),
            sa.Column('prompts_per_player', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('copies_per_player', sa.Integer(), nullable=False, server_default='2'),
            sa.Column('votes_per_player', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('current_phase', sa.String(length=20), nullable=False, server_default='LOBBY'),
            sa.Column('phase_started_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('phase_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='OPEN'),
            sa.Column('locked_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),
            sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        )
        op.create_index('idx_party_sessions_code', 'party_sessions', ['party_code'])
        op.create_index('idx_party_sessions_status', 'party_sessions', ['status', 'created_at'])
        op.create_index('idx_party_sessions_host', 'party_sessions', ['host_player_id'])

    # Create party_participants table
    if not _table_exists('party_participants'):
        op.create_table(
            'party_participants',
            sa.Column('participant_id', uuid, primary_key=True, server_default=uuid_default),
            sa.Column('session_id', uuid, sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
            sa.Column('player_id', uuid, sa.ForeignKey('qf_players.player_id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='JOINED'),
            sa.Column('is_host', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('prompts_submitted', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('copies_submitted', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('votes_submitted', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('joined_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),
            sa.Column('ready_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('last_activity_at', sa.TIMESTAMP(timezone=True), nullable=True),
            sa.UniqueConstraint('session_id', 'player_id', name='uq_party_participants_session_player'),
        )
        op.create_index('idx_party_participants_session', 'party_participants', ['session_id'])
        op.create_index('idx_party_participants_player', 'party_participants', ['player_id'])
        op.create_index('idx_party_participants_status', 'party_participants', ['session_id', 'status'])

    # Create party_rounds table
    if not _table_exists('party_rounds'):
        op.create_table(
            'party_rounds',
            sa.Column('party_round_id', uuid, primary_key=True, server_default=uuid_default),
            sa.Column('session_id', uuid, sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
            sa.Column('round_id', uuid, sa.ForeignKey('qf_rounds.round_id', ondelete='CASCADE'), nullable=False),
            sa.Column('participant_id', uuid, sa.ForeignKey('party_participants.participant_id', ondelete='CASCADE'), nullable=False),
            sa.Column('round_type', sa.String(length=10), nullable=False),
            sa.Column('phase', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),
            sa.UniqueConstraint('session_id', 'round_id', name='uq_party_rounds_session_round'),
        )
        op.create_index('idx_party_rounds_session', 'party_rounds', ['session_id', 'phase'])
        op.create_index('idx_party_rounds_participant', 'party_rounds', ['participant_id'])
        op.create_index('idx_party_rounds_round', 'party_rounds', ['round_id'])

    # Create party_phrasesets table
    if not _table_exists('party_phrasesets'):
        op.create_table(
            'party_phrasesets',
            sa.Column('party_phraseset_id', uuid, primary_key=True, server_default=uuid_default),
            sa.Column('session_id', uuid, sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
            sa.Column('phraseset_id', uuid, sa.ForeignKey('qf_phrasesets.phraseset_id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_in_phase', sa.String(length=20), nullable=False),
            sa.Column('available_for_voting', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),
            sa.UniqueConstraint('session_id', 'phraseset_id', name='uq_party_phrasesets_session_phraseset'),
        )
        op.create_index('idx_party_phrasesets_session', 'party_phrasesets', ['session_id', 'available_for_voting'])
        op.create_index('idx_party_phrasesets_phraseset', 'party_phrasesets', ['phraseset_id'])

    # Ensure party_round_id column exists in qf_rounds table (should exist from previous migration)
    if not _column_exists('qf_rounds', 'party_round_id'):
        op.add_column('qf_rounds', sa.Column('party_round_id', uuid, nullable=True))
        op.create_foreign_key('fk_qf_rounds_party_round_id', 'qf_rounds', 'party_rounds', ['party_round_id'], ['party_round_id'])
        op.create_index('idx_qf_rounds_party_round_id', 'qf_rounds', ['party_round_id'])


def downgrade() -> None:
    """Remove party mode tables."""
    # Drop foreign key constraint and column from qf_rounds if it exists
    if _column_exists('qf_rounds', 'party_round_id'):
        op.drop_constraint('fk_qf_rounds_party_round_id', 'qf_rounds', type_='foreignkey')
        op.drop_index('idx_qf_rounds_party_round_id', table_name='qf_rounds')
        op.drop_column('qf_rounds', 'party_round_id')

    # Drop tables in reverse dependency order
    tables_to_drop = [
        'party_phrasesets',
        'party_rounds', 
        'party_participants',
        'party_sessions',
    ]

    for table_name in tables_to_drop:
        if _table_exists(table_name):
            op.drop_table(table_name)