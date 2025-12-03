"""
WebSocket router for push notifications.

Handles WebSocket connections and authentication using short-lived tokens.
Coordinates with NotificationService to send notifications to connected clients.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, WebSocketException, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket

from backend.database import get_db
from backend.services import AuthService, AuthError
from backend.services.qf import NotificationConnectionManager, get_notification_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def authenticate_websocket(websocket: WebSocket, token: str, auth_service: AuthService) -> UUID:
    """
    Authenticate WebSocket connection using short-lived token.

    Returns the authenticated player_id if valid.
    Closes connection with code 1008 if invalid.
    """
    try:
        # Decode token using AuthService
        payload = auth_service.decode_access_token(token)
        player_id = UUID(payload.get("sub"))
        return player_id
    except AuthError as exc:
        logger.warning(f"WebSocket authentication failed: {exc}")
        await websocket.close(code=1008, reason="Authentication failed")
        raise WebSocketException(code=1008, reason="Authentication failed")
    except ValueError as exc:
        logger.warning(f"Invalid player ID in WebSocket token: {exc}")
        await websocket.close(code=1008, reason="Authentication failed")
        raise WebSocketException(code=1008, reason="Authentication failed")


@router.websocket("/notifications/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,
    db: AsyncSession = Depends(get_db),
    connection_manager: NotificationConnectionManager = Depends(get_notification_manager),
):
    """
    WebSocket endpoint for receiving push notifications.

    Query parameters:
        token (str): Short-lived JWT token from /api/auth/ws-token

    Authentication:
        - Token is validated using AuthService.decode_access_token()
        - Invalid tokens close connection with code 1008

    Message format:
        {
            "type": "notification",
            "notification_type": "copy_submitted" | "vote_submitted",
            "actor_username": "Alice",
            "action": "copied" | "voted on",
            "recipient_role": "prompt" | "copy",
            "phrase_text": "truncated phrase (max 50 chars)...",
            "timestamp": "2025-01-15T10:30:00Z"
        }

    Error handling:
        - Connection failures are logged but not sent to client
        - Notifications fail silently if connection drops
        - No reconnect logic - client handles reconnection if needed
    """
    auth_service = AuthService(db)

    try:
        # Authenticate using token
        player_id = await authenticate_websocket(websocket, token, auth_service)
        logger.info(f"WebSocket authenticated for {player_id=}")

        # Add connection to manager
        await connection_manager.connect(str(player_id), websocket)

        # Keep connection alive, listening for any client-sent messages
        # (Currently clients don't send messages, but we keep connection open)
        try:
            while True:
                # Wait for message from client (shouldn't happen, but keeps connection alive)
                data = await websocket.receive_text()
                # Ignore client messages - this is a server-push-only endpoint
                logger.debug(f"Ignored client message for {player_id=}: {data}")
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for {player_id=}")
        except Exception as e:
            logger.error(f"WebSocket error for {player_id=}: {e}")
        finally:
            await connection_manager.disconnect(str(player_id))

    except WebSocketException:
        # Already closed by authenticate_websocket
        pass
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
