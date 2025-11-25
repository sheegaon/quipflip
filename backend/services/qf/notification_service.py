"""
Service for managing notifications and WebSocket delivery.

Handles:
- Creating notifications when players interact with phrasesets
- Filtering human players (excluding AI)
- Sending notifications via WebSocket
- Rate limiting (max 10 notifications per player per minute)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.qf.notification import QFNotification
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.schemas.notification import NotificationWebSocketMessage
from backend.services.ai.ai_service import AI_PLAYER_EMAIL_DOMAIN
from backend.services.qf.websocket_notification_service import (
    WebSocketNotificationService,
    get_websocket_notification_service,
)

logger = logging.getLogger(__name__)

# Rate limiting: max notifications per player per minute
MAX_NOTIFICATIONS_PER_MINUTE = 10


def _is_human_player(player: Optional[QFPlayer]) -> bool:
    """Check if player is human (not AI)."""
    if not player or not player.email:
        return False
    return not player.email.endswith(AI_PLAYER_EMAIL_DOMAIN)


def _truncate_phrase(text: str, max_length: int = 50) -> str:
    """Truncate phrase text to max_length, adding '...' if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


class NotificationService:
    """Service for managing notifications and WebSocket delivery."""

    def __init__(
        self,
        db: AsyncSession,
        connection_manager: Optional["NotificationConnectionManager"] = None,
    ):
        self.db = db
        # Default to the global singleton so callers don't need to manually inject it
        self._connection_manager: Optional["NotificationConnectionManager"] = (
            connection_manager or get_notification_manager()
        )

    def set_connection_manager(self, manager: "NotificationConnectionManager") -> None:
        """Set the WebSocket connection manager (injected by router)."""
        self._connection_manager = manager

    async def notify_copy_submission(
        self,
        phraseset: Phraseset,
        copy_player_id: UUID,
        prompt_round: Round,
    ) -> None:
        """
        Notify the prompt player when someone copies their prompt.
        If this is a second copy, notify the first copy player as well.

        Only notifies if:
        - Both actor and recipient are human
        - Actor != recipient (no self-notifications)
        """
        notifications_created = False

        # Get players
        copy_player = await self.db.get(QFPlayer, copy_player_id)
        prompt_player = await self.db.get(QFPlayer, prompt_round.player_id)

        # Validate copy player is human
        if not _is_human_player(copy_player):
            logger.info(f"Copy player {copy_player_id} is AI, skipping notification")
            return

        prompt_notified = await self._notify_copy_recipient(
            phraseset=phraseset,
            recipient=prompt_player,
            recipient_role="prompt",
            actor_player_id=copy_player_id,
            actor_username=copy_player.username,
            phrase_text=phraseset.prompt_text,
        )
        notifications_created = notifications_created or prompt_notified

        # If this submission filled the second copy slot, notify the first copy player
        first_copy_player_id = prompt_round.copy1_player_id
        is_second_copy = (
            prompt_round.copy2_player_id is not None
            and prompt_round.copy2_player_id == copy_player_id
        )

        if is_second_copy and first_copy_player_id:
            # Get the first copy player
            first_copy_player = await self.db.get(QFPlayer, first_copy_player_id)

            first_copy_notified = await self._notify_copy_recipient(
                phraseset=phraseset,
                recipient=first_copy_player,
                recipient_role="copy",
                actor_player_id=copy_player_id,
                actor_username=copy_player.username,
                phrase_text=phraseset.copy_phrase_1,
            )
            notifications_created = notifications_created or first_copy_notified

        if notifications_created:
            await self.db.commit()

    async def _notify_copy_recipient(
        self,
        *,
        phraseset: Phraseset,
        recipient: Optional[QFPlayer],
        recipient_role: str,
        actor_player_id: UUID,
        actor_username: str,
        phrase_text: Optional[str],
    ) -> bool:
        """Notify a copy recipient (prompt or first copy player)."""

        if not recipient:
            logger.info("Recipient player not found, skipping notification")
            return False

        if not _is_human_player(recipient):
            logger.info(
                f"Recipient player {recipient.player_id} is AI, skipping notification"
            )
            return False

        if recipient.player_id == actor_player_id:
            logger.info("Actor is same as recipient, skipping self-notification")
            return False

        if not await self._check_rate_limit(recipient.player_id):
            logger.warning(
                f"Rate limit exceeded for player {recipient.player_id}, skipping notification"
            )
            return False

        truncated_phrase = _truncate_phrase(phrase_text or "")
        metadata = {
            "phrase_text": truncated_phrase,
            "recipient_role": recipient_role,
            "actor_username": actor_username,
        }

        notification = await self._create_notification(
            player_id=recipient.player_id,
            notification_type="copy_submitted",
            phraseset_id=phraseset.phraseset_id,
            actor_player_id=actor_player_id,
            metadata=metadata,
        )

        if self._connection_manager:
            message = NotificationWebSocketMessage(
                notification_type="copy_submitted",
                actor_username=actor_username,
                action="copied",
                recipient_role=recipient_role,
                phrase_text=truncated_phrase,
                timestamp=notification.created_at.isoformat(),
            )
            await self._connection_manager.send_to_player(
                recipient.player_id, message.model_dump()
            )

        logger.info(
            f"Created copy notification for player {recipient.player_id} "
            f"from {actor_player_id} on phraseset {phraseset.phraseset_id}"
        )

        return True

    async def notify_vote_submission(
        self,
        phraseset: Phraseset,
        voter_player_id: UUID,
    ) -> None:
        """
        Notify all contributors when someone votes.

        Only notifies human contributors, excludes voter.
        Each contributor gets a notification with their specific role and phrase.
        """
        # Get voter
        voter = await self.db.get(QFPlayer, voter_player_id)

        # Skip if voter is AI
        if not _is_human_player(voter):
            logger.info(f"Voter {voter_player_id} is AI, skipping notifications")
            return

        # Get all contributors with their role and phrase
        contributors = await self._get_contributor_data(phraseset)

        notifications_created = False

        for contributor in contributors:
            contributor_id = contributor["player_id"]
            role = contributor["role"]
            phrase_text = contributor["phrase"]

            # Skip if voter is same as contributor
            if voter_player_id == contributor_id:
                logger.info(f"Skipping self-notification for voter {voter_player_id}")
                continue

            # Get contributor player
            contributor_player = await self.db.get(QFPlayer, contributor_id)
            if not _is_human_player(contributor_player):
                logger.info(f"Contributor {contributor_id} is AI, skipping notification")
                continue

            # Check rate limit
            if not await self._check_rate_limit(contributor_id):
                logger.warning(
                    f"Rate limit exceeded for player {contributor_id}, skipping notification"
                )
                continue

            # Create notification
            truncated_phrase = _truncate_phrase(phrase_text or "")
            metadata = {
                "phrase_text": truncated_phrase,
                "recipient_role": role,
                "actor_username": voter.username,
            }

            notification = await self._create_notification(
                player_id=contributor_id,
                notification_type="vote_submitted",
                phraseset_id=phraseset.phraseset_id,
                actor_player_id=voter_player_id,
                metadata=metadata,
            )
            notifications_created = True

            # Send via WebSocket if connected
            if self._connection_manager:
                message = NotificationWebSocketMessage(
                    notification_type="vote_submitted",
                    actor_username=voter.username,
                    action="voted on",
                    recipient_role=role,
                    phrase_text=truncated_phrase,
                    timestamp=notification.created_at.isoformat(),
                )
                await self._connection_manager.send_to_player(
                    contributor_id, message.model_dump()
                )

            logger.info(
                f"Created vote notification for player {contributor_id} "
                f"from {voter_player_id} on phraseset {phraseset.phraseset_id}"
            )

        if notifications_created:
            await self.db.commit()

    async def _get_contributor_data(self, phraseset: Phraseset) -> List[Dict]:
        """
        Get all contributors to a phraseset with their role and phrase.

        Returns: [
            {player_id: UUID, role: 'prompt', phrase: 'prompt_text'},
            {player_id: UUID, role: 'copy', phrase: 'copy_phrase'},
            ...
        ]
        """
        contributors = []

        # Get prompt contributor
        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        if prompt_round:
            contributors.append(
                {
                    "player_id": prompt_round.player_id,
                    "role": "prompt",
                    "phrase": phraseset.prompt_text,
                }
            )

        # Get copy 1 contributor
        if phraseset.copy_round_1_id:
            copy_round_1 = await self.db.get(Round, phraseset.copy_round_1_id)
            if copy_round_1:
                contributors.append(
                    {
                        "player_id": copy_round_1.player_id,
                        "role": "copy",
                        "phrase": phraseset.copy_phrase_1,
                    }
                )

        # Get copy 2 contributor
        if phraseset.copy_round_2_id:
            copy_round_2 = await self.db.get(Round, phraseset.copy_round_2_id)
            if copy_round_2:
                contributors.append(
                    {
                        "player_id": copy_round_2.player_id,
                        "role": "copy",
                        "phrase": phraseset.copy_phrase_2,
                    }
                )

        return contributors

    async def _check_rate_limit(self, player_id: UUID) -> bool:
        """
        Check if player has exceeded rate limit (max 10 notifications per minute).

        Returns False if rate limit exceeded, True if within limit.
        """
        # Get notifications created in the last minute
        one_minute_ago = datetime.now(timezone.utc) - timedelta(minutes=1)

        stmt = (
            select(func.count())
            .select_from(QFNotification)
            .where(
                and_(
                    QFNotification.player_id == player_id,
                    QFNotification.created_at > one_minute_ago,
                )
            )
        )

        result = await self.db.execute(stmt)
        recent_notification_count = result.scalar_one()

        if recent_notification_count >= MAX_NOTIFICATIONS_PER_MINUTE:
            return False

        return True

    async def _create_notification(
        self,
        player_id: UUID,
        notification_type: str,
        phraseset_id: UUID,
        actor_player_id: Optional[UUID],
        metadata: Optional[dict],
    ) -> QFNotification:
        """Create and store a notification in the database."""
        notification = QFNotification(
            player_id=player_id,
            notification_type=notification_type,
            phraseset_id=phraseset_id,
            actor_player_id=actor_player_id,
            data=metadata,
        )

        self.db.add(notification)
        await self.db.flush()  # Ensure it's persisted before returning

        return notification


class NotificationConnectionManager:
    """
    Manages WebSocket connections for push notifications.

    Unlike broadcast patterns (e.g., online_users), this targets specific players.
    Stores per-player WebSocket connections.
    """

    def __init__(
        self, websocket_service: WebSocketNotificationService | None = None
    ) -> None:
        self._websocket_service = (
            websocket_service or get_websocket_notification_service()
        )

    @staticmethod
    def _channel_for_player(player_id: str) -> str:
        return f"player:{player_id}"

    async def connect(self, player_id: str, websocket: "WebSocket") -> None:
        """Add player's WebSocket connection."""
        player_id_str = str(player_id)
        await self._websocket_service.connect(
            self._channel_for_player(player_id_str), player_id_str, websocket
        )
        logger.info(f"WebSocket connected for player {player_id}")

    async def disconnect(self, player_id: str) -> None:
        """Remove player's WebSocket connection."""
        player_id_str = str(player_id)
        connection = await self._websocket_service.disconnect(
            self._channel_for_player(player_id_str), player_id_str
        )
        if connection:
            logger.info(f"WebSocket disconnected for player {player_id}")

    async def send_to_player(self, player_id: UUID, message: dict) -> None:
        """
        Send message to specific player if connected.

        Fails silently if player not connected or connection fails.
        """
        player_id_str = str(player_id)
        await self._websocket_service.send(
            self._channel_for_player(player_id_str), player_id_str, message
        )


# Global singleton instance
_connection_manager = NotificationConnectionManager()


def get_notification_manager() -> NotificationConnectionManager:
    """Get the global NotificationConnectionManager singleton."""
    return _connection_manager
