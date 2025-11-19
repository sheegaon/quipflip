"""Party Mode Pydantic schemas."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID

from backend.schemas.base import BaseSchema


# Request schemas
class CreatePartySessionRequest(BaseModel):
    """Request to create a new party session."""
    min_players: int = Field(default=3, ge=2, le=8, description="Minimum players to start")
    max_players: int = Field(default=8, ge=2, le=8, description="Maximum players allowed")
    prompts_per_player: int = Field(default=1, ge=1, le=3, description="Prompts per player")
    copies_per_player: int = Field(default=2, ge=1, le=4, description="Copies per player")
    votes_per_player: int = Field(default=3, ge=2, le=5, description="Votes per player")


class JoinPartySessionRequest(BaseModel):
    """Request to join an existing party session."""
    party_code: str = Field(..., min_length=8, max_length=8, description="8-character party code")


class SubmitPartyRoundRequest(BaseModel):
    """Request to submit a party round."""
    phrase: str = Field(..., min_length=2, max_length=100, description="Submitted phrase")


# Response schemas
class PartyParticipantResponse(BaseSchema):
    """Participant information in a party session."""
    participant_id: str
    player_id: str
    username: str
    is_host: bool
    status: str
    prompts_submitted: int
    copies_submitted: int
    votes_submitted: int
    prompts_required: int
    copies_required: int
    votes_required: int
    joined_at: Optional[datetime]
    ready_at: Optional[datetime]


class PartySessionProgressResponse(BaseSchema):
    """Progress information for a party session."""
    total_prompts: int
    total_copies: int
    total_votes: int
    required_prompts: int
    required_copies: int
    required_votes: int
    players_ready_for_next_phase: int
    total_players: int


class PartySessionResponse(BaseSchema):
    """Party session information."""
    session_id: str
    party_code: str
    host_player_id: str
    status: str
    current_phase: str
    min_players: int
    max_players: int
    phase_started_at: Optional[datetime]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    participants: List[PartyParticipantResponse]
    progress: PartySessionProgressResponse


class CreatePartySessionResponse(BaseSchema):
    """Response after creating a party session."""
    session_id: str
    party_code: str
    host_player_id: str
    status: str
    current_phase: str
    created_at: datetime
    participants: List[PartyParticipantResponse]
    min_players: int
    max_players: int


class JoinPartySessionResponse(BaseSchema):
    """Response after joining a party session."""
    session_id: str
    party_code: str
    status: str
    current_phase: str
    participants: List[PartyParticipantResponse]
    participant_count: int
    min_players: int
    max_players: int


class MarkReadyResponse(BaseSchema):
    """Response after marking ready."""
    participant_id: str
    status: str
    session: Dict
        # ready_count, total_count, can_start


class StartPartySessionResponse(BaseSchema):
    """Response after starting a party session."""
    session_id: str
    status: str
    current_phase: str
    phase_started_at: datetime
    locked_at: datetime
    participants: List[PartyParticipantResponse]


class PartySessionStatusResponse(BaseSchema):
    """Full party session status."""
    session_id: str
    party_code: str
    host_player_id: str
    status: str
    current_phase: str
    min_players: int
    max_players: int
    phase_started_at: Optional[datetime]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    participants: List[PartyParticipantResponse]
    progress: PartySessionProgressResponse


class StartPartyRoundResponse(BaseSchema):
    """Response after starting a party round."""
    round_id: str
    party_round_id: str
    round_type: str
    expires_at: datetime
    cost: int
    session_progress: Dict


class SubmitPartyRoundResponse(BaseSchema):
    """Response after submitting a party round."""
    success: bool
    phrase: str
    round_type: str
    session_progress: Dict
    phase_transition: Optional[Dict] = None


class PartyPlayerStatsResponse(BaseSchema):
    """Individual player statistics in a party match."""
    player_id: str
    username: str
    rank: int
    spent: int
    earned: int
    net: int
    votes_on_originals: int
    votes_fooled: int
    correct_votes: int
    total_votes: int
    vote_accuracy: float
    prompts_submitted: int
    copies_submitted: int
    votes_submitted: int


class PartyAwardResponse(BaseSchema):
    """Award winner information."""
    player_id: str
    username: str
    metric_value: float


class PartyPhrasesetSummaryResponse(BaseSchema):
    """Summary of a phraseset in the party match."""
    phraseset_id: str
    prompt_text: str
    original_phrase: str
    vote_count: int
    original_player: str
    most_votes: str
    votes_breakdown: Dict[str, int]


class PartyResultsResponse(BaseSchema):
    """Complete party match results."""
    session_id: str
    party_code: str
    completed_at: Optional[datetime]
    rankings: List[PartyPlayerStatsResponse]
    awards: Dict[str, PartyAwardResponse]
    phrasesets_summary: List[PartyPhrasesetSummaryResponse]


class PartyListItemResponse(BaseSchema):
    """Information about a joinable party session."""
    session_id: str
    host_username: str
    participant_count: int
    min_players: int
    max_players: int
    created_at: datetime
    is_full: bool


class PartyListResponse(BaseSchema):
    """List of active/joinable party sessions."""
    parties: List[PartyListItemResponse]
    total_count: int
