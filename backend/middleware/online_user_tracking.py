"""Online user tracking middleware for "Who's Online" feature.

This middleware tracks user activity by recording the last API call made by each
authenticated user. It updates the user_activity table which powers the real-time
online users page accessible from the subheader.

This is distinct from phraseset_activity tracking, which logs historical phraseset
review events and lifecycle information.
"""
import logging
from datetime import datetime, UTC
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import AsyncSessionLocal
from backend.models.user_activity import UserActivity
from backend.services.auth_service import AuthService

logger = logging.getLogger(__name__)


# Action type mapping based on URL paths - must match frontend getActionColor() mapping
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
    # Add missing mappings that frontend expects
    "/rounds/": "Round Review",  # Generic rounds path
    "/phrasesets/": "Phraseset Review",  # Generic phrasesets path
}


def get_friendly_action_name(method: str, path: str) -> str:
    """Convert HTTP method and path to a user-friendly action name."""
    # Check for exact path matches first
    if path in ACTION_MAP:
        return ACTION_MAP[path]
    
    # Check for path prefixes
    for pattern, action in ACTION_MAP.items():
        if path.startswith(pattern):
            return action
    
    # Default fallback based on path patterns
    if path.startswith("/player"):
        return "Player Action"
    elif path.startswith("/rounds"):
        return "Round Action"
    elif path.startswith("/quests"):
        return "Quests"
    elif path.startswith("/auth"):
        return "Authentication"
    else:
        return "Other Action"


async def online_user_tracking_middleware(request: Request, call_next):
    """
    Middleware to track user activity for online users feature.
    
    This middleware runs after request processing and tracks the last activity
    of authenticated users to determine who is currently online.
    """
    response = await call_next(request)
    
    # Only track activity for successful requests to avoid noise
    if response.status_code < 400:
        # Extract token from cookies
        from backend.config import get_settings
        settings = get_settings()
        token = request.cookies.get(settings.access_token_cookie_name)
        
        if token:
            try:
                async with AsyncSessionLocal() as db:
                    auth_service = AuthService(db)
                    
                    # Decode token to get player info
                    try:
                        payload = auth_service.decode_access_token(token)
                        player_id_str = payload.get("sub")
                        
                        if player_id_str:
                            from uuid import UUID
                            player_id = UUID(player_id_str)
                            
                            # Get player to get username
                            from backend.services.player_service import PlayerService
                            player_service = PlayerService(db)
                            player = await player_service.get_player_by_id(player_id)
                            
                            if player:
                                # Update or create activity record
                                result = await db.execute(
                                    select(UserActivity).where(UserActivity.player_id == player_id)
                                )
                                activity = result.scalar_one_or_none()
                                
                                current_time = datetime.now(UTC)
                                action_path = str(request.url.path)
                                
                                # Use friendly action name instead of raw HTTP method + path
                                friendly_action = get_friendly_action_name(request.method, action_path)
                                
                                if activity:
                                    # Update existing activity
                                    activity.username = player.username
                                    activity.last_action = friendly_action
                                    activity.last_action_path = action_path
                                    activity.last_activity = current_time
                                else:
                                    # Create new activity record
                                    activity = UserActivity(
                                        player_id=player_id,
                                        username=player.username,
                                        last_action=friendly_action,
                                        last_action_path=action_path,
                                        last_activity=current_time
                                    )
                                    db.add(activity)
                                
                                await db.commit()
                                
                    except Exception as e:
                        # Don't log token decode failures as they're common (expired tokens, etc.)
                        pass
                        
            except Exception as e:
                logger.error(f"Error in activity tracking middleware: {e}")
    
    return response
