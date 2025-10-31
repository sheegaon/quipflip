"""create survey responses table

Revision ID: 9f2d8a3b1c4e
Revises: 588e85813c74
Create Date: 2025-11-05 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f2d8a3b1c4e'
down_revision: Union[str, None] = '588e85813c74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_type(dialect: str):
    if dialect == 'postgresql':
        from sqlalchemy.dialects import postgresql

        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def _json_type(dialect: str):
    if dialect == 'postgresql':
        from sqlalchemy.dialects import postgresql

        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    """Create survey_responses table with indices."""

    bind = op.get_bind()
    dialect = bind.dialect.name if bind else 'postgresql'

    uuid_type = _uuid_type(dialect)
    json_type = _json_type(dialect)

    created_at_default = sa.func.now()
    if dialect == 'postgresql':
        created_at_default = sa.text("timezone('utc', now())")

    op.create_table(
        'survey_responses',
        sa.Column('response_id', uuid_type, nullable=False),
        sa.Column('player_id', uuid_type, nullable=False),
        sa.Column('survey_id', sa.String(length=64), nullable=False),
        sa.Column('payload', json_type, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=created_at_default),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('response_id'),
    )
    op.create_index('ix_survey_responses_player_id', 'survey_responses', ['player_id'], unique=False)
    op.create_index('ix_survey_responses_survey_id', 'survey_responses', ['survey_id'], unique=False)
    op.create_index('ix_survey_responses_player_survey', 'survey_responses', ['player_id', 'survey_id'], unique=True)


def downgrade() -> None:
    """Drop survey_responses table and related indices."""

    op.drop_index('ix_survey_responses_player_survey', table_name='survey_responses')
    op.drop_index('ix_survey_responses_survey_id', table_name='survey_responses')
    op.drop_index('ix_survey_responses_player_id', table_name='survey_responses')
    op.drop_table('survey_responses')
