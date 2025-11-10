"""Online users API router with WebSocket support."""
from datetime import datetime, UTC, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import logging

from backend.database import get_db, AsyncSessionLocal
from backend.dependencies import get_current_player
from backend.models.user_activity import UserActivity
from backend.models.player import Player
from backend.schemas.online_users import OnlineUser, OnlineUsersResponse
from backend.services.auth_service import AuthService
from backend.services.player_service import PlayerService
from backend.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

settings = get_settings()


async def authenticate_websocket(websocket: WebSocket) -> Optional[Player]:
    """Authenticate a WebSocket connection using token from query params or cookies.

    Returns the authenticated Player or None if authentication fails.
    """
    # Try to get token from query parameters first (for client flexibility)
    token = websocket.query_params.get("token")

    # Fall back to cookie if no query param token
    if not token:
        token = websocket.cookies.get(settings.access_token_cookie_name)

    if not token:
        logger.warning("WebSocket connection attempted without token")
        return None

    # Validate token
    try:
        async with AsyncSessionLocal() as db:
            auth_service = AuthService(db)
            payload = auth_service.decode_access_token(token)

            player_id_str = payload.get("sub")
            if not player_id_str:
                logger.warning("WebSocket token missing player_id")
                return None

            from uuid import UUID
            player_id = UUID(player_id_str)

            player_service = PlayerService(db)
            player = await player_service.get_player_by_id(player_id)

            if not player:
                logger.warning(f"WebSocket token references non-existent player: {player_id}")
                return None

            return player

    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        return None


class ConnectionManager:
    """Manages WebSocket connections for online users updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)


# Global connection manager
manager = ConnectionManager()


async def get_online_users(db: AsyncSession) -> List[OnlineUser]:
    """Get list of users who were active in the last 30 minutes."""
    cutoff_time = datetime.now(UTC) - timedelta(minutes=30)

    result = await db.execute(
        select(UserActivity)
        .where(UserActivity.last_activity >= cutoff_time)
        .order_by(UserActivity.last_activity.desc())
    )
    activities = result.scalars().all()

    # Capture current time once for consistent calculations
    now = datetime.now(UTC)

    online_users = []
    for activity in activities:
        # Calculate time ago
        time_diff = now - activity.last_activity
        seconds = int(time_diff.total_seconds())

        if seconds < 60:
            time_ago = f"{seconds}s ago"
        elif seconds < 3600:
            minutes = seconds // 60
            time_ago = f"{minutes}m ago"
        else:
            hours = seconds // 3600
            time_ago = f"{hours}h ago"

        online_users.append(
            OnlineUser(
                username=activity.username,
                last_action=activity.last_action,
                last_activity=activity.last_activity,
                time_ago=time_ago,
            )
        )

    return online_users


@router.get("/online", response_model=OnlineUsersResponse)
async def get_online_users_endpoint(
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """Get list of currently online users (last 30 minutes)."""
    online_users = await get_online_users(db)

    return OnlineUsersResponse(
        users=online_users,
        total_count=len(online_users),
    )


@router.websocket("/online/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time online users updates.

    Requires authentication via token in query params (?token=...) or cookies.
    """
    # Authenticate before accepting connection
    player = await authenticate_websocket(websocket)

    if not player:
        # Reject unauthenticated connection
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        logger.info("WebSocket connection rejected: authentication failed")
        return

    # Accept authenticated connection
    await manager.connect(websocket)
    logger.info(f"WebSocket authenticated for player: {player.username}")

    try:
        # Get database session for this WebSocket connection
        async with AsyncSessionLocal() as db:
            while True:
                # Send updates every 5 seconds
                online_users = await get_online_users(db)

                message = {
                    "type": "online_users_update",
                    "users": [user.model_dump(mode="json") for user in online_users],
                    "total_count": len(online_users),
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                await websocket.send_json(message)

                # Wait 5 seconds before next update
                await asyncio.sleep(5)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for player: {player.username}")
    except Exception as e:
        logger.error(f"WebSocket error for player {player.username}: {e}")
        manager.disconnect(websocket)
