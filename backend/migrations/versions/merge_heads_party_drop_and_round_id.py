"""Merge heads for party removals and round linkage."""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '6f3b07d822b9'
down_revision: Union[str, Sequence[str], None] = ('2b7d3c1fdc4a', 'b13a3971c741')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
