"""Shared WebSocket notification service.

Centralizes connection tracking for both party mode and per-player
notifications so the application has a single place that knows how to
accept, store, broadcast, and clean up WebSocket connections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """Metadata about a single WebSocket connection."""

    websocket: "WebSocket"
    context: Optional[str] = None


class WebSocketNotificationService:
    """Manage WebSocket connections grouped by arbitrary channel IDs."""

    def __init__(self) -> None:
        # Map channel_id (str) → client_id (str) → WebSocketConnection
        self._channels: Dict[str, Dict[str, WebSocketConnection]] = {}

    async def connect(
        self,
        channel_id: str,
        client_id: str,
        websocket: "WebSocket",
        *,
        context: Optional[str] = None,
    ) -> None:
        """Accept and store a connection for later targeted delivery."""

        await websocket.accept()

        channel_connections = self._channels.setdefault(channel_id, {})
        channel_connections[client_id] = WebSocketConnection(
            websocket=websocket, context=context
        )
        logger.debug(
            "Registered websocket client %s in channel %s", client_id, channel_id
        )

    async def disconnect(
        self, channel_id: str, client_id: str
    ) -> Optional[WebSocketConnection]:
        """Remove a connection from the given channel."""

        channel_connections = self._channels.get(channel_id)
        if not channel_connections:
            return None

        connection = channel_connections.pop(client_id, None)

        if connection:
            logger.debug(
                "Removed websocket client %s from channel %s", client_id, channel_id
            )

        if not channel_connections:
            self._channels.pop(channel_id, None)

        return connection

    def get_connection_context(self, channel_id: str, client_id: str) -> Optional[str]:
        """Return the stored context for a connection if present."""

        connection = self._channels.get(channel_id, {}).get(client_id)
        if connection:
            return connection.context
        return None

    def get_connection_count(self, channel_id: str) -> int:
        """Return how many clients are connected to a channel."""

        channel_connections = self._channels.get(channel_id)
        return len(channel_connections) if channel_connections else 0

    async def broadcast(
        self,
        channel_id: str,
        message: dict,
        exclude_client_id: Optional[str] = None,
    ) -> None:
        """Broadcast a message to every client in a channel."""

        channel_connections = self._channels.get(channel_id)
        if not channel_connections:
            logger.debug("Channel %s has no connections, skipping broadcast", channel_id)
            return

        disconnected: list[str] = []

        for client_id, connection in list(channel_connections.items()):
            if exclude_client_id and client_id == exclude_client_id:
                continue

            websocket = connection.websocket
            if websocket is None:
                logger.debug(
                    "Missing websocket instance for client %s in channel %s",
                    client_id,
                    channel_id,
                )
                disconnected.append(client_id)
                continue

            try:
                await websocket.send_json(message)
            except Exception as exc:  # pragma: no cover - network stack
                logger.warning(
                    "Failed to send websocket message to %s in channel %s: %s",
                    client_id,
                    channel_id,
                    exc,
                )
                disconnected.append(client_id)

        for client_id in disconnected:
            await self.disconnect(channel_id, client_id)

    async def send(self, channel_id: str, client_id: str, message: dict) -> None:
        """Send a message to a specific client in a channel."""

        channel_connections = self._channels.get(channel_id)
        if not channel_connections:
            logger.debug(
                "Channel %s has no connections for client %s", channel_id, client_id
            )
            return

        connection = channel_connections.get(client_id)
        if not connection:
            logger.debug(
                "Client %s not connected in channel %s", client_id, channel_id
            )
            return

        websocket = connection.websocket
        if websocket is None:
            logger.debug(
                "Missing websocket instance for client %s in channel %s",
                client_id,
                channel_id,
            )
            await self.disconnect(channel_id, client_id)
            return

        try:
            await websocket.send_json(message)
        except Exception as exc:  # pragma: no cover - network stack
            logger.warning(
                "Failed to send websocket message to %s in channel %s: %s",
                client_id,
                channel_id,
                exc,
            )
            await self.disconnect(channel_id, client_id)


_websocket_service = WebSocketNotificationService()


def get_websocket_notification_service() -> WebSocketNotificationService:
    """Return the singleton WebSocketNotificationService instance."""

    return _websocket_service
