"""migrate_words_to_phrases

Revision ID: c600ac93b635
Revises: 1b7f94ab2cba
Create Date: 2025-10-12 10:14:08.416450

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c600ac93b635'
down_revision: Union[str, None] = '1b7f94ab2cba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate from words to phrases: rename tables, columns, and expand string lengths."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Step 1: Rename wordsets table to phrasesets
    op.rename_table('wordsets', 'phrasesets')

    # Step 2: Rename columns in phrasesets table
    # Note: SQLite doesn't support ALTER COLUMN for renaming, so we handle it differently
    if dialect_name == 'sqlite':
        # For SQLite, we need to recreate the table
        # First, get UUID type
        uuid_type = sa.String(length=36)

        # Create new table with correct column names and types
        op.create_table('phrasesets_new',
            sa.Column('phraseset_id', uuid_type, nullable=False),
            sa.Column('prompt_round_id', uuid_type, nullable=False),
            sa.Column('copy_round_1_id', uuid_type, nullable=False),
            sa.Column('copy_round_2_id', uuid_type, nullable=False),
            sa.Column('prompt_text', sa.String(length=500), nullable=False),
            sa.Column('original_phrase', sa.String(length=100), nullable=False),
            sa.Column('copy_phrase_1', sa.String(length=100), nullable=False),
            sa.Column('copy_phrase_2', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('vote_count', sa.Integer(), nullable=False),
            sa.Column('third_vote_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('fifth_vote_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('closes_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('total_pool', sa.Integer(), nullable=False),
            sa.Column('system_contribution', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['copy_round_1_id'], ['rounds.round_id'], ),
            sa.ForeignKeyConstraint(['copy_round_2_id'], ['rounds.round_id'], ),
            sa.ForeignKeyConstraint(['prompt_round_id'], ['rounds.round_id'], ),
            sa.PrimaryKeyConstraint('phraseset_id')
        )

        # Copy data
        op.execute("""
            INSERT INTO phrasesets_new (
                phraseset_id, prompt_round_id, copy_round_1_id, copy_round_2_id,
                prompt_text, original_phrase, copy_phrase_1, copy_phrase_2,
                status, vote_count, third_vote_at, fifth_vote_at, closes_at,
                created_at, finalized_at, total_pool, system_contribution
            )
            SELECT
                wordset_id, prompt_round_id, copy_round_1_id, copy_round_2_id,
                prompt_text, original_word, copy_word_1, copy_word_2,
                status, vote_count, third_vote_at, fifth_vote_at, closes_at,
                created_at, finalized_at, total_pool, system_contribution
            FROM phrasesets
        """)

        # Drop old table
        op.drop_table('phrasesets')

        # Rename new table
        op.rename_table('phrasesets_new', 'phrasesets')

        # Recreate indexes
        op.create_index(op.f('ix_phrasesets_fifth_vote_at'), 'phrasesets', ['fifth_vote_at'], unique=False)
        op.create_index(op.f('ix_phrasesets_prompt_round_id'), 'phrasesets', ['prompt_round_id'], unique=False)
        op.create_index('ix_phrasesets_status_vote_count', 'phrasesets', ['status', 'vote_count'], unique=False)

    else:
        # PostgreSQL supports ALTER COLUMN but rename and type adjustments must happen in
        # separate steps for portability across server versions.
        op.alter_column('phrasesets', 'wordset_id', new_column_name='phraseset_id')

        for old_name, new_name in (
            ('original_word', 'original_phrase'),
            ('copy_word_1', 'copy_phrase_1'),
            ('copy_word_2', 'copy_phrase_2'),
        ):
            op.alter_column(
                'phrasesets',
                old_name,
                new_column_name=new_name,
                existing_type=sa.String(15),
            )
            op.alter_column(
                'phrasesets',
                new_name,
                type_=sa.String(100),
                existing_type=sa.String(15),
            )

        # Rename indexes (drop and recreate with new names)
        op.drop_index('ix_wordsets_fifth_vote_at', table_name='phrasesets')
        op.drop_index('ix_wordsets_prompt_round_id', table_name='phrasesets')
        op.drop_index('ix_wordsets_status_vote_count', table_name='phrasesets')

        op.create_index(op.f('ix_phrasesets_fifth_vote_at'), 'phrasesets', ['fifth_vote_at'], unique=False)
        op.create_index(op.f('ix_phrasesets_prompt_round_id'), 'phrasesets', ['prompt_round_id'], unique=False)
        op.create_index('ix_phrasesets_status_vote_count', 'phrasesets', ['status', 'vote_count'], unique=False)

    # Step 3: Update rounds table columns
    with op.batch_alter_table('rounds', schema=None) as batch_op:
        for old_name, new_name in (
            ('submitted_word', 'submitted_phrase'),
            ('original_word', 'original_phrase'),
            ('copy_word', 'copy_phrase'),
        ):
            batch_op.alter_column(
                old_name,
                new_column_name=new_name,
                type_=sa.String(100),
                existing_type=sa.String(15),
            )
        batch_op.alter_column('wordset_id', new_column_name='phraseset_id')

    # Step 4: Update votes table
    with op.batch_alter_table('votes', schema=None) as batch_op:
        # Rename the unique constraint to match the new phraseset terminology
        batch_op.drop_constraint('uq_player_wordset_vote', type_='unique')

        batch_op.alter_column('wordset_id', new_column_name='phraseset_id')
        batch_op.alter_column(
            'voted_word',
            new_column_name='voted_phrase',
            type_=sa.String(100),
            existing_type=sa.String(15),
        )

        batch_op.create_unique_constraint(
            'uq_player_phraseset_vote',
            ['player_id', 'phraseset_id']
        )

    # Step 5: Update result_views table
    with op.batch_alter_table('result_views', schema=None) as batch_op:
        batch_op.alter_column('wordset_id', new_column_name='phraseset_id')

        # Drop and recreate unique constraint with new name
        if dialect_name == 'postgresql':
            batch_op.drop_constraint('uq_player_wordset_result', type_='unique')
            batch_op.create_unique_constraint('uq_player_phraseset_result', ['player_id', 'phraseset_id'])
        # SQLite handles this automatically with batch operations


def downgrade() -> None:
    """Rollback phrases to words migration."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Reverse Step 5: Update result_views table
    with op.batch_alter_table('result_views', schema=None) as batch_op:
        batch_op.alter_column('phraseset_id', new_column_name='wordset_id')

        if dialect_name == 'postgresql':
            batch_op.drop_constraint('uq_player_phraseset_result', type_='unique')
            batch_op.create_unique_constraint('uq_player_wordset_result', ['player_id', 'wordset_id'])

    # Reverse Step 4: Update votes table
    with op.batch_alter_table('votes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_player_phraseset_vote', type_='unique')

        batch_op.alter_column('phraseset_id', new_column_name='wordset_id')
        batch_op.alter_column(
            'voted_phrase',
            new_column_name='voted_word',
            type_=sa.String(15),
            existing_type=sa.String(100),
        )

        batch_op.create_unique_constraint(
            'uq_player_wordset_vote',
            ['player_id', 'wordset_id']
        )

    # Reverse Step 3: Update rounds table
    with op.batch_alter_table('rounds', schema=None) as batch_op:
        for new_name, old_name in (
            ('submitted_phrase', 'submitted_word'),
            ('original_phrase', 'original_word'),
            ('copy_phrase', 'copy_word'),
        ):
            batch_op.alter_column(
                new_name,
                new_column_name=old_name,
                type_=sa.String(15),
                existing_type=sa.String(100),
            )
        batch_op.alter_column('phraseset_id', new_column_name='wordset_id')

    # Reverse Step 2 & 1: Rename phrasesets back to wordsets
    if dialect_name == 'sqlite':
        uuid_type = sa.String(length=36)

        # Create old table structure
        op.create_table('wordsets_new',
            sa.Column('wordset_id', uuid_type, nullable=False),
            sa.Column('prompt_round_id', uuid_type, nullable=False),
            sa.Column('copy_round_1_id', uuid_type, nullable=False),
            sa.Column('copy_round_2_id', uuid_type, nullable=False),
            sa.Column('prompt_text', sa.String(length=500), nullable=False),
            sa.Column('original_word', sa.String(length=15), nullable=False),
            sa.Column('copy_word_1', sa.String(length=15), nullable=False),
            sa.Column('copy_word_2', sa.String(length=15), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('vote_count', sa.Integer(), nullable=False),
            sa.Column('third_vote_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('fifth_vote_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('closes_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('total_pool', sa.Integer(), nullable=False),
            sa.Column('system_contribution', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['copy_round_1_id'], ['rounds.round_id'], ),
            sa.ForeignKeyConstraint(['copy_round_2_id'], ['rounds.round_id'], ),
            sa.ForeignKeyConstraint(['prompt_round_id'], ['rounds.round_id'], ),
            sa.PrimaryKeyConstraint('wordset_id')
        )

        # Copy data (truncate phrases to 15 chars)
        op.execute("""
            INSERT INTO wordsets_new (
                wordset_id, prompt_round_id, copy_round_1_id, copy_round_2_id,
                prompt_text, original_word, copy_word_1, copy_word_2,
                status, vote_count, third_vote_at, fifth_vote_at, closes_at,
                created_at, finalized_at, total_pool, system_contribution
            )
            SELECT
                phraseset_id, prompt_round_id, copy_round_1_id, copy_round_2_id,
                prompt_text,
                substr(original_phrase, 1, 15),
                substr(copy_phrase_1, 1, 15),
                substr(copy_phrase_2, 1, 15),
                status, vote_count, third_vote_at, fifth_vote_at, closes_at,
                created_at, finalized_at, total_pool, system_contribution
            FROM phrasesets
        """)

        op.drop_table('phrasesets')
        op.rename_table('wordsets_new', 'wordsets')

        # Recreate indexes
        op.create_index(op.f('ix_wordsets_fifth_vote_at'), 'wordsets', ['fifth_vote_at'], unique=False)
        op.create_index(op.f('ix_wordsets_prompt_round_id'), 'wordsets', ['prompt_round_id'], unique=False)
        op.create_index('ix_wordsets_status_vote_count', 'wordsets', ['status', 'vote_count'], unique=False)

    else:
        # PostgreSQL
        op.drop_index(op.f('ix_phrasesets_fifth_vote_at'), table_name='phrasesets')
        op.drop_index(op.f('ix_phrasesets_prompt_round_id'), table_name='phrasesets')
        op.drop_index('ix_phrasesets_status_vote_count', table_name='phrasesets')

        op.alter_column('phrasesets', 'phraseset_id', new_column_name='wordset_id')

        for new_name, old_name in (
            ('original_phrase', 'original_word'),
            ('copy_phrase_1', 'copy_word_1'),
            ('copy_phrase_2', 'copy_word_2'),
        ):
            op.alter_column(
                'phrasesets',
                new_name,
                new_column_name=old_name,
                existing_type=sa.String(100),
            )
            op.alter_column(
                'phrasesets',
                old_name,
                type_=sa.String(15),
                existing_type=sa.String(100),
            )

        op.rename_table('phrasesets', 'wordsets')

        op.create_index(op.f('ix_wordsets_fifth_vote_at'), 'wordsets', ['fifth_vote_at'], unique=False)
        op.create_index(op.f('ix_wordsets_prompt_round_id'), 'wordsets', ['prompt_round_id'], unique=False)
        op.create_index('ix_wordsets_status_vote_count', 'wordsets', ['status', 'vote_count'], unique=False)
