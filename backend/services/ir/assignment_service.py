"""Database-backed assignment commands for Initial Reaction."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.ir.assignment import IRAssignment
from backend.models.ir.backronym_set import BackronymSet
from backend.models.ir.enums import Mode, SetStatus
from backend.services.auth_service import GameType
from backend.services.ir.backronym_set_service import BackronymSetService
from backend.services.phrase_validator import PhraseValidator
from backend.services.transaction_service import TransactionService


class IRAssignmentError(RuntimeError):
    """Raised when an assignment command cannot be completed."""


class IRAssignmentService:
    """Own assignment creation, reconnect, and entry submission."""

    ACTIVE_STATUSES = ("assigned", "submitting", "submitted")

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.set_service = BackronymSetService(db)

    async def get_active_assignment(
        self,
        player_id: uuid.UUID | str,
    ) -> IRAssignment | None:
        result = await self.db.execute(
            select(IRAssignment)
            .join(BackronymSet, BackronymSet.set_id == IRAssignment.set_id)
            .where(
                IRAssignment.player_id == player_id,
                IRAssignment.status.in_(self.ACTIVE_STATUSES),
                BackronymSet.status != SetStatus.FINALIZED,
            )
            .order_by(IRAssignment.assigned_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def assign(
        self,
        player_id: uuid.UUID | str,
        mode: str = Mode.RAPID,
    ) -> tuple[IRAssignment, BackronymSet]:
        """Return the player's current assignment or create one."""

        existing = await self.get_active_assignment(player_id)
        if existing:
            set_obj = await self.set_service.get_set_by_id(existing.set_id)
            if set_obj:
                return existing, set_obj

        set_obj = await self.set_service.get_available_set_for_entry(
            exclude_player_id=str(player_id)
        )
        if not set_obj:
            set_obj = await self.set_service.create_set(mode=mode)

        assignment = IRAssignment(
            assignment_id=uuid.uuid4(),
            assignment_token=uuid.uuid4(),
            player_id=player_id,
            set_id=set_obj.set_id,
            status="assigned",
            assigned_at=datetime.now(UTC),
        )
        self.db.add(assignment)

        try:
            await self.db.commit()
            await self.db.refresh(assignment)
            return assignment, set_obj
        except IntegrityError:
            await self.db.rollback()
            existing = await self.get_active_assignment(player_id)
            if not existing:
                raise IRAssignmentError("assignment_conflict")
            existing_set = await self.set_service.get_set_by_id(existing.set_id)
            if not existing_set:
                raise IRAssignmentError("assignment_set_not_found")
            return existing, existing_set

    async def submit(
        self,
        player_id: uuid.UUID | str,
        set_id: uuid.UUID | str,
        assignment_token: uuid.UUID | str,
        words: list[str],
    ):
        """Claim an assignment once and atomically charge and persist its entry."""

        try:
            token = uuid.UUID(str(assignment_token))
        except ValueError as exc:
            raise IRAssignmentError("invalid_assignment_token") from exc

        result = await self.db.execute(
            select(IRAssignment).where(
                IRAssignment.player_id == player_id,
                IRAssignment.set_id == set_id,
                IRAssignment.assignment_token == token,
            )
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise IRAssignmentError("assignment_not_found")
        if assignment.status == "submitted" and assignment.entry_id:
            raise IRAssignmentError("assignment_already_submitted")
        if assignment.status != "assigned":
            raise IRAssignmentError("assignment_not_claimable")

        set_obj = await self.set_service.get_set_by_id(set_id)
        if not set_obj or set_obj.status != SetStatus.OPEN:
            raise IRAssignmentError("assignment_set_not_open")
        is_valid, error = PhraseValidator().validate_backronym_words(
            words,
            set_obj.word,
        )
        if not is_valid:
            raise IRAssignmentError(error)

        claimed = await self.db.execute(
            update(IRAssignment)
            .where(
                IRAssignment.assignment_id == assignment.assignment_id,
                IRAssignment.status == "assigned",
                IRAssignment.version == assignment.version,
            )
            .values(
                status="submitting",
                version=assignment.version + 1,
            )
        )
        if claimed.rowcount != 1:
            await self.db.rollback()
            raise IRAssignmentError("assignment_not_claimable")

        transaction_service = TransactionService(self.db, GameType.IR)
        try:
            await transaction_service.debit_wallet(
                player_id=uuid.UUID(str(player_id)),
                amount=self.settings.ir_backronym_entry_cost,
                transaction_type=transaction_service.ENTRY_CREATION,
                reference_id=uuid.UUID(str(set_id)),
                auto_commit=False,
            )
            entry = await self.set_service.add_entry(
                set_id=set_id,
                player_id=player_id,
                backronym_text=words,
                is_ai=False,
                auto_commit=False,
                transition_when_full=False,
            )

            assignment.status = "submitted"
            assignment.entry_id = entry.entry_id
            assignment.submitted_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(entry)
        except Exception:
            await self.db.rollback()
            raise

        set_obj = await self.set_service.get_set_by_id(set_id)
        if set_obj and set_obj.entry_count >= 5 and set_obj.status == SetStatus.OPEN:
            set_obj = await self.set_service.transition_to_voting(set_id)

        return entry, set_obj
