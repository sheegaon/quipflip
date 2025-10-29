"""Quest service for managing player quests and achievements."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from uuid import UUID
import uuid
import logging
from datetime import datetime, timedelta, UTC, date
from typing import List, Optional, Dict, Any

from backend.models.quest import Quest, QuestTemplate, QuestType, QuestStatus, QuestCategory
from backend.models.player import Player
from backend.models.vote import Vote
from backend.models.round import Round
from backend.models.prompt import Prompt
from backend.models.phraseset import Phraseset
from backend.models.prompt_feedback import PromptFeedback
from backend.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)


# Quest configuration mapping
QUEST_CONFIGS = {
    QuestType.HOT_STREAK_5: {
        "name": "Hot Streak",
        "description": "Get 5 votes correct in a row",
        "target": 5,
        "reward": 10,
        "category": QuestCategory.STREAK,
        "next_tier": QuestType.HOT_STREAK_10,
    },
    QuestType.HOT_STREAK_10: {
        "name": "Blazing Streak",
        "description": "Get 10 votes correct in a row",
        "target": 10,
        "reward": 25,
        "category": QuestCategory.STREAK,
        "next_tier": QuestType.HOT_STREAK_20,
    },
    QuestType.HOT_STREAK_20: {
        "name": "Inferno Streak",
        "description": "Get 20 votes correct in a row",
        "target": 20,
        "reward": 75,
        "category": QuestCategory.STREAK,
        "next_tier": None,
    },
    QuestType.DECEPTIVE_COPY: {
        "name": "Master Deceiver",
        "description": "Get 75% or more votes on your copy",
        "target": 75,
        "reward": 20,
        "category": QuestCategory.QUALITY,
    },
    QuestType.OBVIOUS_ORIGINAL: {
        "name": "Clear Original",
        "description": "Get 85% or more votes on the original",
        "target": 85,
        "reward": 15,
        "category": QuestCategory.QUALITY,
    },
    QuestType.ROUND_COMPLETION_5: {
        "name": "Quick Player",
        "description": "Complete 5 rounds in 24 hours",
        "target": 5,
        "reward": 25,
        "category": QuestCategory.ACTIVITY,
        "next_tier": QuestType.ROUND_COMPLETION_10,
    },
    QuestType.ROUND_COMPLETION_10: {
        "name": "Active Player",
        "description": "Complete 10 rounds in 24 hours",
        "target": 10,
        "reward": 75,
        "category": QuestCategory.ACTIVITY,
        "next_tier": QuestType.ROUND_COMPLETION_20,
    },
    QuestType.ROUND_COMPLETION_20: {
        "name": "Power Player",
        "description": "Complete 20 rounds in 24 hours",
        "target": 20,
        "reward": 200,
        "category": QuestCategory.ACTIVITY,
        "next_tier": None,
    },
    QuestType.BALANCED_PLAYER: {
        "name": "Balanced Player",
        "description": "Complete 1 prompt, 2 copies, and 10 votes in 24 hours",
        "target": 10,
        "reward": 20,
        "category": QuestCategory.ACTIVITY,
    },
    QuestType.LOGIN_STREAK_7: {
        "name": "Week Warrior",
        "description": "Log in for 7 consecutive days",
        "target": 7,
        "reward": 200,
        "category": QuestCategory.STREAK,
    },
    QuestType.FEEDBACK_CONTRIBUTOR_10: {
        "name": "Feedback Novice",
        "description": "Submit 10 feedback responses",
        "target": 10,
        "reward": 5,
        "category": QuestCategory.MILESTONE,
        "next_tier": QuestType.FEEDBACK_CONTRIBUTOR_50,
    },
    QuestType.FEEDBACK_CONTRIBUTOR_50: {
        "name": "Feedback Expert",
        "description": "Submit 50 feedback responses",
        "target": 50,
        "reward": 25,
        "category": QuestCategory.MILESTONE,
        "next_tier": None,
    },
    QuestType.MILESTONE_VOTES_100: {
        "name": "Century Voter",
        "description": "Cast 100 total votes",
        "target": 100,
        "reward": 50,
        "category": QuestCategory.MILESTONE,
    },
    QuestType.MILESTONE_PROMPTS_50: {
        "name": "Prompt Master",
        "description": "Submit 50 total prompts",
        "target": 50,
        "reward": 100,
        "category": QuestCategory.MILESTONE,
    },
    QuestType.MILESTONE_COPIES_100: {
        "name": "Copy Champion",
        "description": "Submit 100 total copies",
        "target": 100,
        "reward": 75,
        "category": QuestCategory.MILESTONE,
    },
    QuestType.MILESTONE_PHRASESET_20VOTES: {
        "name": "Popular Set",
        "description": "Have a phraseset receive 20 votes",
        "target": 20,
        "reward": 25,
        "category": QuestCategory.MILESTONE,
    },
}


class QuestService:
    """Service for managing player quests."""

    STARTER_QUEST_TYPES: List[QuestType] = [
        QuestType.HOT_STREAK_5,
        QuestType.ROUND_COMPLETION_5,
        QuestType.BALANCED_PLAYER,
        QuestType.LOGIN_STREAK_7,
        QuestType.FEEDBACK_CONTRIBUTOR_10,
        QuestType.MILESTONE_VOTES_100,
        QuestType.MILESTONE_PROMPTS_50,
        QuestType.MILESTONE_COPIES_100,
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_quests_for_player(self, player_id: UUID) -> List[Quest]:
        """Initialize starter quests for a new player."""
        starter_quests = self.STARTER_QUEST_TYPES

        quests = []
        for quest_type in starter_quests:
            quest = await self._create_quest(player_id, quest_type)
            quests.append(quest)

        await self.db.commit()
        logger.info(f"Initialized {len(quests)} quests for player {player_id}")
        return quests

    async def _create_quest(self, player_id: UUID, quest_type: QuestType) -> Quest:
        """Create a new quest for a player."""
        config = QUEST_CONFIGS[quest_type]

        # Check if quest already exists
        existing_result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == quest_type.value
                )
            )
        )
        existing_quest = existing_result.scalar_one_or_none()
        if existing_quest:
            logger.info(f"Quest {quest_type.value} already exists for player {player_id}")
            return existing_quest

        quest = Quest(
            quest_id=uuid.uuid4(),
            player_id=player_id,
            quest_type=quest_type.value,
            status=QuestStatus.ACTIVE.value,
            progress=self._get_initial_progress(quest_type),
            reward_amount=config["reward"],
        )

        self.db.add(quest)
        logger.info(f"Created quest {quest_type.value} for player {player_id}")
        return quest

    def _get_initial_progress(self, quest_type: QuestType) -> Dict[str, Any]:
        """Get initial progress structure for a quest type."""
        config = QUEST_CONFIGS[quest_type]
        target = config["target"]

        if quest_type in [QuestType.HOT_STREAK_5, QuestType.HOT_STREAK_10, QuestType.HOT_STREAK_20]:
            return {"current_streak": 0, "target": target, "highest_streak": 0}

        elif quest_type in [QuestType.ROUND_COMPLETION_5, QuestType.ROUND_COMPLETION_10, QuestType.ROUND_COMPLETION_20]:
            return {
                "rounds_completed": 0,
                "target": target,
                "window_start": datetime.now(UTC).isoformat(),
                "round_timestamps": []
            }

        elif quest_type == QuestType.BALANCED_PLAYER:
            return {
                "window_start": datetime.now(UTC).isoformat(),
                "prompts": 0,
                "copies": 0,
                "votes": 0,
                "target": {"prompts": 1, "copies": 2, "votes": target}
            }

        elif quest_type == QuestType.LOGIN_STREAK_7:
            return {
                "consecutive_days": 0,
                "target": target,
                "last_login_date": None,
                "login_dates": []
            }

        else:  # Milestone quests
            return {"current": 0, "target": target}

    async def get_player_quests(
        self, player_id: UUID, status: Optional[str] = None
    ) -> List[Quest]:
        """Get all quests for a player, optionally filtered by status."""
        query = select(Quest).where(Quest.player_id == player_id)

        if status:
            query = query.where(Quest.status == status)

        query = query.order_by(Quest.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_quest_by_id(self, quest_id: UUID) -> Optional[Quest]:
        """Get a quest by ID."""
        result = await self.db.execute(
            select(Quest).where(Quest.quest_id == quest_id)
        )
        return result.scalar_one_or_none()

    async def claim_quest_reward(
        self, quest_id: UUID, player_id: UUID, transaction_service: TransactionService
    ) -> Dict[str, Any]:
        """
        Claim a completed quest reward.

        Returns:
            Dict with success, quest_type, reward_amount, new_balance
        """
        # Get quest with lock
        result = await self.db.execute(
            select(Quest).where(
                and_(Quest.quest_id == quest_id, Quest.player_id == player_id)
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
            f"Quest reward claimed: player={player_id}, quest={quest.quest_type}, "
            f"reward={quest.reward_amount}, new_balance={transaction.balance_after}"
        )

        # Check if we should auto-create next tier quest
        quest_type = QuestType(quest.quest_type)
        config = QUEST_CONFIGS.get(quest_type)
        if config and "next_tier" in config and config["next_tier"]:
            await self._create_quest(player_id, config["next_tier"])
            await self.db.commit()
            logger.info(f"Created next tier quest {config['next_tier'].value} for player {player_id}")

        return {
            "success": True,
            "quest_type": quest.quest_type,
            "reward_amount": quest.reward_amount,
            "new_balance": transaction.balance_after,
        }

    async def check_and_update_vote_streak(self, player_id: UUID, vote_correct: bool) -> None:
        """Check and update hot streak quest after a vote."""
        # Get active hot streak quests
        result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.status == QuestStatus.ACTIVE.value,
                    Quest.quest_type.in_([
                        QuestType.HOT_STREAK_5.value,
                        QuestType.HOT_STREAK_10.value,
                        QuestType.HOT_STREAK_20.value,
                    ])
                )
            )
        )
        quests = list(result.scalars().all())

        for quest in quests:
            progress = quest.progress
            config = QUEST_CONFIGS[QuestType(quest.quest_type)]

            if vote_correct:
                progress["current_streak"] += 1
                progress["highest_streak"] = max(
                    progress.get("highest_streak", 0),
                    progress["current_streak"]
                )

                # Check if quest completed
                if progress["current_streak"] >= config["target"]:
                    quest.status = QuestStatus.COMPLETED.value
                    quest.completed_at = datetime.now(UTC)
                    logger.info(f"Quest {quest.quest_type} completed for player {player_id}")
            else:
                # Reset streak on incorrect vote
                progress["current_streak"] = 0

            quest.progress = progress
            self.db.add(quest)

        await self.db.commit()

    async def check_deceptive_copy(self, phraseset_id: UUID) -> None:
        """Check if any player earned the deceptive copy bonus."""
        # Get phraseset
        result = await self.db.execute(
            select(Phraseset).where(Phraseset.phraseset_id == phraseset_id)
        )
        phraseset = result.scalar_one_or_none()

        if not phraseset or phraseset.status != "finalized":
            return

        # Get vote counts by querying the votes table
        votes_result = await self.db.execute(
            select(Vote.voted_phrase, func.count(Vote.vote_id).label('vote_count'))
            .where(Vote.phraseset_id == phraseset_id)
            .group_by(Vote.voted_phrase)
        )
        vote_counts = {phrase: count for phrase, count in votes_result.all()}
        
        # Calculate total votes
        total_votes = sum(vote_counts.values())
        if total_votes == 0:
            return

        # Get player IDs from the rounds
        copy1_result = await self.db.execute(
            select(Round.player_id).where(Round.round_id == phraseset.copy_round_1_id)
        )
        copy1_player_id = copy1_result.scalar_one_or_none()
        
        copy2_result = await self.db.execute(
            select(Round.player_id).where(Round.round_id == phraseset.copy_round_2_id)
        )
        copy2_player_id = copy2_result.scalar_one_or_none()

        # Check both copy players
        copy_data = [
            (copy1_player_id, phraseset.copy_phrase_1),
            (copy2_player_id, phraseset.copy_phrase_2),
        ]
        
        for copy_player_id, copy_phrase in copy_data:
            if not copy_player_id:
                continue

            copy_votes = vote_counts.get(copy_phrase, 0)
            vote_percentage = (copy_votes / total_votes) * 100

            if vote_percentage >= 75:
                # Check if player has active quest
                quest_result = await self.db.execute(
                    select(Quest).where(
                        and_(
                            Quest.player_id == copy_player_id,
                            Quest.quest_type == QuestType.DECEPTIVE_COPY.value,
                            Quest.status == QuestStatus.ACTIVE.value
                        )
                    )
                )
                quest = quest_result.scalar_one_or_none()

                if not quest:
                    # Create and complete quest
                    quest = await self._create_quest(copy_player_id, QuestType.DECEPTIVE_COPY)

                if quest.status == QuestStatus.ACTIVE.value:
                    quest.status = QuestStatus.COMPLETED.value
                    quest.completed_at = datetime.now(UTC)
                    quest.progress["percentage"] = vote_percentage
                    self.db.add(quest)
                    logger.info(
                        f"Deceptive copy quest completed for player {copy_player_id}, "
                        f"percentage={vote_percentage:.1f}%"
                    )

        await self.db.commit()

    async def check_obvious_original(self, phraseset_id: UUID) -> None:
        """Check if the original prompt player earned the obvious original bonus."""
        # Get phraseset
        result = await self.db.execute(
            select(Phraseset).where(Phraseset.phraseset_id == phraseset_id)
        )
        phraseset = result.scalar_one_or_none()

        if not phraseset or phraseset.status != "finalized":
            return

        # Get vote counts by querying the votes table
        votes_result = await self.db.execute(
            select(Vote.voted_phrase, func.count(Vote.vote_id).label('vote_count'))
            .where(Vote.phraseset_id == phraseset_id)
            .group_by(Vote.voted_phrase)
        )
        vote_counts = {phrase: count for phrase, count in votes_result.all()}
        
        # Calculate total votes
        total_votes = sum(vote_counts.values())
        if total_votes == 0:
            return

        # Get original player ID from the prompt round
        original_result = await self.db.execute(
            select(Round.player_id).where(Round.round_id == phraseset.prompt_round_id)
        )
        original_player_id = original_result.scalar_one_or_none()
        
        if not original_player_id:
            return

        original_votes = vote_counts.get(phraseset.original_phrase, 0)
        vote_percentage = (original_votes / total_votes) * 100

        if vote_percentage >= 85:
            # Check if player has active quest
            quest_result = await self.db.execute(
                select(Quest).where(
                    and_(
                        Quest.player_id == original_player_id,
                        Quest.quest_type == QuestType.OBVIOUS_ORIGINAL.value,
                        Quest.status == QuestStatus.ACTIVE.value
                    )
                )
            )
            quest = quest_result.scalar_one_or_none()

            if not quest:
                # Create and complete quest
                quest = await self._create_quest(original_player_id, QuestType.OBVIOUS_ORIGINAL)

            if quest.status == QuestStatus.ACTIVE.value:
                quest.status = QuestStatus.COMPLETED.value
                quest.completed_at = datetime.now(UTC)
                quest.progress["percentage"] = vote_percentage
                self.db.add(quest)
                logger.info(
                    f"Obvious original quest completed for player {original_player_id}, "
                    f"percentage={vote_percentage:.1f}%"
                )

            await self.db.commit()

    async def increment_round_completion(self, player_id: UUID) -> None:
        """Track round completion for activity quests."""
        now = datetime.now(UTC)
        window_start = now - timedelta(hours=24)

        # Get active round completion quests
        result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.status == QuestStatus.ACTIVE.value,
                    Quest.quest_type.in_([
                        QuestType.ROUND_COMPLETION_5.value,
                        QuestType.ROUND_COMPLETION_10.value,
                        QuestType.ROUND_COMPLETION_20.value,
                    ])
                )
            )
        )
        quests = list(result.scalars().all())

        for quest in quests:
            progress = quest.progress
            config = QUEST_CONFIGS[QuestType(quest.quest_type)]

            # Add current timestamp
            timestamps = progress.get("round_timestamps", [])
            timestamps.append(now.isoformat())

            # Filter to 24-hour window
            valid_timestamps = [
                ts for ts in timestamps
                if datetime.fromisoformat(ts) >= window_start
            ]

            progress["round_timestamps"] = valid_timestamps
            progress["rounds_completed"] = len(valid_timestamps)
            progress["window_start"] = window_start.isoformat()

            # Check if quest completed
            if progress["rounds_completed"] >= config["target"]:
                quest.status = QuestStatus.COMPLETED.value
                quest.completed_at = now
                logger.info(f"Quest {quest.quest_type} completed for player {player_id}")

            quest.progress = progress
            self.db.add(quest)

        await self.db.commit()

    async def check_balanced_player(self, player_id: UUID) -> None:
        """Check balanced player quest progress."""
        # Get active balanced player quest
        result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == QuestType.BALANCED_PLAYER.value,
                    Quest.status == QuestStatus.ACTIVE.value
                )
            )
        )
        quest = result.scalar_one_or_none()

        if not quest:
            return

        # NOTE: This method still uses COUNT queries because it needs 24-hour sliding windows.
        # Incremental tracking would require storing all timestamps and filtering them on each call,
        # which may not be more efficient. Consider caching or periodic background updates if this
        # becomes a performance bottleneck. For now, we accept the query cost since balanced_player
        # is checked less frequently than milestone quests (only on round submission).

        now = datetime.now(UTC)
        window_start = now - timedelta(hours=24)

        # Count rounds in 24h window
        from backend.models.base import RoundType, RoundStatus

        prompts_result = await self.db.execute(
            select(func.count()).select_from(Round).where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == "prompt",
                    Round.status == "submitted",
                    Round.created_at >= window_start
                )
            )
        )
        prompts = prompts_result.scalar() or 0

        copies_result = await self.db.execute(
            select(func.count()).select_from(Round).where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == "copy",
                    Round.status == "submitted",
                    Round.created_at >= window_start
                )
            )
        )
        copies = copies_result.scalar() or 0

        votes_result = await self.db.execute(
            select(func.count()).select_from(Vote).where(
                and_(
                    Vote.player_id == player_id,
                    Vote.created_at >= window_start
                )
            )
        )
        votes = votes_result.scalar() or 0

        # Update progress
        progress = quest.progress
        progress.update({
            "prompts": prompts,
            "copies": copies,
            "votes": votes,
            "window_start": window_start.isoformat(),
        })

        # Check if completed
        if prompts >= 1 and copies >= 2 and votes >= 10:
            quest.status = QuestStatus.COMPLETED.value
            quest.completed_at = now
            logger.info(f"Balanced player quest completed for player {player_id}")

        quest.progress = progress
        self.db.add(quest)
        await self.db.commit()

    async def check_login_streak(self, player_id: UUID) -> None:
        """Update login streak quest."""
        # Get player's last login date
        result = await self.db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            return

        # Get active login streak quest
        quest_result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == QuestType.LOGIN_STREAK_7.value,
                    Quest.status == QuestStatus.ACTIVE.value
                )
            )
        )
        quest = quest_result.scalar_one_or_none()

        if not quest:
            return

        today = date.today()
        progress = quest.progress
        last_login = progress.get("last_login_date")

        if last_login:
            last_date = date.fromisoformat(last_login)
            days_diff = (today - last_date).days

            if days_diff == 1:
                # Consecutive day
                progress["consecutive_days"] += 1
                progress["login_dates"].append(today.isoformat())
            elif days_diff > 1:
                # Streak broken
                progress["consecutive_days"] = 1
                progress["login_dates"] = [today.isoformat()]
            # else: same day, no change
        else:
            # First login
            progress["consecutive_days"] = 1
            progress["login_dates"] = [today.isoformat()]

        progress["last_login_date"] = today.isoformat()

        # Check if completed
        if progress["consecutive_days"] >= 7:
            quest.status = QuestStatus.COMPLETED.value
            quest.completed_at = datetime.now(UTC)
            logger.info(f"Login streak quest completed for player {player_id}")

        quest.progress = progress
        self.db.add(quest)
        await self.db.commit()

    async def increment_feedback_count(self, player_id: UUID) -> None:
        """Track feedback contributions using incremental updates."""
        # Get active feedback quests
        quests_result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.status == QuestStatus.ACTIVE.value,
                    Quest.quest_type.in_([
                        QuestType.FEEDBACK_CONTRIBUTOR_10.value,
                        QuestType.FEEDBACK_CONTRIBUTOR_50.value,
                    ])
                )
            )
        )
        quests = list(quests_result.scalars().all())

        for quest in quests:
            progress = quest.progress
            config = QUEST_CONFIGS[QuestType(quest.quest_type)]

            # Increment the counter instead of recounting from database
            current = progress.get("current", 0)
            progress["current"] = current + 1

            if progress["current"] >= config["target"]:
                quest.status = QuestStatus.COMPLETED.value
                quest.completed_at = datetime.now(UTC)
                logger.info(f"Quest {quest.quest_type} completed for player {player_id}")

            quest.progress = progress
            self.db.add(quest)

        await self.db.commit()

    async def check_milestone_votes(self, player_id: UUID) -> None:
        """Check milestone vote quest using incremental tracking."""
        # Get the active milestone vote quest
        quest_result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == QuestType.MILESTONE_VOTES_100.value,
                    Quest.status == QuestStatus.ACTIVE.value
                )
            )
        )
        quest = quest_result.scalar_one_or_none()

        if quest:
            progress = quest.progress
            config = QUEST_CONFIGS[QuestType.MILESTONE_VOTES_100]

            # Increment the counter instead of recounting from database
            current = progress.get("current", 0)
            progress["current"] = current + 1

            if progress["current"] >= config["target"]:
                quest.status = QuestStatus.COMPLETED.value
                quest.completed_at = datetime.now(UTC)
                logger.info(f"Quest {quest.quest_type} completed for player {player_id}")

            quest.progress = progress
            self.db.add(quest)
            await self.db.commit()

    async def check_milestone_prompts(self, player_id: UUID) -> None:
        """Check milestone prompt quest using incremental tracking."""
        quest_result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == QuestType.MILESTONE_PROMPTS_50.value,
                    Quest.status == QuestStatus.ACTIVE.value
                )
            )
        )
        quest = quest_result.scalar_one_or_none()

        if quest:
            progress = quest.progress
            config = QUEST_CONFIGS[QuestType.MILESTONE_PROMPTS_50]

            # Increment the counter instead of recounting from database
            current = progress.get("current", 0)
            progress["current"] = current + 1

            if progress["current"] >= config["target"]:
                quest.status = QuestStatus.COMPLETED.value
                quest.completed_at = datetime.now(UTC)
                logger.info(f"Quest {quest.quest_type} completed for player {player_id}")

            quest.progress = progress
            self.db.add(quest)
            await self.db.commit()

    async def check_milestone_copies(self, player_id: UUID) -> None:
        """Check milestone copy quest using incremental tracking."""
        quest_result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == QuestType.MILESTONE_COPIES_100.value,
                    Quest.status == QuestStatus.ACTIVE.value
                )
            )
        )
        quest = quest_result.scalar_one_or_none()

        if quest:
            progress = quest.progress
            config = QUEST_CONFIGS[QuestType.MILESTONE_COPIES_100]

            # Increment the counter instead of recounting from database
            current = progress.get("current", 0)
            progress["current"] = current + 1

            if progress["current"] >= config["target"]:
                quest.status = QuestStatus.COMPLETED.value
                quest.completed_at = datetime.now(UTC)
                logger.info(f"Quest {quest.quest_type} completed for player {player_id}")

            quest.progress = progress
            self.db.add(quest)
            await self.db.commit()

    async def check_milestone_phraseset_20votes(
        self, player_id: UUID, phraseset_id: UUID, vote_count: int
    ) -> None:
        """Check if a phraseset reached 20 votes."""
        if vote_count < 20:
            return

        # Get active quest
        result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == QuestType.MILESTONE_PHRASESET_20VOTES.value,
                    Quest.status == QuestStatus.ACTIVE.value
                )
            )
        )
        quest = result.scalar_one_or_none()

        if not quest:
            quest = await self._create_quest(player_id, QuestType.MILESTONE_PHRASESET_20VOTES)

        if quest.status == QuestStatus.ACTIVE.value:
            quest.status = QuestStatus.COMPLETED.value
            quest.completed_at = datetime.now(UTC)
            quest.progress["phraseset_id"] = str(phraseset_id)
            quest.progress["vote_count"] = vote_count
            self.db.add(quest)
            await self.db.commit()
            logger.info(
                f"Phraseset 20 votes milestone completed for player {player_id}"
            )

    async def _check_milestone_quest(
        self, player_id: UUID, quest_type: QuestType, current_count: int
    ) -> None:
        """Generic milestone quest checker."""
        # Get or create quest
        result = await self.db.execute(
            select(Quest).where(
                and_(
                    Quest.player_id == player_id,
                    Quest.quest_type == quest_type.value,
                    or_(
                        Quest.status == QuestStatus.ACTIVE.value,
                        Quest.status == QuestStatus.COMPLETED.value
                    )
                )
            )
        )
        quest = result.scalar_one_or_none()

        if not quest:
            quest = await self._create_quest(player_id, quest_type)

        if quest.status != QuestStatus.ACTIVE.value:
            return

        config = QUEST_CONFIGS[quest_type]
        progress = quest.progress
        progress["current"] = current_count

        if current_count >= config["target"]:
            quest.status = QuestStatus.COMPLETED.value
            quest.completed_at = datetime.now(UTC)
            logger.info(f"Quest {quest_type.value} completed for player {player_id}")

        quest.progress = progress
        self.db.add(quest)
        await self.db.commit()
