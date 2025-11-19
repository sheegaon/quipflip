"""add party mode tables

This migration adds tables for Party Mode feature:
- party_sessions: Track party match state and phase
- party_participants: Track players in each session
- party_rounds: Link rounds to party sessions
- party_phrasesets: Link phrasesets to party sessions

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3g4h5i6
Create Date: 2025-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from backend.migrations.util import get_uuid_type, get_uuid_default, get_timestamp_default


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd1e2f3g4h5i6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Party Mode tables."""
    uuid = get_uuid_type()
    uuid_default = get_uuid_default()
    timestamp_default = get_timestamp_default()

    # Create party_sessions table
    op.create_table(
        'party_sessions',
        sa.Column('session_id', uuid, primary_key=True, server_default=uuid_default),
        sa.Column('party_code', sa.String(length=8), unique=True, nullable=False),
        sa.Column('host_player_id', uuid, sa.ForeignKey('qf_players.player_id', ondelete='CASCADE'), nullable=False),

        # Configuration
        sa.Column('min_players', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_players', sa.Integer(), nullable=False, server_default='8'),
        sa.Column('prompts_per_player', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('copies_per_player', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('votes_per_player', sa.Integer(), nullable=False, server_default='3'),

        # Phase tracking
        sa.Column('current_phase', sa.String(length=20), nullable=False, server_default='LOBBY'),
        sa.Column('phase_started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('phase_expires_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # Status
        sa.Column('status', sa.String(length=20), nullable=False, server_default='OPEN'),
        sa.Column('locked_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Create indexes for party_sessions
    op.create_index('idx_party_sessions_code', 'party_sessions', ['party_code'])
    op.create_index('idx_party_sessions_status', 'party_sessions', ['status', 'created_at'])
    op.create_index('idx_party_sessions_host', 'party_sessions', ['host_player_id'])

    # Create party_participants table
    op.create_table(
        'party_participants',
        sa.Column('participant_id', uuid, primary_key=True, server_default=uuid_default),
        sa.Column('session_id', uuid, sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('player_id', uuid, sa.ForeignKey('qf_players.player_id', ondelete='CASCADE'), nullable=False),

        # Status tracking
        sa.Column('status', sa.String(length=20), nullable=False, server_default='JOINED'),
        sa.Column('is_host', sa.Boolean(), nullable=False, server_default='false'),

        # Progress tracking
        sa.Column('prompts_submitted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('copies_submitted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('votes_submitted', sa.Integer(), nullable=False, server_default='0'),

        # Metadata
        sa.Column('joined_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column('ready_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_activity_at', sa.TIMESTAMP(timezone=True), nullable=True),

        # Unique constraint defined inline for SQLite compatibility
        sa.UniqueConstraint('session_id', 'player_id', name='uq_party_participants_session_player'),
    )

    # Create indexes for party_participants
    op.create_index('idx_party_participants_session', 'party_participants', ['session_id'])
    op.create_index('idx_party_participants_player', 'party_participants', ['player_id'])
    op.create_index('idx_party_participants_status', 'party_participants', ['session_id', 'status'])

    # Create party_rounds table
    op.create_table(
        'party_rounds',
        sa.Column('party_round_id', uuid, primary_key=True, server_default=uuid_default),
        sa.Column('session_id', uuid, sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('round_id', uuid, sa.ForeignKey('qf_rounds.round_id', ondelete='CASCADE'), nullable=False),
        sa.Column('participant_id', uuid, sa.ForeignKey('party_participants.participant_id', ondelete='CASCADE'), nullable=False),

        # Round classification
        sa.Column('round_type', sa.String(length=10), nullable=False),
        sa.Column('phase', sa.String(length=20), nullable=False),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),

        # Unique constraint defined inline for SQLite compatibility
        sa.UniqueConstraint('session_id', 'round_id', name='uq_party_rounds_session_round'),
    )

    # Create indexes for party_rounds
    op.create_index('idx_party_rounds_session', 'party_rounds', ['session_id', 'phase'])
    op.create_index('idx_party_rounds_participant', 'party_rounds', ['participant_id'])
    op.create_index('idx_party_rounds_round', 'party_rounds', ['round_id'])

    # Create party_phrasesets table
    op.create_table(
        'party_phrasesets',
        sa.Column('party_phraseset_id', uuid, primary_key=True, server_default=uuid_default),
        sa.Column('session_id', uuid, sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('phraseset_id', uuid, sa.ForeignKey('qf_phrasesets.phraseset_id', ondelete='CASCADE'), nullable=False),

        # Metadata
        sa.Column('created_in_phase', sa.String(length=20), nullable=False),
        sa.Column('available_for_voting', sa.Boolean(), nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=timestamp_default),

        # Unique constraint defined inline for SQLite compatibility
        sa.UniqueConstraint('session_id', 'phraseset_id', name='uq_party_phrasesets_session_phraseset'),
    )

    # Create indexes for party_phrasesets
    op.create_index('idx_party_phrasesets_session', 'party_phrasesets', ['session_id', 'available_for_voting'])
    op.create_index('idx_party_phrasesets_phraseset', 'party_phrasesets', ['phraseset_id'])


def downgrade() -> None:
    """Drop Party Mode tables."""
    op.drop_table('party_phrasesets')
    op.drop_table('party_rounds')
    op.drop_table('party_participants')
    op.drop_table('party_sessions')
