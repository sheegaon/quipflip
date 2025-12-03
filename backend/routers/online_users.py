"""Online users API router with WebSocket support for "Who's Online" feature.

Provides REST and WebSocket endpoints to query and stream real-time updates about
which users are currently active based on their recent API calls (last 30 minutes).

This is distinct from phraseset_activity tracking, which logs historical phraseset
review events.
"""
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional, Tuple
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import logging
from uuid import UUID

from backend.database import get_db, AsyncSessionLocal
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.schemas.online_users import (
    OnlineUser,
    OnlineUsersResponse,
    PingUserRequest,
    PingUserResponse,
)
from backend.schemas.notification import PingWebSocketMessage
from backend.services import AuthService
from backend.utils.model_registry import (
    GameType,
    get_player_data_model,
    get_transaction_model,
    get_user_activity_model,
)
from backend.services.qf import NotificationConnectionManager, get_notification_manager
from backend.services.qf.player_service import QFPlayerService
from backend.services.ir.player_service import IRPlayerService
from backend.services.mm.player_service import MMPlayerService
from backend.config import get_settings
from backend.utils.datetime_helpers import ensure_utc

logger = logging.getLogger(__name__)

router = APIRouter()

settings = get_settings()


async def detect_player_and_game(
    request: Request,
    authorization: str | None,
    db: AsyncSession,
) -> Tuple[Player, GameType]:
    """Detect the authenticated player and their game type from the request."""
    for game_type in GameType:
        try:
            player = await get_current_player(
                request=request,
                game_type=game_type,
                authorization=authorization,
                db=db,
            )
            return player, game_type
        except HTTPException:
            continue

    raise HTTPException(status_code=401, detail="invalid_token")


def get_player_service(game_type: GameType, db: AsyncSession):
    """Return the appropriate player service for a game type."""
    if game_type == GameType.QF:
        return QFPlayerService(db)
    if game_type == GameType.IR:
        return IRPlayerService(db)
    if game_type == GameType.MM:
        return MMPlayerService(db)
    raise ValueError(f"Unsupported game type: {game_type}")


async def authenticate_websocket(websocket: WebSocket) -> Optional[Tuple[Player, GameType]]:
    """Authenticate a WebSocket connection using token from query params or cookies.

    Returns the authenticated Player and associated GameType or None if authentication fails.
    """
    token = websocket.query_params.get("token")

    if not token:
        token = websocket.cookies.get(settings.access_token_cookie_name)

    if not token:
        logger.warning("WebSocket connection attempted without token")
        return None

    try:
        async with AsyncSessionLocal() as db:
            for game_type in (GameType.QF, GameType.IR, GameType.MM):
                try:
                    auth_service = AuthService(db, game_type=game_type)
                    payload = auth_service.decode_access_token(token)
                except Exception:
                    continue

                player_id_str = payload.get("sub") if payload else None
                if not player_id_str:
                    continue

                player_id = UUID(player_id_str)
                player_service = get_player_service(game_type, db)
                player = await player_service.get_player_by_id(player_id)

                if not player:
                    continue

                return player, game_type

            logger.warning("WebSocket token did not match any supported game type")
            return None

    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        return None


class ConnectionManager:
    """Manages WebSocket connections for online users updates by game."""

    def __init__(self):
        self.active_connections: Dict[GameType, List[WebSocket]] = {
            game_type: [] for game_type in GameType
        }
        self._background_task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self, websocket: WebSocket, game_type: GameType):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[game_type].append(websocket)
        logger.info(
            "New WebSocket connection. Game=%s Total=%s",
            game_type.value,
            len(self.active_connections[game_type]),
        )

        if not self._running:
            self._start_background_task()

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        for game_type, connections in self.active_connections.items():
            if websocket in connections:
                connections.remove(websocket)
                logger.info(
                    "WebSocket disconnected. Game=%s Total=%s",
                    game_type.value,
                    len(connections),
                )
                break

        if self._running and not any(self.active_connections.values()):
            self._stop_background_task()

    async def broadcast(self, game_type: GameType, message: dict):
        """Broadcast a message to all connected clients for a game."""
        connections = self.active_connections.get(game_type, [])
        if not connections:
            return

        disconnected = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    def _start_background_task(self):
        if self._running:
            return

        self._running = True
        self._background_task = asyncio.create_task(self._broadcast_loop())
        logger.info("Started online users broadcast task")

    def _stop_background_task(self):
        if not self._running:
            return

        self._running = False
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
        logger.info("Stopped online users broadcast task")

    async def _broadcast_loop(self):
        try:
            while self._running:
                async with AsyncSessionLocal() as db:
                    for game_type, connections in self.active_connections.items():
                        if not connections:
                            continue

                        try:
                            online_users = await get_online_users(db, game_type)

                            message = {
                                "type": "online_users_update",
                                "users": [
                                    user.model_dump(mode="json") for user in online_users
                                ],
                                "total_count": len(online_users),
                                "timestamp": datetime.now(UTC).isoformat(),
                            }

                            await self.broadcast(game_type, message)
                        except Exception as e:
                            logger.error(
                                "Error in online users broadcast loop for %s: %s",
                                game_type.value,
                                e,
                            )

                await asyncio.sleep(5)

        except asyncio.CancelledError:
            logger.info("Online users broadcast task cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in online users broadcast task: {e}")
        finally:
            self._running = False


# Global connection manager
manager = ConnectionManager()


async def get_online_users(db: AsyncSession, game_type: GameType) -> List[OnlineUser]:
    """Get list of users who were active in the last 30 minutes.

    Excludes guest users who have taken no actions (no submitted rounds,
    no phraseset activities, no transactions, and haven't navigated beyond dashboard).
    """
    cutoff_time = datetime.now(UTC) - timedelta(minutes=30)

    try:
        UserActivityModel = get_user_activity_model(game_type)
        PlayerDataModel = get_player_data_model(game_type)
        TransactionModel = get_transaction_model(game_type)
    except ValueError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc

    result = await db.execute(
        select(
            UserActivityModel,
            PlayerDataModel.wallet,
            Player.created_at,
            Player.is_guest,
            Player.player_id,
        )
        .join(Player, UserActivityModel.player_id == Player.player_id)
        .outerjoin(PlayerDataModel, PlayerDataModel.player_id == Player.player_id)
        .where(UserActivityModel.last_activity >= cutoff_time)
        .order_by(UserActivityModel.last_activity.desc())
    )
    rows = result.all()

    # Capture current time once for consistent calculations
    now = datetime.now(UTC)

    # Collect guest player IDs to check for activity
    guest_ids = [player_id for _, _, _, is_guest, player_id in rows if is_guest]

    # If there are guests, check which ones have activity
    guests_with_activity = set()
    if guest_ids:
        transactions_result = await db.execute(
            select(TransactionModel.player_id)
            .where(TransactionModel.player_id.in_(guest_ids))
            .distinct()
        )
        guests_with_activity.update(row[0] for row in transactions_result)

    online_users = []
    for activity, wallet, created_at, is_guest, player_id in rows:
        if is_guest and player_id not in guests_with_activity:
            continue

        # Calculate time ago
        # Ensure last_activity is timezone-aware (handle naive datetimes from DB)
        last_activity = ensure_utc(activity.last_activity)
        time_diff = now - last_activity
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
                last_action_category=activity.last_action_category,
                last_activity=activity.last_activity,
                time_ago=time_ago,
                wallet=wallet or 0,
                created_at=created_at,
            )
        )

    return online_users


@router.get("/online", response_model=OnlineUsersResponse)
async def get_online_users_endpoint(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
):
    """Get list of currently online users (last 30 minutes)."""
    _, game_type = await detect_player_and_game(request, authorization, db)

    online_users = await get_online_users(db, game_type)

    return OnlineUsersResponse(
        users=online_users,
        total_count=len(online_users),
    )


@router.post("/online/ping", response_model=PingUserResponse)
async def ping_online_user(
    ping_request: PingUserRequest,
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
    connection_manager: NotificationConnectionManager = Depends(
        get_notification_manager
    ),
):
    """Send a ping notification to another online user."""

    player, game_type = await detect_player_and_game(request, authorization, db)

    if ping_request.username == player.username:
        raise HTTPException(status_code=400, detail="Cannot ping yourself")

    player_service = get_player_service(game_type, db)
    target_player = await player_service.get_player_by_username(ping_request.username)

    if not target_player:
        raise HTTPException(status_code=404, detail="User not found")

    ping_message = PingWebSocketMessage(
        from_username=player.username,
        timestamp=datetime.now(UTC).isoformat(),
    )

    await connection_manager.send_to_player(
        target_player.player_id, ping_message.model_dump()
    )

    return PingUserResponse(success=True, message="Ping sent")


@router.websocket("/online/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time online users updates.

    Requires authentication via token in query params (?token=...) or cookies.
    """
    # Authenticate before accepting connection
    auth_result = await authenticate_websocket(websocket)

    if not auth_result:
        # Reject unauthenticated connection
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        logger.info("WebSocket connection rejected: authentication failed")
        return

    player, game_type = auth_result

    # Accept authenticated connection
    await manager.connect(websocket, game_type)
    logger.info("WebSocket authenticated for player: %s (game=%s)", player.username, game_type.value)

    try:
        # Keep connection alive and listen for client disconnects
        # The actual data broadcasting is handled by the background task
        while True:
            # Just wait for client messages or disconnects
            # We don't expect any messages from clients, but this keeps the connection alive
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for player {player.username}: {e}")
    finally:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected for player: %s (game=%s)", player.username, game_type.value)
