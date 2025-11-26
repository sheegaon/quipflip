"""Shared dependencies for IR routers."""
from fastapi import Depends, HTTPException, Header, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.ir.player import IRPlayer
from backend.services import AuthService, AuthError
from backend.utils.model_registry import GameType
from backend.services.ir import IRPlayerService


async def get_current_player(
    authorization: str | None = Header(None, alias="Authorization"),
    ir_access_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> IRPlayer:
    """Get current authenticated IR player from token.

    Supports both Authorization header and cookie.
    """
    token = None

    # Try Authorization header first
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    # Fall back to cookie
    if not token and ir_access_token:
        token = ir_access_token

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    auth_service = AuthService(db, game_type=GameType.IR)
    try:
        payload = auth_service.decode_access_token(token)
        player_id = payload.get("sub")
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    # Use IR player service since this is IR dependencies
    player_service = IRPlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=401, detail="Player not found")

    return player
