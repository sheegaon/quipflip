"""Shared helper utilities for service modules."""
from __future__ import annotations

from typing import Tuple
from uuid import UUID

from sqlalchemy import select, insert as sa_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.qf.result_view import ResultView


async def upsert_result_view(
    db: AsyncSession,
    *,
    phraseset_id: UUID,
    player_id: UUID,
    values: dict,
) -> Tuple[ResultView, bool]:
    """Insert a ResultView row if missing and return the persisted instance.

    Args:
        db: Active SQLAlchemy session.
        phraseset_id: Identifier for the phraseset the view belongs to.
        player_id: Player identifier for the view owner.
        values: Column values used when inserting a new row.

    Returns:
        A tuple of ``(result_view, inserted)`` where ``inserted`` indicates
        whether the row was newly created.
    """

    dialect = db.bind.dialect.name if db.bind else ""

    if dialect == "postgresql":
        stmt = (
            pg_insert(ResultView)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=[ResultView.player_id, ResultView.phraseset_id]
            )
        )
    else:
        stmt = sa_insert(ResultView).values(**values)
        if dialect == "sqlite":
            stmt = stmt.prefix_with("OR IGNORE")

    result = await db.execute(stmt)
    await db.flush()

    inserted = bool(getattr(result, "rowcount", 0))

    reload_stmt = select(ResultView).where(
        ResultView.phraseset_id == phraseset_id,
        ResultView.player_id == player_id,
    )
    reload_result = await db.execute(reload_stmt)
    result_view = reload_result.scalar_one()

    return result_view, inserted

