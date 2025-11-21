"""Party Mode WebSocket manager for real-time session updates."""
import logging
from typing import Dict, List
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PartyWebSocketManager:
    """
    Manages WebSocket connections for Party Mode sessions.

    Groups connections by session_id to enable session-wide broadcasts.
    Each session can have multiple connected players.
    """

    def __init__(self):
        # Map session_id (str) → { player_id (str): { 'websocket': WebSocket, 'context': str | None } }
        self.session_connections: Dict[str, Dict[str, Dict[str, object]]] = {}

    async def connect(
        self,
        session_id: UUID,
        player_id: UUID,
        websocket: "WebSocket",
        db: AsyncSession = None,
        context: str | None = None,
    ) -> None:
        """Add player's WebSocket connection to a session.

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player
            websocket: WebSocket connection to add
            db: Optional database session to update connection status
            context: Optional string describing where the connection originated (e.g., 'lobby')
        """
        await websocket.accept()

        session_id_str = str(session_id)
        player_id_str = str(player_id)

        # Initialize session dict if needed
        if session_id_str not in self.session_connections:
            self.session_connections[session_id_str] = {}

        # Store player's connection and context
        self.session_connections[session_id_str][player_id_str] = {
            'websocket': websocket,
            'context': context,
        }

        # Update participant connection status in database
        if db:
            from backend.models.qf.party_participant import PartyParticipant
            from backend.models.qf.party_session import PartySession

            result = await db.execute(
                select(PartyParticipant, PartySession)
                .join(PartySession, PartyParticipant.session_id == PartySession.session_id)
                .where(
                    and_(
                        PartyParticipant.session_id == session_id,
                        PartyParticipant.player_id == player_id
                    )
                )
            )
            row = result.first()

            if row:
                participant, session = row
                participant.connection_status = 'connected'
                participant.last_activity_at = datetime.now(UTC)
                participant.disconnected_at = None
                if session.status == 'OPEN' and context == 'lobby':
                    participant.status = 'READY'
                    participant.ready_at = datetime.now(UTC)
                await db.commit()
                logger.info(f"Updated participant {player_id} to connected status")

                if session.status == 'OPEN' and context == 'lobby':
                    await self.notify_session_update(
                        session_id=session_id,
                        session_status={
                            'reason': 'lobby_presence_changed',
                            'message': 'player_reconnected'
                        }
                    )

        logger.info(
            f"WebSocket connected for player {player_id} in session {session_id} "
            f"(total connections in session: {len(self.session_connections[session_id_str])})"
        )

    async def disconnect(
        self,
        session_id: UUID,
        player_id: UUID,
        db: AsyncSession = None,
        context: str | None = None,
    ) -> None:
        """Remove player's WebSocket connection from a session.

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player
            db: Optional database session to update connection status
        """
        session_id_str = str(session_id)
        player_id_str = str(player_id)

        connection_context = context

        if session_id_str in self.session_connections:
            player_connection = self.session_connections[session_id_str].get(player_id_str)
            if player_connection:
                connection_context = connection_context or player_connection.get('context')
                del self.session_connections[session_id_str][player_id_str]
                logger.info(f"WebSocket disconnected for player {player_id} in session {session_id}")

                # Update participant connection status in database
                if db:
                    from backend.models.qf.party_participant import PartyParticipant
                    from backend.models.qf.party_session import PartySession

                    result = await db.execute(
                        select(PartyParticipant, PartySession)
                        .join(PartySession, PartyParticipant.session_id == PartySession.session_id)
                        .where(
                            and_(
                                PartyParticipant.session_id == session_id,
                                PartyParticipant.player_id == player_id
                            )
                        )
                    )
                    row = result.first()

                    if row:
                        participant, session = row
                        participant.connection_status = 'disconnected'
                        participant.disconnected_at = datetime.now(UTC)
                        participant.last_activity_at = datetime.now(UTC)
                        if session.status == 'OPEN' and connection_context == 'lobby':
                            participant.status = 'JOINED'
                            participant.ready_at = None
                        await db.commit()
                        logger.info(f"Updated participant {player_id} to disconnected status")

                        if session.status == 'OPEN' and connection_context == 'lobby':
                            await self.notify_session_update(
                                session_id=session_id,
                                session_status={
                                    'reason': 'lobby_presence_changed',
                                    'message': 'player_disconnected'
                                }
                            )

                # Clean up empty session dict
                if not self.session_connections[session_id_str]:
                    del self.session_connections[session_id_str]
                    logger.info(f"Removed empty session {session_id} from connections")

    async def broadcast_to_session(
        self,
        session_id: UUID,
        message: dict,
        exclude_player_id: UUID = None,
    ) -> None:
        """Broadcast message to all connected players in a session.

        Args:
            session_id: UUID of the party session
            message: Message dict to send
            exclude_player_id: Optional player ID to exclude from broadcast
        """
        session_id_str = str(session_id)

        if session_id_str not in self.session_connections:
            logger.debug(f"Session {session_id} has no connections, skipping broadcast")
            return

        connections = self.session_connections[session_id_str].copy()
        exclude_player_id_str = str(exclude_player_id) if exclude_player_id else None

        disconnected = []

        for player_id_str, connection in connections.items():
            websocket = connection.get('websocket') if isinstance(connection, dict) else None

            if websocket is None:
                logger.debug(
                    f"No websocket found for player {player_id_str} in session {session_id}, skipping"
                )
                disconnected.append(player_id_str)
                continue
            # Skip excluded player
            if exclude_player_id_str and player_id_str == exclude_player_id_str:
                continue

            try:
                await websocket.send_json(message)
                logger.debug(f"Sent message to player {player_id_str} in session {session_id}")
            except Exception as e:
                logger.warning(
                    f"Failed to send WebSocket to player {player_id_str} in session {session_id}: {e}"
                )
                disconnected.append(player_id_str)

        # Clean up disconnected players
        for player_id_str in disconnected:
            if player_id_str in self.session_connections.get(session_id_str, {}):
                del self.session_connections[session_id_str][player_id_str]

        # Clean up empty session
        if session_id_str in self.session_connections and not self.session_connections[session_id_str]:
            del self.session_connections[session_id_str]

    async def send_to_player(
        self,
        session_id: UUID,
        player_id: UUID,
        message: dict,
    ) -> None:
        """Send message to a specific player in a session.

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player
            message: Message dict to send
        """
        session_id_str = str(session_id)
        player_id_str = str(player_id)

        if session_id_str not in self.session_connections:
            logger.debug(f"Session {session_id} has no connections, skipping send")
            return

        if player_id_str not in self.session_connections[session_id_str]:
            logger.debug(
                f"Player {player_id} not connected to session {session_id}, skipping send"
            )
            return

        try:
            connection = self.session_connections[session_id_str][player_id_str]
            websocket = connection.get('websocket') if isinstance(connection, dict) else None
            if websocket is None:
                logger.debug(
                    f"Missing websocket for player {player_id} in session {session_id}, removing stale connection"
                )
                await self.disconnect(session_id, player_id)
                return
            await websocket.send_json(message)
            logger.debug(f"Sent message to player {player_id} in session {session_id}")
        except Exception as e:
            logger.warning(
                f"Failed to send WebSocket to player {player_id} in session {session_id}: {e}"
            )
            # Remove disconnected player
            await self.disconnect(session_id, player_id)

    async def notify_phase_transition(
        self,
        session_id: UUID,
        old_phase: str,
        new_phase: str,
        message: str = "",
    ) -> None:
        """Notify all players in session of phase transition.

        Args:
            session_id: UUID of the party session
            old_phase: Previous phase name
            new_phase: New phase name
            message: Optional message to include
        """
        notification = {
            'type': 'phase_transition',
            'session_id': str(session_id),
            'old_phase': old_phase,
            'new_phase': new_phase,
            'message': message,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.info(f"Sent phase transition notification to session {session_id}: {old_phase} → {new_phase}")

    async def notify_player_progress(
        self,
        session_id: UUID,
        player_id: UUID,
        username: str,
        action: str,
        progress: dict,
        session_progress: dict,
    ) -> None:
        """Notify all players in session of player progress update.

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player who made progress
            username: Username of the player
            action: Action taken (e.g., 'submitted_prompt')
            progress: Player's current progress dict
            session_progress: Session-wide progress dict
        """
        notification = {
            'type': 'progress_update',
            'session_id': str(session_id),
            'player_id': str(player_id),
            'username': username,
            'action': action,
            'progress': progress,
            'session_progress': session_progress,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.info(f"Sent progress update to session {session_id}: {username} {action}")

    async def notify_player_joined(
        self,
        session_id: UUID,
        player_id: UUID,
        username: str,
        participant_count: int,
    ) -> None:
        """Notify all players that someone joined the session.

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player who joined
            username: Username of the player
            participant_count: Total number of participants
        """
        notification = {
            'type': 'player_joined',
            'session_id': str(session_id),
            'player_id': str(player_id),
            'username': username,
            'participant_count': participant_count,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        # Don't send to the player who just joined
        await self.broadcast_to_session(session_id, notification, exclude_player_id=player_id)
        logger.info(f"Sent player joined notification to session {session_id}: {username}")

    async def notify_player_left(
        self,
        session_id: UUID,
        player_id: UUID,
        username: str,
        participant_count: int,
    ) -> None:
        """Notify all players that someone left the session.

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player who left
            username: Username of the player
            participant_count: Total number of participants
        """
        notification = {
            'type': 'player_left',
            'session_id': str(session_id),
            'player_id': str(player_id),
            'username': username,
            'participant_count': participant_count,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.info(f"Sent player left notification to session {session_id}: {username}")

    async def notify_player_ready(
        self,
        session_id: UUID,
        player_id: UUID,
        username: str,
        ready_count: int,
        total_count: int,
    ) -> None:
        """Notify all players that someone marked ready.

        Args:
            session_id: UUID of the party session
            player_id: UUID of the player who marked ready
            username: Username of the player
            ready_count: Number of ready players
            total_count: Total number of players
        """
        notification = {
            'type': 'player_ready',
            'session_id': str(session_id),
            'player_id': str(player_id),
            'username': username,
            'ready_count': ready_count,
            'total_count': total_count,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.info(f"Sent player ready notification to session {session_id}: {username}")

    async def notify_host_ping(
        self,
        session_id: UUID,
        host_player_id: UUID,
        host_username: str,
        join_url: str,
    ) -> None:
        """Notify all players that the host pinged the lobby."""

        notification = {
            'type': 'host_ping',
            'session_id': str(session_id),
            'data': {
                'host_player_id': str(host_player_id),
                'host_username': host_username,
                'join_url': join_url,
            },
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.info(f"Sent host ping notification to session {session_id}")

    async def notify_session_started(
        self,
        session_id: UUID,
        current_phase: str,
        participant_count: int,
        message: str = "",
    ) -> None:
        """Notify all players that the session has started.

        Args:
            session_id: UUID of the party session
            current_phase: Current phase after starting
            participant_count: Number of participants
            message: Optional message to include
        """
        notification = {
            'type': 'session_started',
            'session_id': str(session_id),
            'current_phase': current_phase,
            'participant_count': participant_count,
            'message': message,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.info(f"Sent session started notification to session {session_id}")

    async def notify_session_completed(
        self,
        session_id: UUID,
        completed_at: datetime,
        message: str = "",
    ) -> None:
        """Notify all players that the session has completed.

        Args:
            session_id: UUID of the party session
            completed_at: Completion timestamp
            message: Optional message to include
        """
        notification = {
            'type': 'session_completed',
            'session_id': str(session_id),
            'completed_at': completed_at.isoformat() if completed_at else None,
            'message': message,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.info(f"Sent session completed notification to session {session_id}")

    async def notify_session_update(
        self,
        session_id: UUID,
        session_status: dict,
    ) -> None:
        """Notify all players of general session status update.

        Args:
            session_id: UUID of the party session
            session_status: Complete session status dict
        """
        notification = {
            'type': 'session_update',
            'session_id': str(session_id),
            **session_status,
            'timestamp': datetime.now(UTC).isoformat(),
        }

        await self.broadcast_to_session(session_id, notification)
        logger.debug(f"Sent session update to session {session_id}")

    def get_connection_count(self, session_id: UUID) -> int:
        """Get number of connected players in a session.

        Args:
            session_id: UUID of the party session

        Returns:
            int: Number of connected players
        """
        session_id_str = str(session_id)
        if session_id_str not in self.session_connections:
            return 0
        return len(self.session_connections[session_id_str])


# Global singleton instance
_party_ws_manager = PartyWebSocketManager()


def get_party_websocket_manager() -> PartyWebSocketManager:
    """Get the global PartyWebSocketManager singleton."""
    return _party_ws_manager
