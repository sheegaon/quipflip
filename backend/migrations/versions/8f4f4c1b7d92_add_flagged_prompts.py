"""Add flagged prompts table and player lock fields."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f4f4c1b7d92'
down_revision: Union[str, None] = 'd3ddc9470e6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create flagged_prompts table and extend players with lock metadata."""

    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        from sqlalchemy.dialects import postgresql

        uuid_type = postgresql.UUID()
        false_default = sa.text('false')
    else:
        uuid_type = sa.String(length=36)
        false_default = sa.text('0')

    # Player lock fields
    op.add_column(
        'players',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'players',
        sa.Column('flag_dismissal_streak', sa.Integer(), nullable=False, server_default='0'),
    )
    if dialect_name != "sqlite":
        op.alter_column(
            'players',
            'flag_dismissal_streak',
            server_default=None,
            existing_type=sa.Integer(),
        )

    # Flagged prompts table
    op.create_table(
        'flagged_prompts',
        sa.Column('flag_id', uuid_type, nullable=False),
        sa.Column('prompt_round_id', uuid_type, nullable=False),
        sa.Column('copy_round_id', uuid_type, nullable=True),
        sa.Column('reporter_player_id', uuid_type, nullable=False),
        sa.Column('prompt_player_id', uuid_type, nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_player_id', uuid_type, nullable=True),
        sa.Column('original_phrase', sa.String(length=100), nullable=False),
        sa.Column('prompt_text', sa.String(length=500), nullable=True),
        sa.Column('previous_phraseset_status', sa.String(length=20), nullable=True),
        sa.Column('queue_removed', sa.Boolean(), nullable=False, server_default=false_default),
        sa.Column('round_cost', sa.Integer(), nullable=False),
        sa.Column('partial_refund_amount', sa.Integer(), nullable=False),
        sa.Column('penalty_kept', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['prompt_round_id'], ['rounds.round_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['copy_round_id'], ['rounds.round_id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reporter_player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prompt_player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_player_id'], ['players.player_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('flag_id'),
    )

    op.create_index('ix_flagged_prompts_status', 'flagged_prompts', ['status'], unique=False)
    op.create_index('ix_flagged_prompts_prompt_round_id', 'flagged_prompts', ['prompt_round_id'], unique=False)
    op.create_index('ix_flagged_prompts_copy_round_id', 'flagged_prompts', ['copy_round_id'], unique=False)
    op.create_index('ix_flagged_prompts_reporter', 'flagged_prompts', ['reporter_player_id'], unique=False)
    op.create_index('ix_flagged_prompts_reviewer', 'flagged_prompts', ['reviewer_player_id'], unique=False)


def downgrade() -> None:
    """Revert flagged prompt additions."""

    op.drop_index('ix_flagged_prompts_reviewer', table_name='flagged_prompts')
    op.drop_index('ix_flagged_prompts_reporter', table_name='flagged_prompts')
    op.drop_index('ix_flagged_prompts_copy_round_id', table_name='flagged_prompts')
    op.drop_index('ix_flagged_prompts_prompt_round_id', table_name='flagged_prompts')
    op.drop_index('ix_flagged_prompts_status', table_name='flagged_prompts')
    op.drop_table('flagged_prompts')

    op.drop_column('players', 'flag_dismissal_streak')
    op.drop_column('players', 'locked_until')
