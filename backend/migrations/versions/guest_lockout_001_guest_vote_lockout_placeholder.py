"""Placeholder for historic guest vote lockout migration.

This revision identifier previously existed only in production environments.
It did not have a corresponding migration file in the repository, which
prevented Alembic from upgrading because the revision could not be located.

Revision ID: guest_lockout_001
Revises: 0c5e8a127691
Create Date: 2025-10-31 00:00:00

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "guest_lockout_001"
down_revision: Union[str, None] = "0c5e8a127691"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op upgrade.

    The actual schema changes for the guest vote lockout feature live in the
    subsequent migration (revision ``d3ddc9470e6d``).  This placeholder exists
    solely so that databases already stamped with ``guest_lockout_001`` can
    continue upgrading without errors.
    """
    pass


def downgrade() -> None:
    """No-op downgrade."""
    pass
