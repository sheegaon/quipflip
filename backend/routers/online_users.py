"""Online users API router with WebSocket support."""
from datetime import datetime, UTC, timedelta
from typing import List
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import logging
import json

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.user_activity import UserActivity
from backend.models.player import Player
from backend.schemas.online_users import OnlineUser, OnlineUsersResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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

    online_users = []
    for activity in activities:
        # Calculate time ago
        time_diff = datetime.now(UTC) - activity.last_activity
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
    """WebSocket endpoint for real-time online users updates."""
    await manager.connect(websocket)

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
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# Import AsyncSessionLocal for WebSocket connection
from backend.database import AsyncSessionLocal
