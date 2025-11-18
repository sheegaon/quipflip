"""Survey response model for beta surveys."""
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.models.survey_response_base import SurveyResponseBase
from backend.models.base import get_uuid_column


class IRSurveyResponse(SurveyResponseBase):
    """Persisted survey response payloads for in-app surveys."""

    __tablename__ = "ir_survey_responses"

    # Override player_id to add IR-specific foreign key constraint
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"), index=True, nullable=False
    )

    player = relationship("IRPlayer", backref="survey_responses")

    __table_args__ = (
        Index("ix_survey_responses_player_survey", "player_id", "survey_id", unique=True),
    )