"""add party_round_id to rounds table

Revision ID: b13a3971c741
Revises: 88c3b03e171a
Create Date: 2025-11-19 21:56:25.971030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b13a3971c741'
down_revision: Union[str, None] = '88c3b03e171a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from backend.migrations.util import get_uuid_type

def upgrade() -> None:
    uuid_type = get_uuid_type()
    op.add_column('qf_rounds', sa.Column('party_round_id', uuid_type, nullable=True))
    op.create_index('ix_qf_rounds_party_round_id', 'qf_rounds', ['party_round_id'])


def downgrade() -> None:
    op.drop_index('ix_qf_rounds_party_round_id', table_name='qf_rounds')
    op.drop_column('qf_rounds', 'party_round_id')
