"""Persist and reuse vote-choice ordering for QuipFlip solo rounds."""
from __future__ import annotations

import logging
import random
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.qf.phraseset import Phraseset
from backend.models.qf.round import Round
from backend.models.qf.vote_choice import QFVoteChoice

logger = logging.getLogger(__name__)


class QFVoteChoiceService:
    """Manage vote-choice rows for a vote round."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_choices(self, round_id: UUID) -> list[QFVoteChoice]:
        result = await self.db.execute(
            select(QFVoteChoice)
            .where(QFVoteChoice.round_id == round_id)
            .order_by(QFVoteChoice.position.asc())
        )
        return list(result.scalars().all())

    async def get_or_create_vote_choices(self, round_object: Round, phraseset: Phraseset) -> list[QFVoteChoice]:
        """Return a stable vote-choice order for the round, creating it once if missing."""

        existing = await self._load_choices(round_object.round_id)
        if len(existing) == 3:
            return existing
        if existing:
            raise RuntimeError(
                f"Unexpected partial vote-choice state for round {round_object.round_id}: {len(existing)} rows"
            )

        seed_source = getattr(round_object, "assignment_token", None)
        seed = seed_source.int if seed_source is not None else round_object.round_id.int
        rng = random.Random(seed)

        choices = [
            ("original", phraseset.original_phrase),
            ("copy1", phraseset.copy_phrase_1),
            ("copy2", phraseset.copy_phrase_2),
        ]
        rng.shuffle(choices)

        try:
            async with self.db.begin_nested():
                for position, (internal_role, displayed_phrase) in enumerate(choices, start=1):
                    self.db.add(
                        QFVoteChoice(
                            choice_id=uuid.uuid4(),
                            round_id=round_object.round_id,
                            position=position,
                            choice_token=uuid.uuid4(),
                            displayed_phrase=displayed_phrase,
                            internal_role=internal_role,
                        )
                    )
                await self.db.flush()
        except IntegrityError:
            logger.debug(
                "Vote-choice rows already existed for round %s; loading persisted order",
                round_object.round_id,
            )

        await self.db.commit()
        persisted = await self._load_choices(round_object.round_id)
        if len(persisted) != 3:
            raise RuntimeError(
                f"Failed to persist vote choices for round {round_object.round_id}: {len(persisted)} rows"
            )
        return persisted
