"""
Service for managing notifications and WebSocket delivery.

Handles:
- Creating notifications when players interact with phrasesets
- Filtering human players (excluding AI)
- Sending notifications via WebSocket
- Rate limiting (max 10 notifications per player per minute)
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.notification import Notification
from backend.models.phraseset import Phraseset
from backend.models.player import Player
from backend.models.round import Round
from backend.schemas.notification import NotificationWebSocketMessage

logger = logging.getLogger(__name__)

# AI players have emails ending with this domain
AI_PLAYER_EMAIL_DOMAIN = "@quipflip.internal"

# Rate limiting: max notifications per player per minute
MAX_NOTIFICATIONS_PER_MINUTE = 10


def _is_human_player(player: Optional[Player]) -> bool:
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

    def __init__(self, db: AsyncSession):
        self.db = db
        self._connection_manager: Optional["NotificationConnectionManager"] = None

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

        Only notifies if:
        - Both actor and recipient are human
        - Actor != recipient (no self-notifications)
        """
        # Get players
        copy_player = await self.db.get(Player, copy_player_id)
        prompt_player = await self.db.get(Player, prompt_round.player_id)

        # Validate both are human
        if not _is_human_player(copy_player):
            logger.info(f"Copy player {copy_player_id} is AI, skipping notification")
            return

        if not _is_human_player(prompt_player):
            logger.info(f"Prompt player {prompt_round.player_id} is AI, skipping notification")
            return

        # Skip self-notification
        if copy_player_id == prompt_round.player_id:
            logger.info("Copy player is same as prompt player, skipping self-notification")
            return

        # Check rate limit
        if not await self._check_rate_limit(prompt_round.player_id):
            logger.warning(
                f"Rate limit exceeded for player {prompt_round.player_id}, skipping notification"
            )
            return

        # Create notification
        truncated_phrase = _truncate_phrase(phraseset.prompt_text or "")
        metadata = {
            "phrase_text": truncated_phrase,
            "recipient_role": "prompt",
            "actor_username": copy_player.username,
        }

        notification = await self._create_notification(
            player_id=prompt_round.player_id,
            notification_type="copy_submitted",
            phraseset_id=phraseset.phraseset_id,
            actor_player_id=copy_player_id,
            metadata=metadata,
        )

        # Send via WebSocket if connected
        if self._connection_manager:
            message = NotificationWebSocketMessage(
                notification_type="copy_submitted",
                actor_username=copy_player.username,
                action="copied",
                recipient_role="prompt",
                phrase_text=truncated_phrase,
                timestamp=notification.created_at.isoformat(),
            )
            await self._connection_manager.send_to_player(
                prompt_round.player_id, message.model_dump()
            )

        logger.info(
            f"Created copy notification for player {prompt_round.player_id} "
            f"from {copy_player_id} on phraseset {phraseset.phraseset_id}"
        )

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
        voter = await self.db.get(Player, voter_player_id)

        # Skip if voter is AI
        if not _is_human_player(voter):
            logger.info(f"Voter {voter_player_id} is AI, skipping notifications")
            return

        # Get all contributors with their role and phrase
        contributors = await self._get_contributor_data(phraseset)

        for contributor in contributors:
            contributor_id = contributor["player_id"]
            role = contributor["role"]
            phrase_text = contributor["phrase"]

            # Skip if voter is same as contributor
            if voter_player_id == contributor_id:
                logger.info(f"Skipping self-notification for voter {voter_player_id}")
                continue

            # Get contributor player
            contributor_player = await self.db.get(Player, contributor_id)
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

        stmt = select(Notification).where(
            and_(
                Notification.player_id == player_id,
                Notification.created_at > one_minute_ago,
            )
        )

        result = await self.db.execute(stmt)
        recent_notifications = result.scalars().all()

        if len(recent_notifications) >= MAX_NOTIFICATIONS_PER_MINUTE:
            return False

        return True

    async def _create_notification(
        self,
        player_id: UUID,
        notification_type: str,
        phraseset_id: UUID,
        actor_player_id: Optional[UUID],
        metadata: Optional[dict],
    ) -> Notification:
        """Create and store a notification in the database."""
        notification = Notification(
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

    def __init__(self):
        # Map player_id (UUID) → WebSocket connection
        self.active_connections: Dict[str, "WebSocket"] = {}

    async def connect(self, player_id: str, websocket: "WebSocket") -> None:
        """Add player's WebSocket connection."""
        await websocket.accept()
        self.active_connections[str(player_id)] = websocket
        logger.info(f"WebSocket connected for player {player_id}")

    async def disconnect(self, player_id: str) -> None:
        """Remove player's WebSocket connection."""
        if str(player_id) in self.active_connections:
            del self.active_connections[str(player_id)]
            logger.info(f"WebSocket disconnected for player {player_id}")

    async def send_to_player(self, player_id: UUID, message: dict) -> None:
        """
        Send message to specific player if connected.

        Fails silently if player not connected or connection fails.
        """
        player_id_str = str(player_id)

        if player_id_str not in self.active_connections:
            logger.debug(f"Player {player_id} not connected, skipping WebSocket send")
            return

        try:
            websocket = self.active_connections[player_id_str]
            await websocket.send_json(message)
            logger.debug(f"Sent notification to player {player_id} via WebSocket")
        except Exception as e:
            logger.warning(f"Failed to send WebSocket to player {player_id}: {e}")
            # Fail silently - remove connection
            await self.disconnect(player_id_str)


# Global singleton instance
_connection_manager = NotificationConnectionManager()


def get_notification_manager() -> NotificationConnectionManager:
    """Get the global NotificationConnectionManager singleton."""
    return _connection_manager
