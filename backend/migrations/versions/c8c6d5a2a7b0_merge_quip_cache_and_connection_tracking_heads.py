"""Merge heads for quip cache and connection tracking branches."""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = 'c8c6d5a2a7b0'
down_revision: Union[str, Sequence[str], None] = (
    '7f1cbe2d3e6a',
    'a71603eb2fd8',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
