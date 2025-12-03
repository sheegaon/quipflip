"""Create initial ThinkLink schema

Revision ID: tl_001
Revises: unify_player_001
Create Date: 2025-12-02

This migration creates the core ThinkLink tables:
- tl_player_data: Game-specific player wallet, vault, and tutorial tracking
- tl_prompt: Prompt corpus with embeddings
- tl_answer: Answer corpus with embeddings and cluster assignments
- tl_cluster: Semantic clusters with centroid embeddings
- tl_round: Round state with snapshots
- tl_guess: Guess history with embeddings and match results
- tl_transaction: Balance transaction ledger
- tl_challenge: Head-to-head challenge structure (v2, no implementation in v1)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from backend.migrations.util import get_timestamp_default, get_uuid_type

# revision identifiers, used by Alembic.
revision: str = 'tl_001'
down_revision: Union[str, None] = 'unify_player_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_column():
    """Return JSON column compatible with SQLite and Postgres."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"

    if dialect_name == "postgresql":
        return sa.JSON()

    # SQLite stores JSON as TEXT but SQLAlchemy will handle serialization
    return sa.JSON().with_variant(sa.Text(), "sqlite")


def _vector_column(dim: int = 1536):
    """Return vector column, using TEXT for SQLite compatibility."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"

    if dialect_name == "postgresql":
        # Use pgvector extension
        try:
            # Enable pgvector extension
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception:
            pass  # Extension might already exist or not available

        return sa.JSON()  # pgvector will be handled by native type

    # SQLite: store embeddings as JSON
    return sa.JSON()


def upgrade() -> None:
    uuid = get_uuid_type()
    json_type = _json_column()

    # Create tl_player_data table
    op.create_table(
        'tl_player_data',
        sa.Column('player_id', uuid, nullable=False),
        sa.Column('wallet', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('vault', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tutorial_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('tutorial_progress', sa.String(length=50), nullable=False, server_default='not_started'),
        sa.Column('tutorial_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tutorial_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('player_id'),
    )

    # Create tl_prompt table
    op.create_table(
        'tl_prompt',
        sa.Column('prompt_id', uuid, nullable=False),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('embedding', json_type, nullable=True),  # Vector stored as JSON
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ai_seeded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.PrimaryKeyConstraint('prompt_id'),
    )
    op.create_index('idx_tl_prompt_active', 'tl_prompt', ['is_active'], unique=False)
    op.create_index('idx_tl_prompt_text', 'tl_prompt', ['text'], unique=False)

    # Create tl_cluster table
    op.create_table(
        'tl_cluster',
        sa.Column('cluster_id', uuid, nullable=False),
        sa.Column('prompt_id', uuid, nullable=False),
        sa.Column('centroid_embedding', json_type, nullable=False),
        sa.Column('size', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('example_answer_id', uuid, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.ForeignKeyConstraint(['prompt_id'], ['tl_prompt.prompt_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('cluster_id'),
    )
    op.create_index('idx_tl_cluster_prompt', 'tl_cluster', ['prompt_id'], unique=False)

    # Create tl_answer table
    op.create_table(
        'tl_answer',
        sa.Column('answer_id', uuid, nullable=False),
        sa.Column('prompt_id', uuid, nullable=False),
        sa.Column('text', sa.String(length=200), nullable=False),
        sa.Column('embedding', json_type, nullable=False),
        sa.Column('cluster_id', uuid, nullable=True),
        sa.Column('answer_players_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('contributed_matches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.ForeignKeyConstraint(['cluster_id'], ['tl_cluster.cluster_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['prompt_id'], ['tl_prompt.prompt_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('answer_id'),
    )
    op.create_index('idx_tl_answer_active', 'tl_answer', ['is_active', 'prompt_id'], unique=False)
    op.create_index('idx_tl_answer_cluster', 'tl_answer', ['cluster_id'], unique=False)
    op.create_index('idx_tl_answer_prompt', 'tl_answer', ['prompt_id'], unique=False)

    # Create tl_challenge table (v2 - no logic in v1)
    op.create_table(
        'tl_challenge',
        sa.Column('challenge_id', uuid, nullable=False),
        sa.Column('prompt_id', uuid, nullable=False),
        sa.Column('initiator_player_id', uuid, nullable=False),
        sa.Column('opponent_player_id', uuid, nullable=False),
        sa.Column('initiator_round_id', uuid, nullable=True),
        sa.Column('opponent_round_id', uuid, nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('time_limit_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('winner_player_id', uuid, nullable=True),
        sa.Column('initiator_final_coverage', sa.Float(), nullable=True),
        sa.Column('opponent_final_coverage', sa.Float(), nullable=True),
        sa.Column('initiator_gross_payout', sa.Integer(), nullable=True),
        sa.Column('opponent_gross_payout', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.CheckConstraint("status IN ('pending', 'active', 'completed', 'cancelled', 'expired')", name='valid_challenge_status'),
        sa.ForeignKeyConstraint(['initiator_player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['opponent_player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_id'], ['tl_prompt.prompt_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('challenge_id'),
    )

    # Create tl_round table
    op.create_table(
        'tl_round',
        sa.Column('round_id', uuid, nullable=False),
        sa.Column('player_id', uuid, nullable=False),
        sa.Column('prompt_id', uuid, nullable=False),
        sa.Column('snapshot_answer_ids', json_type, nullable=False),
        sa.Column('snapshot_cluster_ids', json_type, nullable=False),
        sa.Column('snapshot_total_weight', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('matched_clusters', json_type, nullable=False, server_default='[]'),
        sa.Column('strikes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('final_coverage', sa.Float(), nullable=True),
        sa.Column('gross_payout', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('challenge_id', uuid, nullable=True),
        sa.CheckConstraint('strikes >= 0 AND strikes <= 3', name='valid_strikes'),
        sa.CheckConstraint("status IN ('active', 'completed', 'abandoned')", name='valid_status'),
        sa.ForeignKeyConstraint(['challenge_id'], ['tl_challenge.challenge_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_id'], ['tl_prompt.prompt_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('round_id'),
    )
    op.create_index('idx_tl_round_player', 'tl_round', ['player_id'], unique=False)
    op.create_index('idx_tl_round_status', 'tl_round', ['status'], unique=False)

    # Create tl_guess table
    op.create_table(
        'tl_guess',
        sa.Column('guess_id', uuid, nullable=False),
        sa.Column('round_id', uuid, nullable=False),
        sa.Column('text', sa.String(length=200), nullable=False),
        sa.Column('embedding', json_type, nullable=False),
        sa.Column('was_match', sa.Boolean(), nullable=False),
        sa.Column('matched_answer_ids', json_type, nullable=False, server_default='[]'),
        sa.Column('matched_cluster_ids', json_type, nullable=False, server_default='[]'),
        sa.Column('caused_strike', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.ForeignKeyConstraint(['round_id'], ['tl_round.round_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('guess_id'),
    )
    op.create_index('idx_tl_guess_round', 'tl_guess', ['round_id'], unique=False)

    # Create tl_transaction table
    op.create_table(
        'tl_transaction',
        sa.Column('transaction_id', uuid, nullable=False),
        sa.Column('player_id', uuid, nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(length=50), nullable=False),
        sa.Column('round_id', uuid, nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['round_id'], ['tl_round.round_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('transaction_id'),
    )
    op.create_index('idx_tl_transaction_player', 'tl_transaction', ['player_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_tl_transaction_player', table_name='tl_transaction')
    op.drop_table('tl_transaction')
    op.drop_index('idx_tl_guess_round', table_name='tl_guess')
    op.drop_table('tl_guess')
    op.drop_index('idx_tl_round_status', table_name='tl_round')
    op.drop_index('idx_tl_round_player', table_name='tl_round')
    op.drop_table('tl_round')
    op.drop_table('tl_challenge')
    op.drop_index('idx_tl_answer_prompt', table_name='tl_answer')
    op.drop_index('idx_tl_answer_cluster', table_name='tl_answer')
    op.drop_index('idx_tl_answer_active', table_name='tl_answer')
    op.drop_table('tl_answer')
    op.drop_index('idx_tl_cluster_prompt', table_name='tl_cluster')
    op.drop_table('tl_cluster')
    op.drop_index('idx_tl_prompt_text', table_name='tl_prompt')
    op.drop_index('idx_tl_prompt_active', table_name='tl_prompt')
    op.drop_table('tl_prompt')
    op.drop_table('tl_player_data')
