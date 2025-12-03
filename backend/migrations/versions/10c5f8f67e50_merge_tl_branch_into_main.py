"""Merge ThinkLink branch into main chain.

Revision ID: 10c5f8f67e50
Revises: 0f5c7c89f4bb, tl_002
Create Date: 2026-02-01
"""
from typing import Sequence, Union

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "10c5f8f67e50"
down_revision: Union[str, tuple[str, ...], None] = ("0f5c7c89f4bb", "tl_002")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This migration merges the ThinkLink branch (tl_002) into the main schema chain.
    pass


def downgrade() -> None:
    pass
