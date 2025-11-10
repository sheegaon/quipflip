"""Middleware to track user activity for online users feature."""
import asyncio
from datetime import datetime, UTC
from typing import Optional
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
import logging

from backend.database import AsyncSessionLocal
from backend.models.user_activity import UserActivity
from backend.utils.simple_jwt import decode_jwt

logger = logging.getLogger(__name__)


# Action type mapping based on URL paths
ACTION_MAP = {
    "/rounds/prompt": "Prompt Round",
    "/rounds/copy": "Copy Round",
    "/rounds/vote": "Vote Round",
    "/player/leaderboard": "Leaderboard",
    "/player/statistics": "Statistics",
    "/rounds/results": "Round Review",
    "/player/dashboard": "Dashboard",
    "/rounds/completed": "Completed Rounds",
    "/quests": "Quests",
    "/phrasesets": "Phraseset Review",
    "/player/balance": "Balance Check",
    "/player/tutorial": "Tutorial",
}


def get_action_type(path: str) -> str:
    """Determine the action type based on the URL path."""
    # Check exact matches first
    for pattern, action in ACTION_MAP.items():
        if path.startswith(pattern):
            return action

    # Default fallback
    if path.startswith("/player"):
        return "Player Action"
    elif path.startswith("/rounds"):
        return "Round Action"
    elif path.startswith("/quests"):
        return "Quests"
    else:
        return "Other"


async def get_user_from_token(authorization: Optional[str]) -> Optional[tuple[str, str]]:
    """Extract player_id and username from JWT token."""
    if not authorization:
        return None

    try:
        from backend.config import get_settings
        settings = get_settings()

        # Remove "Bearer " prefix if present
        token = authorization.replace("Bearer ", "").strip()
        payload = decode_jwt(token, settings.secret_key, algorithms=[settings.jwt_algorithm])

        if not payload:
            return None

        player_id = payload.get("sub")  # player_id is stored in 'sub' field
        username = payload.get("username")

        if player_id and username:
            return (player_id, username)

    except Exception as e:
        logger.debug(f"Error extracting user from token: {e}")

    return None


async def update_user_activity_db(
    player_id: str,
    username: str,
    action: str,
    path: str
):
    """Update user activity in the database asynchronously."""
    try:
        async with AsyncSessionLocal() as db:
            # Use upsert to insert or update
            # Check if we're using SQLite or PostgreSQL
            from backend.config import get_settings
            settings = get_settings()

            if "sqlite" in settings.database_url.lower():
                # SQLite upsert
                stmt = sqlite_insert(UserActivity).values(
                    player_id=player_id,
                    username=username,
                    last_action=action,
                    last_action_path=path,
                    last_activity=datetime.now(UTC)
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['player_id'],
                    set_={
                        'username': username,
                        'last_action': action,
                        'last_action_path': path,
                        'last_activity': datetime.now(UTC)
                    }
                )
            else:
                # PostgreSQL upsert
                stmt = pg_insert(UserActivity).values(
                    player_id=player_id,
                    username=username,
                    last_action=action,
                    last_action_path=path,
                    last_activity=datetime.now(UTC)
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['player_id'],
                    set_={
                        'username': username,
                        'last_action': action,
                        'last_action_path': path,
                        'last_activity': datetime.now(UTC)
                    }
                )

            await db.execute(stmt)
            await db.commit()

    except Exception as e:
        logger.error(f"Error updating user activity: {e}")


async def activity_tracking_middleware(request: Request, call_next):
    """Track user activity for authenticated requests."""
    # Process the request first
    response = await call_next(request)

    # Skip tracking for certain paths
    skip_paths = [
        "/docs",
        "/openapi.json",
        "/favicon.ico",
        "/health",
        "/",
        "/auth/login",
        "/auth/register",
        "/auth/guest",
    ]

    if any(request.url.path.startswith(path) for path in skip_paths):
        return response

    # Only track successful requests
    if response.status_code >= 400:
        return response

    # Extract user info from authorization header
    authorization = request.headers.get("authorization")
    user_info = await get_user_from_token(authorization)

    if user_info:
        player_id, username = user_info
        action = get_action_type(request.url.path)

        # Update activity asynchronously without blocking the response
        asyncio.create_task(
            update_user_activity_db(player_id, username, action, request.url.path)
        )

    return response
