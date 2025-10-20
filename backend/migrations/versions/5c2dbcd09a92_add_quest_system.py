"""add_quest_system

Revision ID: 5c2dbcd09a92
Revises: 048b76471e0e
Create Date: 2025-10-19 00:42:36.044556

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c2dbcd09a92'
down_revision: Union[str, None] = '048b76471e0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add quest system tables."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == "postgresql":
        from sqlalchemy.dialects import postgresql
        uuid = postgresql.UUID()
    else:
        uuid = sa.String(length=36)

    # Create quest_templates table
    op.create_table('quest_templates',
        sa.Column('template_id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('reward_amount', sa.Integer(), nullable=False),
        sa.Column('target_value', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('template_id')
    )

    # Create quests table
    op.create_table('quests',
        sa.Column('quest_id', uuid, nullable=False),
        sa.Column('player_id', uuid, nullable=False),
        sa.Column('quest_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('progress', sa.JSON(), nullable=False),
        sa.Column('reward_amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('quest_id')
    )

    # Create indexes
    op.create_index('ix_quests_player_id', 'quests', ['player_id'], unique=False)
    op.create_index('ix_quests_quest_type', 'quests', ['quest_type'], unique=False)
    op.create_index('ix_quests_status', 'quests', ['status'], unique=False)
    op.create_index('ix_quests_player_status', 'quests', ['player_id', 'status'], unique=False)
    op.create_index('ix_quests_player_type', 'quests', ['player_id', 'quest_type'], unique=True)

    # Insert quest templates
    op.execute("""
        INSERT INTO quest_templates (template_id, name, description, reward_amount, target_value, category) VALUES
        ('hot_streak_5', 'Hot Streak', 'Get 5 votes correct in a row', 10, 5, 'streak'),
        ('hot_streak_10', 'Blazing Streak', 'Get 10 votes correct in a row', 25, 10, 'streak'),
        ('hot_streak_20', 'Inferno Streak', 'Get 20 votes correct in a row', 75, 20, 'streak'),
        ('deceptive_copy', 'Master Deceiver', 'Get 75% or more votes on your copy', 20, 75, 'quality'),
        ('obvious_original', 'Clear Original', 'Get 85% or more votes on the original', 15, 85, 'quality'),
        ('round_completion_5', 'Quick Player', 'Complete 5 rounds in 24 hours', 25, 5, 'activity'),
        ('round_completion_10', 'Active Player', 'Complete 10 rounds in 24 hours', 75, 10, 'activity'),
        ('round_completion_20', 'Power Player', 'Complete 20 rounds in 24 hours', 200, 20, 'activity'),
        ('balanced_player', 'Balanced Player', 'Complete 1 prompt, 2 copies, and 10 votes in 24 hours', 20, 10, 'activity'),
        ('login_streak_7', 'Week Warrior', 'Log in for 7 consecutive days', 200, 7, 'streak'),
        ('feedback_contributor_10', 'Feedback Novice', 'Submit 10 feedback responses', 5, 10, 'milestone'),
        ('feedback_contributor_50', 'Feedback Expert', 'Submit 50 feedback responses', 25, 50, 'milestone'),
        ('milestone_votes_100', 'Century Voter', 'Cast 100 total votes', 50, 100, 'milestone'),
        ('milestone_prompts_50', 'Prompt Master', 'Submit 50 total prompts', 100, 50, 'milestone'),
        ('milestone_copies_100', 'Copy Champion', 'Submit 100 total copies', 75, 100, 'milestone'),
        ('milestone_phraseset_20votes', 'Popular Set', 'Have a phraseset receive 20 votes', 25, 20, 'milestone')
    """)


def downgrade() -> None:
    """Remove quest system tables."""
    op.drop_index('ix_quests_player_type', table_name='quests')
    op.drop_index('ix_quests_player_status', table_name='quests')
    op.drop_index('ix_quests_status', table_name='quests')
    op.drop_index('ix_quests_quest_type', table_name='quests')
    op.drop_index('ix_quests_player_id', table_name='quests')
    op.drop_table('quests')
    op.drop_table('quest_templates')
