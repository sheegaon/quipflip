"""Base quest service with common functionality."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any, Type
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from backend.models.quest_base import QuestBase, QuestStatus
from backend.services.transaction_service import TransactionService
from backend.utils.model_registry import GameType

logger = logging.getLogger(__name__)


class QuestServiceError(RuntimeError):
    """Base exception for quest service errors."""


class QuestServiceBase(ABC):
    """Base service for managing player quests and achievements."""

    def __init__(self, db: AsyncSession):
        """Initialize quest service.

        Args:
            db: Database session
        """
        self.db = db

    @property
    @abstractmethod
    def quest_model(self) -> Type[QuestBase]:
        """Return the quest model class for this game."""
        pass

    @property
    @abstractmethod
    def player_service_class(self) -> Type[Any]:
        """Return the player service class for this game."""
        pass

    @property
    @abstractmethod
    def game_type(self) -> GameType:
        """Return the game type for this service."""
        pass

    @property
    @abstractmethod
    def quest_configs(self) -> Dict[Any, Dict[str, Any]]:
        """Return the quest configuration mapping for this game."""
        pass

    @property
    @abstractmethod
    def starter_quest_types(self) -> List[Any]:
        """Return the list of starter quest types for new players."""
        pass

    async def initialize_quests_for_player(self, player_id: UUID, *, auto_commit: bool = True) -> List[QuestBase]:
        """Ensure all starter quests exist for the player.

        Args:
            player_id: Player UUID to align with the starter quest set.
            auto_commit: When ``True`` (default) the session is committed on
                success. When ``False`` the caller is responsible for committing
                and this method will ``flush`` the pending changes instead.

        Returns:
            A list of quest instances representing the player's starter quests.
        """
        quests: List[QuestBase] = []
        try:
            for quest_type in self.starter_quest_types:
                try:
                    quest = await self._create_quest(
                        player_id, quest_type, check_existing=True
                    )
                    quests.append(quest)
                except Exception:
                    logger.exception(f"Failed to ensure quest {quest_type.value} for {player_id=}")

            if auto_commit:
                await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        finally:
            if not auto_commit and getattr(self.db, "in_transaction", lambda: False)():
                try:
                    await self.db.flush()
                except Exception:
                    logger.exception(f"Failed to flush quest initialization changes for {player_id=}")

        logger.info(
            f"Ensured starter quests exist for {self.game_type.value} {player_id=} "
            f"(total={len(self.starter_quest_types)})"
        )
        return quests

    async def create_missing_starter_quests(
        self,
        player_id: UUID,
        missing_quest_types: List[Any],
        *,
        auto_commit: bool = True,
    ) -> List[QuestBase]:
        """Create only the missing starter quests for a player.

        Args:
            player_id: Player receiving additional starter quests.
            missing_quest_types: Quest types that are not currently assigned to
                the player.
            auto_commit: When ``True`` (default) the session is committed on
                success. When ``False`` the caller is responsible for committing
                and the method flushes the pending changes instead.

        Returns:
            The quests that now exist for the player (newly created or
            previously present when a race condition is detected).
        """
        if not missing_quest_types:
            return []

        quests: List[QuestBase] = []
        try:
            for quest_type in missing_quest_types:
                try:
                    quests.append(await self._create_quest(player_id, quest_type, check_existing=False))
                except Exception:
                    logger.exception(f"Failed to create quest {quest_type.value} for {player_id=}")

            if auto_commit:
                await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        finally:
            if not auto_commit and getattr(self.db, "in_transaction", lambda: False)():
                try:
                    await self.db.flush()
                except Exception:
                    logger.exception(f"Failed to flush missing quest creation for {player_id=}")

        logger.info(
            f"Ensured {len(missing_quest_types)} missing starter quests exist for {self.game_type.value} {player_id=}")
        return quests

    async def _create_quest(
        self,
        player_id: UUID,
        quest_type: Any,
        *,
        check_existing: bool = True,
    ) -> QuestBase:
        """Create a new quest for a player, avoiding duplicates via UPSERT."""
        config = self.quest_configs.get(quest_type)
        if not config:
            raise ValueError(f"Unknown quest configuration for {quest_type=}")

        if check_existing:
            existing_quest = await self._get_existing_quest(player_id, quest_type)
            if existing_quest:
                logger.info(f"Quest {quest_type.value} already exists for {self.game_type.value} {player_id=}")
                return existing_quest

        reward_amount = config.get("reward")
        if reward_amount is None:
            raise ValueError(f"Quest configuration for {quest_type.value} is missing a reward amount")

        quest_values = {
            "player_id": player_id,
            "quest_type": quest_type.value,
            "status": QuestStatus.ACTIVE.value,
            "progress": self._get_initial_progress(quest_type),
            "reward_amount": reward_amount,
        }

        bind = self.db.get_bind()
        dialect_name = (bind.dialect.name if bind is not None else "").lower()
        if "sqlite" in dialect_name:
            insert_stmt = sqlite_insert(self.quest_model)
        else:
            insert_stmt = postgres_insert(self.quest_model)

        stmt = insert_stmt.values(**quest_values)
        if hasattr(stmt, "on_conflict_do_nothing"):
            stmt = stmt.on_conflict_do_nothing(index_elements=["player_id", "quest_type"])

        try:
            result = await self.db.execute(stmt)
        except IntegrityError as exc:
            logger.warning(
                f"Integrity error while creating quest {quest_type.value} for "
                f"{self.game_type.value} {player_id=}: {exc}"
            )
            return await self._get_existing_quest(player_id, quest_type)

        if getattr(result, "rowcount", None) == 1:
            logger.info(f"Created quest {quest_type.value} for {self.game_type.value} {player_id=}")
        else:
            logger.info(
                f"Quest {quest_type.value} already existed for {self.game_type.value} {player_id=} "
                f"(detected via upsert)"
            )

        quest = await self._get_existing_quest(player_id, quest_type)
        if quest is None:
            raise RuntimeError(
                f"Quest {quest_type.value} for {self.game_type.value} {player_id=} "
                f"could not be loaded after upsert"
            )
        return quest

    async def _get_existing_quest(
        self, player_id: UUID, quest_type: Any
    ) -> Optional[QuestBase]:
        """Get an existing quest by player and type."""
        existing_result = await self.db.execute(
            select(self.quest_model).where(
                and_(
                    self.quest_model.player_id == player_id,
                    self.quest_model.quest_type == quest_type.value,
                )
            )
        )
        return existing_result.scalar_one_or_none()

    async def get_player_quests(self, player_id: UUID, status: Optional[str] = None) -> List[QuestBase]:
        """Get all quests for a player, optionally filtered by status."""
        query = select(self.quest_model).where(self.quest_model.player_id == player_id)

        if status:
            query = query.where(self.quest_model.status == status)

        query = query.order_by(self.quest_model.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_quest_by_id(self, quest_id: UUID) -> Optional[QuestBase]:
        """Get a quest by ID."""
        result = await self.db.execute(select(self.quest_model).where(self.quest_model.quest_id == quest_id))
        return result.scalar_one_or_none()

    async def claim_quest_reward(self, quest_id: UUID, player_id: UUID, transaction_service: TransactionService
                                 ) -> Dict[str, Any]:
        """
        Claim a completed quest reward.

        Returns:
            Dict with success, quest_type, reward_amount, new_wallet, new_vault
        """
        # Get quest with lock
        result = await self.db.execute(
            select(self.quest_model).where(
                and_(
                    self.quest_model.quest_id == quest_id, 
                    self.quest_model.player_id == player_id
                )
            ).with_for_update()
        )
        quest = result.scalar_one_or_none()

        if not quest:
            raise ValueError("Quest not found")

        if quest.status != QuestStatus.COMPLETED.value:
            raise ValueError("Quest is not completed")

        if quest.claimed_at is not None:
            raise ValueError("Quest reward already claimed")

        # Update quest status
        quest.status = QuestStatus.CLAIMED.value
        quest.claimed_at = datetime.now(UTC)

        # Create transaction for reward
        transaction = await transaction_service.create_transaction(
            player_id=player_id,
            amount=quest.reward_amount,
            trans_type=f"quest_reward_{quest.quest_type}",
            reference_id=quest_id,
            auto_commit=False,
            skip_lock=True,
        )

        await self.db.commit()
        await self.db.refresh(quest)

        logger.info(
            f"Quest reward claimed: {self.game_type.value} {player_id=}, "
            f"{quest.quest_type=}, {quest.reward_amount=}, "
            f"{transaction.wallet_balance_after=}, {transaction.vault_balance_after=}"
        )

        # Check if we should auto-create next tier quest
        await self._check_next_tier_quest(player_id, quest.quest_type)

        return {
            "success": True,
            "quest_type": quest.quest_type,
            "reward_amount": quest.reward_amount,
            "new_wallet": transaction.wallet_balance_after,
            "new_vault": transaction.vault_balance_after,
        }

    async def _check_next_tier_quest(self, player_id: UUID, quest_type_str: str) -> None:
        """Check if we should create a next tier quest after claiming a reward."""
        try:
            # Convert string back to enum for lookup
            quest_type = self._string_to_quest_type(quest_type_str)
            config = self.quest_configs.get(quest_type)
            if config and "next_tier" in config and config["next_tier"]:
                await self._create_quest(player_id, config["next_tier"])
                await self.db.commit()
                logger.info(
                    f"Created next tier quest {config['next_tier'].value} for {self.game_type.value} {player_id=}")
        except Exception as e:
            logger.error(f"Failed to create next tier quest: {e}", exc_info=True)

    @abstractmethod
    def _string_to_quest_type(self, quest_type_str: str) -> Any:
        """Convert a quest type string back to the appropriate enum."""
        pass

    @abstractmethod
    def _get_initial_progress(self, quest_type: Any) -> Dict[str, Any]:
        """Get initial progress structure for a quest type."""
        pass

    # Common incremental progress tracking methods
    async def increment_progress_counter(self, player_id: UUID, quest_types: List[Any], increment: int = 1) -> None:
        """Increment progress counters for milestone-style quests."""
        if not quest_types:
            return

        quest_type_values = [qt.value for qt in quest_types]
        
        # Get active quests of the specified types
        quests_result = await self.db.execute(
            select(self.quest_model).where(
                and_(
                    self.quest_model.player_id == player_id,
                    self.quest_model.status == QuestStatus.ACTIVE.value,
                    self.quest_model.quest_type.in_(quest_type_values)
                )
            )
        )
        quests = list(quests_result.scalars().all())

        for quest in quests:
            quest_type = self._string_to_quest_type(quest.quest_type)
            config = self.quest_configs.get(quest_type)
            if not config:
                continue

            progress = quest.progress
            current = progress.get("current", 0)
            progress["current"] = current + increment

            if progress["current"] >= config["target"]:
                quest.status = QuestStatus.COMPLETED.value
                quest.completed_at = datetime.now(UTC)
                logger.info(f"Quest {quest.quest_type} completed for {self.game_type.value} {player_id=}")

            quest.progress = progress
            self.db.add(quest)

        if quests:
            await self.db.commit()

    async def update_streak_quest(self, player_id: UUID, quest_types: List[Any], streak_broken: bool = False) -> None:
        """Update streak-based quests."""
        if not quest_types:
            return

        quest_type_values = [qt.value for qt in quest_types]
        
        result = await self.db.execute(
            select(self.quest_model).where(
                and_(
                    self.quest_model.player_id == player_id,
                    self.quest_model.status == QuestStatus.ACTIVE.value,
                    self.quest_model.quest_type.in_(quest_type_values)
                )
            )
        )
        quests = list(result.scalars().all())

        for quest in quests:
            quest_type = self._string_to_quest_type(quest.quest_type)
            config = self.quest_configs.get(quest_type)
            if not config:
                continue

            progress = quest.progress

            if streak_broken:
                progress["current_streak"] = 0
            else:
                progress["current_streak"] = progress.get("current_streak", 0) + 1
                progress["highest_streak"] = max(
                    progress.get("highest_streak", 0),
                    progress["current_streak"]
                )

                # Check if quest completed
                if progress["current_streak"] >= config["target"]:
                    quest.status = QuestStatus.COMPLETED.value
                    quest.completed_at = datetime.now(UTC)
                    logger.info(f"Quest {quest.quest_type} completed for {self.game_type.value} {player_id=}")

            quest.progress = progress
            self.db.add(quest)

        if quests:
            await self.db.commit()
