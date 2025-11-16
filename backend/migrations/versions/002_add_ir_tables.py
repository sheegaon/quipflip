"""Add Initial Reaction (IR) game tables.

Revision ID: add_ir_002
Revises: rename_qf_001
Create Date: 2025-01-15

This migration creates all tables needed for the Initial Reaction game,
a separate game that coexists with Quipflip in the same database.
IR uses the ir_ table prefix for complete separation.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from backend.migrations.util import get_uuid_type


# revision identifiers, used by Alembic.
revision: str = "add_ir_002"
down_revision: Union[str, None] = "rename_qf_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create Initial Reaction tables."""
    uuid_type = get_uuid_type()

    # ir_players table - IR-specific player accounts
    op.create_table(
        'ir_players',
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('username', sa.String(80), nullable=False, unique=True),
        sa.Column('username_canonical', sa.String(80), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('wallet', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('vault', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_login_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_guest', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consecutive_incorrect_votes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('vote_lockout_until', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('player_id'),
        sa.UniqueConstraint('username_canonical', name='uq_ir_players_username_canonical'),
    )
    op.create_index('ix_ir_players_username', 'ir_players', ['username'])

    # ir_backronym_sets table - Backronym competition instances
    op.create_table(
        'ir_backronym_sets',
        sa.Column('set_id', uuid_type, nullable=False),
        sa.Column('word', sa.String(5), nullable=False),
        sa.Column('mode', sa.String(10), nullable=False, server_default='rapid'),
        sa.Column('status', sa.String(10), nullable=False, server_default='open'),
        sa.Column('entry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('vote_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('non_participant_vote_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pool', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('vote_contributions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('non_participant_payouts_paid', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('creator_final_pool', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_participant_joined_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_human_entry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_human_vote_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('set_id'),
    )
    op.create_index('ix_ir_set_status_created', 'ir_backronym_sets', ['status', 'created_at'])
    op.create_index('ix_ir_set_mode_status', 'ir_backronym_sets', ['mode', 'status'])
    op.create_index('ix_ir_set_finalized_at', 'ir_backronym_sets', ['finalized_at'])
    op.create_index('ix_ir_set_word_status', 'ir_backronym_sets', ['word', 'status'])
    op.create_index('ix_ir_set_last_human_vote', 'ir_backronym_sets', ['last_human_vote_at'])

    # ir_backronym_entries table - Individual backronym submissions
    op.create_table(
        'ir_backronym_entries',
        sa.Column('entry_id', uuid_type, nullable=False),
        sa.Column('set_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('backronym_text', sa.JSON(), nullable=False),
        sa.Column('is_ai', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('vote_share_pct', sa.Integer(), nullable=True),
        sa.Column('received_votes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('forfeited_to_vault', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('entry_id'),
        sa.ForeignKeyConstraint(['set_id'], ['ir_backronym_sets.set_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['ir_players.player_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('player_id', 'set_id', name='uq_ir_entry_player_set'),
    )
    op.create_index('ix_ir_entry_set', 'ir_backronym_entries', ['set_id'])
    op.create_index('ix_ir_entry_player_set', 'ir_backronym_entries', ['player_id', 'set_id'])
    op.create_index('ix_ir_entry_submitted', 'ir_backronym_entries', ['submitted_at'])

    # ir_backronym_votes table - Votes on backronym entries
    op.create_table(
        'ir_backronym_votes',
        sa.Column('vote_id', uuid_type, nullable=False),
        sa.Column('set_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('chosen_entry_id', uuid_type, nullable=False),
        sa.Column('is_participant_voter', sa.Boolean(), nullable=False),
        sa.Column('is_ai', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_correct_popular', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('vote_id'),
        sa.ForeignKeyConstraint(['set_id'], ['ir_backronym_sets.set_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['ir_players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['chosen_entry_id'], ['ir_backronym_entries.entry_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('player_id', 'set_id', name='uq_ir_vote_player_set'),
    )
    op.create_index('ix_ir_vote_set', 'ir_backronym_votes', ['set_id'])
    op.create_index('ix_ir_vote_player_set', 'ir_backronym_votes', ['player_id', 'set_id'])
    op.create_index('ix_ir_vote_entry', 'ir_backronym_votes', ['chosen_entry_id'])
    op.create_index('ix_ir_vote_created', 'ir_backronym_votes', ['created_at'])

    # ir_transactions table - Ledger for wallet/vault changes
    op.create_table(
        'ir_transactions',
        sa.Column('transaction_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('wallet_type', sa.String(20), nullable=False, server_default='wallet'),
        sa.Column('reference_id', uuid_type, nullable=True),
        sa.Column('wallet_balance_after', sa.Integer(), nullable=True),
        sa.Column('vault_balance_after', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('transaction_id'),
        sa.ForeignKeyConstraint(['player_id'], ['ir_players.player_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_ir_transaction_player_id', 'ir_transactions', ['player_id'])
    op.create_index('ix_ir_transaction_type', 'ir_transactions', ['type'])
    op.create_index('ix_ir_transaction_reference_id', 'ir_transactions', ['reference_id'])
    op.create_index('ix_ir_transaction_created_at', 'ir_transactions', ['created_at'])
    op.create_index('ix_ir_transaction_player_created', 'ir_transactions', ['player_id', 'created_at'])

    # ir_result_views table - Track result viewing and payout idempotency
    op.create_table(
        'ir_result_views',
        sa.Column('view_id', uuid_type, nullable=False),
        sa.Column('set_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('result_viewed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('payout_amount', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('viewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_viewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('result_viewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('view_id'),
        sa.ForeignKeyConstraint(['set_id'], ['ir_backronym_sets.set_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['ir_players.player_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('player_id', 'set_id', name='uq_ir_result_view_player_set'),
    )
    op.create_index('ix_ir_result_view_set', 'ir_result_views', ['set_id'])
    op.create_index('ix_ir_result_view_player', 'ir_result_views', ['player_id'])
    op.create_index('ix_ir_result_view_result_viewed', 'ir_result_views', ['result_viewed'])

    # ir_refresh_tokens table - JWT refresh tokens for IR auth
    op.create_table(
        'ir_refresh_tokens',
        sa.Column('token_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('token_id'),
        sa.ForeignKeyConstraint(['player_id'], ['ir_players.player_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('token_hash', name='uq_ir_refresh_token_hash'),
    )
    op.create_index('ix_ir_refresh_tokens_player', 'ir_refresh_tokens', ['player_id'])
    op.create_index('ix_ir_refresh_tokens_expires', 'ir_refresh_tokens', ['expires_at'])

    # ir_daily_bonuses table - Daily login bonus tracking
    op.create_table(
        'ir_daily_bonuses',
        sa.Column('bonus_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('bonus_amount', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('bonus_id'),
        sa.ForeignKeyConstraint(['player_id'], ['ir_players.player_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('player_id', 'date', name='uq_ir_daily_bonus_player_date'),
    )
    op.create_index('ix_ir_daily_bonus_player', 'ir_daily_bonuses', ['player_id'])
    op.create_index('ix_ir_daily_bonus_date', 'ir_daily_bonuses', ['date'])

    # ir_ai_phrase_cache table - Cache for AI-generated backronym words
    # Must be created BEFORE ir_ai_metrics because ir_ai_metrics has a foreign key to this table
    op.create_table(
        'ir_ai_phrase_cache',
        sa.Column('cache_id', uuid_type, nullable=False),
        sa.Column('prompt_round_id', uuid_type, nullable=False, unique=True),
        sa.Column('validated_phrases', sa.JSON(), nullable=False),
        sa.Column('generation_provider', sa.String(50), nullable=False),
        sa.Column('generation_model', sa.String(100), nullable=False),
        sa.Column('used_for_backup_copy', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('used_for_hints', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('cache_id'),
        sa.ForeignKeyConstraint(['prompt_round_id'], ['ir_backronym_sets.set_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_ir_ai_phrase_cache_prompt_round_id', 'ir_ai_phrase_cache', ['prompt_round_id'])
    op.create_index('ix_ir_ai_phrase_cache_created_at', 'ir_ai_phrase_cache', ['created_at'])

    # ir_ai_metrics table - Track AI operation metrics and performance
    op.create_table(
        'ir_ai_metrics',
        sa.Column('metric_id', uuid_type, nullable=False),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('validation_passed', sa.Boolean(), nullable=True),
        sa.Column('vote_correct', sa.Boolean(), nullable=True),
        sa.Column('cache_id', uuid_type, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('metric_id'),
        sa.ForeignKeyConstraint(['cache_id'], ['ir_ai_phrase_cache.cache_id'], ondelete='SET NULL'),
    )
    op.create_index('ix_ir_ai_metrics_operation_type', 'ir_ai_metrics', ['operation_type'])
    op.create_index('ix_ir_ai_metrics_provider', 'ir_ai_metrics', ['provider'])
    op.create_index('ix_ir_ai_metrics_success', 'ir_ai_metrics', ['success'])
    op.create_index('ix_ir_ai_metrics_created_at', 'ir_ai_metrics', ['created_at'])
    op.create_index('ix_ir_ai_metrics_operation_provider', 'ir_ai_metrics', ['operation_type', 'provider'])
    op.create_index('ix_ir_ai_metrics_created_at_success', 'ir_ai_metrics', ['created_at', 'success'])
    op.create_index('ix_ir_ai_metrics_cache_id', 'ir_ai_metrics', ['cache_id'])

    # ir_backronym_observer_guards table - Eligibility snapshot for non-participant voters
    op.create_table(
        'ir_backronym_observer_guards',
        sa.Column('set_id', uuid_type, nullable=False),
        sa.Column('first_participant_created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('set_id'),
        sa.ForeignKeyConstraint(['set_id'], ['ir_backronym_sets.set_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_ir_observer_guards_set', 'ir_backronym_observer_guards', ['set_id'])


def downgrade() -> None:
    """Drop Initial Reaction tables."""
    # Drop ir_ai_metrics BEFORE ir_ai_phrase_cache (has FK to ir_ai_phrase_cache)
    op.drop_table('ir_ai_metrics')
    op.drop_table('ir_ai_phrase_cache')
    op.drop_table('ir_daily_bonuses')
    op.drop_table('ir_refresh_tokens')
    op.drop_table('ir_result_views')
    op.drop_table('ir_transactions')
    op.drop_table('ir_backronym_votes')
    op.drop_table('ir_backronym_entries')
    op.drop_table('ir_backronym_observer_guards')
    op.drop_table('ir_backronym_sets')
    op.drop_table('ir_players')
