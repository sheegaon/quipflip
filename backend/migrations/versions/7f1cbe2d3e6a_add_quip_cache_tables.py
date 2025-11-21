"""Add quip cache tables for AI prompt responses

Revision ID: 7f1cbe2d3e6a
Revises: 6f3b07d822b9
Create Date: 2025-03-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from backend.migrations.util import get_uuid_type


# revision identifiers, used by Alembic.
revision: str = '7f1cbe2d3e6a'
down_revision: Union[str, Sequence[str], None] = '6f3b07d822b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = get_uuid_type()

    op.create_table(
        'qf_ai_quip_cache',
        sa.Column('cache_id', uuid, nullable=False),
        sa.Column('prompt_id', uuid, nullable=True),
        sa.Column('prompt_text', sa.String(length=500), nullable=False),
        sa.Column('generation_provider', sa.String(length=50), nullable=False),
        sa.Column('generation_model', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['prompt_id'], ['qf_prompts.prompt_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('cache_id')
    )
    op.create_index('ix_quip_cache_prompt_text_provider', 'qf_ai_quip_cache', ['prompt_text', 'generation_provider'], unique=False)

    op.create_table(
        'qf_ai_quip_phrase',
        sa.Column('phrase_id', uuid, nullable=False),
        sa.Column('cache_id', uuid, nullable=False),
        sa.Column('phrase_text', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cache_id'], ['qf_ai_quip_cache.cache_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('phrase_id')
    )
    op.create_index('ix_qf_ai_quip_phrase_cache_id', 'qf_ai_quip_phrase', ['cache_id'], unique=False)

    op.create_table(
        'qf_ai_quip_phrase_usage',
        sa.Column('usage_id', uuid, nullable=False),
        sa.Column('phrase_id', uuid, nullable=False),
        sa.Column('prompt_round_id', uuid, nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['phrase_id'], ['qf_ai_quip_phrase.phrase_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_round_id'], ['qf_rounds.round_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('usage_id')
    )
    op.create_index('ix_quip_phrase_usage_round', 'qf_ai_quip_phrase_usage', ['prompt_round_id'], unique=False)
    op.create_index('ix_qf_ai_quip_phrase_usage_phrase_id', 'qf_ai_quip_phrase_usage', ['phrase_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_qf_ai_quip_phrase_usage_phrase_id', table_name='qf_ai_quip_phrase_usage')
    op.drop_index('ix_quip_phrase_usage_round', table_name='qf_ai_quip_phrase_usage')
    op.drop_table('qf_ai_quip_phrase_usage')

    op.drop_index('ix_qf_ai_quip_phrase_cache_id', table_name='qf_ai_quip_phrase')
    op.drop_table('qf_ai_quip_phrase')

    op.drop_index('ix_quip_cache_prompt_text_provider', table_name='qf_ai_quip_cache')
    op.drop_table('qf_ai_quip_cache')
