"""add_ai_phrase_cache_table

Revision ID: 3b9164a1de94
Revises: c7d8e9f0a1b2
Create Date: 2025-11-09 15:32:12.237413

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b9164a1de94'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ai_phrase_cache table
    op.create_table(
        'ai_phrase_cache',
        sa.Column('cache_id', sa.String(36), nullable=False),
        sa.Column('prompt_round_id', sa.String(36), nullable=False),
        sa.Column('original_phrase', sa.String(length=100), nullable=False),
        sa.Column('prompt_text', sa.String(length=500), nullable=True),
        sa.Column('validated_phrases', sa.JSON(), nullable=False),
        sa.Column('generation_provider', sa.String(length=50), nullable=False),
        sa.Column('generation_model', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_for_backup_copy', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('used_for_hints', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['prompt_round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('cache_id'),
        sa.UniqueConstraint('prompt_round_id')
    )
    op.create_index('ix_ai_phrase_cache_created_at', 'ai_phrase_cache', ['created_at'], unique=False)
    op.create_index('ix_ai_phrase_cache_prompt_round_id', 'ai_phrase_cache', ['prompt_round_id'], unique=True)

    # Add cache_id column to ai_metrics table using batch mode for SQLite compatibility
    with op.batch_alter_table('ai_metrics', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cache_id', sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            'fk_ai_metrics_cache_id',
            'ai_phrase_cache',
            ['cache_id'],
            ['cache_id'],
            ondelete='SET NULL'
        )
        batch_op.create_index('ix_ai_metrics_cache_id', ['cache_id'], unique=False)


def downgrade() -> None:
    # Remove cache_id from ai_metrics using batch mode for SQLite compatibility
    with op.batch_alter_table('ai_metrics', schema=None) as batch_op:
        batch_op.drop_index('ix_ai_metrics_cache_id')
        batch_op.drop_constraint('fk_ai_metrics_cache_id', type_='foreignkey')
        batch_op.drop_column('cache_id')

    # Drop ai_phrase_cache table
    op.drop_index('ix_ai_phrase_cache_prompt_round_id', table_name='ai_phrase_cache')
    op.drop_index('ix_ai_phrase_cache_created_at', table_name='ai_phrase_cache')
    op.drop_table('ai_phrase_cache')
