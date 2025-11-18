"""Online user tracking middleware for "Who's Online" feature.

This middleware tracks user activity by recording the last API call made by each
authenticated user. It updates the user_activity table which powers the real-time
online users page accessible from the subheader.

This is distinct from phraseset_activity tracking, which logs historical phraseset
review events and lifecycle information.
"""
import logging
from datetime import datetime, UTC
from uuid import UUID
from fastapi import Request
from sqlalchemy import select
from jwt import InvalidTokenError, ExpiredSignatureError, DecodeError

from backend.database import AsyncSessionLocal
from backend.services import AuthService
from backend.services.auth_service import GameType
from backend.config import get_settings
from backend.utils.model_registry import get_user_activity_model

logger = logging.getLogger(__name__)

# Action type mapping based on URL paths with categories for consistent frontend styling
ACTION_MAP = {
    # Player paths (from most specific to least specific)
    "/player/statistics/weekly-leaderboard": {"name": "Weekly Leaderboard", "category": "stats"},
    "/player/statistics/alltime-leaderboard": {"name": "All-Time Leaderboard", "category": "stats"},
    "/player/statistics": {"name": "Statistics", "category": "stats"},
    "/player/leaderboard": {"name": "Leaderboard", "category": "stats"},
    "/player/dashboard": {"name": "Dashboard", "category": "navigation"},
    "/player/current-round": {"name": "Current Round", "category": "round_navigation"},
    "/player/pending-results": {"name": "Pending Results", "category": "review"},
    "/player/balance": {"name": "Wallet", "category": "economy"},
    "/player/claim-daily-bonus": {"name": "Daily Bonus", "category": "economy"},
    "/player/tutorial": {"name": "Tutorial", "category": "tutorial"},
    "/player/password": {"name": "Updating Password", "category": "account"},
    "/player/email": {"name": "Updating Email", "category": "account"},
    "/player/username": {"name": "Updating Username", "category": "account"},
    "/player/account": {"name": "Account Settings", "category": "account"},

    # Round paths
    "/rounds/prompt": {"name": "Prompt Round", "category": "round_prompt"},
    "/rounds/copy": {"name": "Copy Round", "category": "round_copy"},
    "/rounds/vote": {"name": "Vote Round", "category": "round_vote"},
    "/rounds/available": {"name": "Browsing Rounds", "category": "round_navigation"},
    "/rounds/results": {"name": "Round Review", "category": "review"},
    "/rounds/completed": {"name": "Completed Rounds", "category": "review"},
    "/rounds/": {"name": "Round Activity", "category": "round_other"},  # Generic rounds path

    # Quest paths
    "/quests/active": {"name": "Active Quests", "category": "quests"},
    "/quests/claimable": {"name": "Claiming Quest Rewards", "category": "quest_rewards"},
    "/quests": {"name": "Quests", "category": "quests"},

    # Phraseset paths
    "/phrasesets/practice": {"name": "Practice Mode", "category": "practice"},
    "/phrasesets": {"name": "Phraseset Review", "category": "review"},
    "/phrasesets/": {"name": "Phraseset Review", "category": "review"},  # Generic phrasesets path

    # Other paths
    "/feedback/beta-survey": {"name": "Beta Survey", "category": "feedback"},
    "/notifications": {"name": "Notifications", "category": "notifications"},
    "/online-users": {"name": "Online Users", "category": "navigation"},
}


def get_friendly_action_info(method: str, path: str) -> dict:
    """Convert HTTP method and path to a user-friendly action name and category."""
    # Check for exact path matches first
    if path in ACTION_MAP:
        return ACTION_MAP[path]
    
    # Check for path prefixes
    for pattern, action_info in ACTION_MAP.items():
        if path.startswith(pattern):
            return action_info
    
    # Default fallback based on path patterns
    if path.startswith("/player"):
        return {"name": "Player Action", "category": "navigation"}
    elif path.startswith("/rounds"):
        return {"name": "Round Action", "category": "round_other"}
    elif path.startswith("/quests"):
        return {"name": "Quests", "category": "quests"}
    elif path.startswith("/auth"):
        return {"name": "Authentication", "category": "auth"}
    else:
        return {"name": "Other Action", "category": "other"}


async def update_user_activity_task(
    player_id: UUID,
    username: str,
    action_name: str,
    action_category: str,
    action_path: str,
    game_type: GameType
):
    """Background task to update user activity without blocking response."""
    try:
        async with AsyncSessionLocal() as db:
            # Get the concrete user activity model for this game type
            user_activity_model = get_user_activity_model(game_type)

            # Update or create activity record
            result = await db.execute(
                select(user_activity_model).where(user_activity_model.player_id == player_id)
            )
            activity = result.scalar_one_or_none()

            current_time = datetime.now(UTC)

            if activity:
                # Update existing activity
                activity.username = username
                activity.last_action = action_name
                activity.last_action_category = action_category
                activity.last_action_path = action_path
                activity.last_activity = current_time
            else:
                # Create new activity record
                activity = user_activity_model(
                    player_id=player_id,
                    username=username,
                    last_action=action_name,
                    last_action_category=action_category,
                    last_action_path=action_path,
                    last_activity=current_time
                )
                db.add(activity)

            await db.commit()

    except Exception as e:
        logger.error(f"Error updating user activity in background task: {e}")


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
        settings = get_settings()
        token = request.cookies.get(settings.access_token_cookie_name)
        
        if token:
            try:
                # Create a temporary auth service instance for token decoding only
                # Try QF first, then IR if that fails
                async with AsyncSessionLocal() as temp_db:
                    payload = None
                    detected_game_type = None

                    # Try QF game type first
                    try:
                        qf_auth_service = AuthService(temp_db, game_type=GameType.QF)
                        payload = qf_auth_service.decode_access_token(token)
                        detected_game_type = GameType.QF
                    except Exception:
                        # If QF fails, try IR game type
                        try:
                            ir_auth_service = AuthService(temp_db, game_type=GameType.IR)
                            payload = ir_auth_service.decode_access_token(token)
                            detected_game_type = GameType.IR
                        except Exception:
                            # If both fail, let it raise to the outer exception handler
                            raise

                    # Decode token to get player info
                    player_id_str = payload.get("sub")
                    username = payload.get("username")

                    if player_id_str and username and detected_game_type:
                        player_id = UUID(player_id_str)
                        action_path = str(request.url.path)

                        # Use friendly action info instead of raw HTTP method + path
                        friendly_action_info = get_friendly_action_info(request.method, action_path)

                        # Update activity in background task - fire and forget approach
                        import asyncio
                        asyncio.create_task(update_user_activity_task(
                            player_id,
                            username,
                            friendly_action_info["name"],
                            friendly_action_info["category"],
                            action_path,
                            detected_game_type
                        ))
                        
            except (InvalidTokenError, ExpiredSignatureError, DecodeError):
                # Token is invalid or expired - this is expected and shouldn't be logged
                pass
            except Exception as e:
                logger.error(f"Unexpected error in activity tracking middleware: {e}")
    
    return response
