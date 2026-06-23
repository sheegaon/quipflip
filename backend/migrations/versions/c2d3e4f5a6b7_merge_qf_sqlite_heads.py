"""Merge the lifecycle and SQLite repair heads.

Revision ID: c2d3e4f5a6b7
Revises: a3f6c8d9e0b1, b1d2c3e4f5a6
Create Date: 2026-06-22 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

from alembic import op


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, tuple[str, str], None] = ("a3f6c8d9e0b1", "b1d2c3e4f5a6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
