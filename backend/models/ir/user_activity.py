"""User activity model for "Who's Online" feature.

This is distinct from other activity tracking models, which log historical 
events and lifecycle information.
"""
from sqlalchemy import Index
from backend.models.user_activity_base import UserActivityBase


class IRUserActivity(UserActivityBase):
    """Tracks the last API call made by each user for online status.

    Used by the "Who's Online" page to show which users are currently active.
    Each row represents a single user's most recent activity.
    """

    __tablename__ = "ir_user_activity"

    __table_args__ = (
        Index('ix_user_activity_last_activity', 'last_activity', postgresql_using='brin'),
    )