"""Regression tests for lifecycle invariants."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from backend.migrations.versions.b1d2c3e4f5a6_add_lifecycle_invariants import (
    _build_legacy_idempotency_key,
)
from backend.models.qf.party_session import PartySession
from backend.models.qf.transaction import QFTransaction
from backend.services.transaction_service import TransactionService
from backend.utils.idempotency import build_idempotency_key
from backend.utils.model_registry import GameType


@pytest.mark.asyncio
async def test_sqlite_pragmas_are_enabled(db_session):
    """SQLite connections should run with the production pragmas."""

    foreign_keys = await db_session.scalar(text("PRAGMA foreign_keys"))
    journal_mode = await db_session.scalar(text("PRAGMA journal_mode"))
    busy_timeout = await db_session.scalar(text("PRAGMA busy_timeout"))
    synchronous = await db_session.scalar(text("PRAGMA synchronous"))

    assert int(foreign_keys) == 1
    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) == 5000
    assert int(synchronous) == 2


def test_build_idempotency_key_normalizes_uuid_strings_and_set_order():
    """Equivalent payloads should hash identically across driver formats."""

    class OrderedSet(set):
        def __init__(self, values):
            super().__init__(values)
            self._order = list(values)

        def __iter__(self):
            return iter(self._order)

    token = uuid.uuid4()

    first = build_idempotency_key(
        "lifecycle-demo",
        {
            "player_id": token,
            "reference_id": token,
            "tags": OrderedSet(["beta", "alpha"]),
            "nested": {"round_id": token},
        },
    )
    second = build_idempotency_key(
        "lifecycle-demo",
        {
            "player_id": str(token),
            "reference_id": str(token),
            "tags": OrderedSet(["alpha", "beta"]),
            "nested": {"round_id": str(token)},
        },
    )

    assert first == second


def test_legacy_idempotency_backfill_is_unique_per_transaction_row():
    """Historical rows with the same logical payload still need unique keys."""

    payload = {
        "player_id": uuid.uuid4(),
        "amount": -5,
        "type": "mm_round_entry",
        "reference_id": None,
        "wallet_type": "wallet",
    }
    first = _build_legacy_idempotency_key(
        "mm_transactions",
        {
            **payload,
            "transaction_id": uuid.uuid4(),
        },
    )
    second = _build_legacy_idempotency_key(
        "mm_transactions",
        {
            **payload,
            "transaction_id": uuid.uuid4(),
        },
    )

    assert first != second


@pytest.mark.asyncio
async def test_transaction_service_is_idempotent(db_session, player_factory):
    """Retrying the same money command should not double-move balance."""

    player = await player_factory()
    service = TransactionService(db_session, GameType.QF)
    reference_id = uuid.uuid4()

    first = await service.create_transaction(
        player.player_id,
        -10,
        "round_entry",
        reference_id=reference_id,
        auto_commit=True,
    )
    second = await service.create_transaction(
        player.player_id,
        -10,
        "round_entry",
        reference_id=reference_id,
        auto_commit=True,
    )

    await db_session.refresh(player)

    assert first.transaction_id == second.transaction_id
    assert player.wallet == 4990

    count = await db_session.scalar(
        select(func.count(QFTransaction.transaction_id)).where(
            QFTransaction.idempotency_key == first.idempotency_key
        )
    )
    assert int(count) == 1


@pytest.mark.asyncio
async def test_versioned_party_session_rejects_stale_update(db_session, test_engine, player_factory):
    """Versioned lifecycle rows should reject stale concurrent writes."""

    host = await player_factory()
    session = PartySession(
        party_code=f"AB{uuid.uuid4().hex[:6]}",
        host_player_id=host.player_id,
        status="OPEN",
        current_phase="LOBBY",
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session_one, async_session() as session_two:
        first = await session_one.scalar(
            select(PartySession).where(PartySession.session_id == session.session_id)
        )
        second = await session_two.scalar(
            select(PartySession).where(PartySession.session_id == session.session_id)
        )

        assert first is not None
        assert second is not None

        first.status = "IN_PROGRESS"
        await session_one.commit()

        second.status = "COMPLETED"
        with pytest.raises(StaleDataError):
            await session_two.commit()
