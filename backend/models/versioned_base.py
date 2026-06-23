"""Mixin for optimistic versioned rows."""
from __future__ import annotations

from sqlalchemy import Column, Integer
from sqlalchemy.orm import declared_attr


class VersionedBase:
    """Mixin that enables SQLAlchemy optimistic locking."""

    version = Column(Integer, nullable=False, default=1)

    @declared_attr.directive
    def __mapper_args__(cls):  # pragma: no cover - declarative wiring
        return {"version_id_col": cls.version}
