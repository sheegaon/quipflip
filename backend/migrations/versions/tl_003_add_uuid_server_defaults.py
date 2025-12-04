"""Add server defaults for ThinkLink UUID primary keys.

Revision ID: tl_003_add_uuid_server_defaults
Revises: populate_tl_001
Create Date: 2026-02-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_uuid_default, get_uuid_type

# revision identifiers, used by Alembic.
revision: str = 'tl_003_add_uuid_server_defaults'
down_revision: Union[str, None] = 'populate_tl_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = get_uuid_type()
    uuid_default = get_uuid_default()

    if uuid_default is None:
        return

    op.alter_column(
        'tl_transaction',
        'transaction_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=uuid_default,
    )
    op.alter_column(
        'tl_challenge',
        'challenge_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=uuid_default,
    )
    op.alter_column(
        'tl_answer',
        'answer_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=uuid_default,
    )
    op.alter_column(
        'tl_cluster',
        'cluster_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=uuid_default,
    )
    op.alter_column(
        'tl_guess',
        'guess_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=uuid_default,
    )
    op.alter_column(
        'tl_round',
        'round_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=uuid_default,
    )


def downgrade() -> None:
    uuid_type = get_uuid_type()

    op.alter_column(
        'tl_transaction',
        'transaction_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        'tl_challenge',
        'challenge_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        'tl_answer',
        'answer_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        'tl_cluster',
        'cluster_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        'tl_guess',
        'guess_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        'tl_round',
        'round_id',
        existing_type=uuid_type,
        nullable=False,
        server_default=None,
    )
