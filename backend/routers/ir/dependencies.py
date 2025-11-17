"""Shared dependencies for IR routers."""
from fastapi import Depends, HTTPException, Header, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.ir.ir_player import IRPlayer
from backend.services.ir.auth_service import IRAuthService, IRAuthError
from backend.services.ir.player_service import IRPlayerService


async def get_ir_current_player(
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

    auth_service = IRAuthService(db)
    try:
        player_id = await auth_service.verify_access_token(token)
    except IRAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    player_service = IRPlayerService(db)
    player = await player_service.get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=401, detail="Player not found")

    return player
