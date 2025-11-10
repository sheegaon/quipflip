"""Middleware to track user activity for online users feature."""
import asyncio
from datetime import datetime, UTC
from typing import Optional
from fastapi import Request
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
import logging
from uuid import UUID

from backend.database import AsyncSessionLocal
from backend.models.user_activity import UserActivity
from backend.utils.simple_jwt import decode_jwt
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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


async def get_user_from_request(request: Request) -> Optional[tuple[str, str]]:
    """Extract player_id and username from JWT token in cookies or Authorization header.

    Checks in the same order as get_current_player:
    1. HTTP-only cookie (preferred method for web clients)
    2. Authorization header (backward compatibility, API clients)
    """
    # Try to get token from cookie first (preferred method)
    token = request.cookies.get(settings.access_token_cookie_name)

    # Fall back to Authorization header if no cookie
    if not token:
        authorization = request.headers.get("authorization")
        if authorization:
            # Remove "Bearer " prefix if present
            token = authorization.replace("Bearer ", "").strip()

    if not token:
        return None

    try:
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


def _normalize_player_id(player_id: str | UUID) -> UUID | None:
    """Ensure player_id is a UUID instance for ORM compatibility."""
    if player_id is None:
        return None
    if isinstance(player_id, UUID):
        return player_id
    try:
        return UUID(str(player_id))
    except (ValueError, TypeError):
        logger.warning("Unable to normalize player_id '%s' to UUID", player_id)
        return None


async def update_user_activity_db(
    player_id: str | UUID,
    username: str,
    action: str,
    path: str
):
    """Update user activity in the database asynchronously."""
    try:
        normalized_player_id = _normalize_player_id(player_id)
        if normalized_player_id is None:
            logger.debug("Skipping user activity update due to invalid player_id: %s", player_id)
            return

        # Capture timestamp once for consistency
        now = datetime.now(UTC)

        # Create shared data dictionary
        activity_data = {
            'player_id': normalized_player_id,
            'username': username,
            'last_action': action,
            'last_action_path': path,
            'last_activity': now
        }

        # Update data for on_conflict (excluding player_id since it's the key)
        update_data = {
            'username': username,
            'last_action': action,
            'last_action_path': path,
            'last_activity': now
        }

        async with AsyncSessionLocal() as db:
            # Use database-appropriate upsert
            if "sqlite" in settings.database_url.lower():
                stmt = sqlite_insert(UserActivity).values(**activity_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['player_id'],
                    set_=update_data
                )
            else:
                stmt = pg_insert(UserActivity).values(**activity_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['player_id'],
                    set_=update_data
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
    skip_path_prefixes = [
        "/docs",
        "/openapi.json",
        "/favicon.ico",
        "/health",
        "/auth/login",
        "/auth/register",
        "/auth/guest",
        "/auth/refresh",
        "/auth/logout",
        "/auth/suggest-username",
    ]

    # Skip root path (exact match only) or paths that start with skip prefixes
    if request.url.path == "/" or any(request.url.path.startswith(path) for path in skip_path_prefixes):
        return response

    # Only track successful requests
    if response.status_code >= 400:
        return response

    # Wrap tracking in try-except to prevent any issues from breaking the request
    try:
        # Extract user info from cookies or authorization header
        user_info = await get_user_from_request(request)

        if user_info:
            player_id, username = user_info
            action = get_action_type(request.url.path)

            # Update activity asynchronously without blocking the response
            # Use create_task with exception handling to ensure errors don't propagate
            task = asyncio.create_task(
                update_user_activity_db(player_id, username, action, request.url.path)
            )
            # Prevent task exceptions from propagating
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    except Exception as e:
        # Log but don't fail the request if activity tracking has issues
        logger.error(f"Activity tracking middleware error: {e}")

    return response
