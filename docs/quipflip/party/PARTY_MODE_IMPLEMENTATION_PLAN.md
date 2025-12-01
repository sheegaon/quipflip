# Party Mode Implementation Plan

## Executive Summary

This document provides a complete technical implementation plan for **Quipflip Party Mode**, a coordinated multiplayer session feature that allows 3-8 players to play together in a structured match format. Party Mode reuses the existing prompt/copy/vote infrastructure while adding session coordination, real-time synchronization, and match-specific scoring.

**Key Design Principles:**
- Reuse existing Round, Phraseset, and Vote infrastructure
- Add minimal new tables for session coordination
- Use WebSocket for real-time player synchronization
- All coins earned/lost are real and affect global accounts
- Session-local scoring determines "who won this party"

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Data Models](#2-data-models)
3. [Backend Services](#3-backend-services)
4. [API Endpoints](#4-api-endpoints)
5. [WebSocket Communication](#5-websocket-communication)
6. [Phase-by-Phase Game Flow](#6-phase-by-phase-game-flow)
7. [Economy Integration](#7-economy-integration)
8. [Frontend Implementation](#8-frontend-implementation)
9. [Testing Strategy](#9-testing-strategy)
10. [Migration & Deployment](#10-migration--deployment)
11. [Future Enhancements](#11-future-enhancements)

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

Party Mode sits as a **coordinated layer** on top of the existing game infrastructure:

```
┌─────────────────────────────────────────────────────────┐
│                    Party Mode Layer                      │
│  - Session Management (PartySession table)               │
│  - Phase Coordination (WebSocket sync)                   │
│  - Match Scoring (session-local aggregation)             │
└─────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────┐
│              Existing Game Infrastructure                │
│  - Round Service (prompt/copy/vote)                      │
│  - Phraseset Service (phrase aggregation)                │
│  - Vote Service (voting logic)                           │
│  - Transaction Service (wallet management)               │
│  - Scoring Service (prize distribution)                  │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Key Capabilities

**Session Coordination:**
- Party code generation and joining
- Player roster management
- Phase progression tracking
- Status synchronization via WebSocket

**Constraint Enforcement:**
- All players write 1 original each (Phase 1)
- All players write 2 copies each (Phase 2)
- All players vote 3-4 times each (Phase 3)
- Players cannot vote on phrasesets they contributed to

**Match Scoring:**
- Aggregate player performance within the session timeframe
- Award categories: Best Writer, Top Impostor, Sharpest Voter
- Net coin earnings as tiebreaker/ranking metric

---

## 2. Data Models

### 2.1 New Tables

#### PartySession

Tracks the state of a party match.

```sql
CREATE TABLE party_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_code VARCHAR(8) UNIQUE NOT NULL,  -- 8-char alphanumeric code
    host_player_id UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,

    -- Configuration
    min_players INTEGER NOT NULL DEFAULT 3,
    max_players INTEGER NOT NULL DEFAULT 8,
    prompts_per_player INTEGER NOT NULL DEFAULT 1,
    copies_per_player INTEGER NOT NULL DEFAULT 2,
    votes_per_player INTEGER NOT NULL DEFAULT 3,

    -- Phase tracking
    current_phase VARCHAR(20) NOT NULL DEFAULT 'LOBBY',
        -- 'LOBBY', 'PROMPT', 'COPY', 'VOTE', 'RESULTS', 'COMPLETED'
    phase_started_at TIMESTAMP WITH TIME ZONE,
    phase_expires_at TIMESTAMP WITH TIME ZONE,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
        -- 'OPEN', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED'
    locked_at TIMESTAMP WITH TIME ZONE,  -- When room locked to new joiners

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Indexes
    INDEX idx_party_sessions_code (party_code),
    INDEX idx_party_sessions_status (status, created_at),
    INDEX idx_party_sessions_host (host_player_id)
);
```

#### PartyParticipant

Tracks individual player participation in a party session.

```sql
CREATE TABLE party_participants (
    participant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES party_sessions(session_id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'JOINED',
        -- 'JOINED', 'READY', 'ACTIVE', 'COMPLETED', 'DISCONNECTED'
    is_host BOOLEAN NOT NULL DEFAULT FALSE,

    -- Progress tracking
    prompts_submitted INTEGER NOT NULL DEFAULT 0,
    copies_submitted INTEGER NOT NULL DEFAULT 0,
    votes_submitted INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ready_at TIMESTAMP WITH TIME ZONE,
    last_activity_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    UNIQUE (session_id, player_id),
    INDEX idx_party_participants_session (session_id),
    INDEX idx_party_participants_player (player_id),
    INDEX idx_party_participants_status (session_id, status)
);
```

#### PartyRound

Links existing rounds to party sessions.

```sql
CREATE TABLE party_rounds (
    party_round_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES party_sessions(session_id) ON DELETE CASCADE,
    round_id UUID NOT NULL REFERENCES rounds(round_id) ON DELETE CASCADE,
    participant_id UUID NOT NULL REFERENCES party_participants(participant_id) ON DELETE CASCADE,

    -- Round classification
    round_type VARCHAR(10) NOT NULL,  -- 'prompt', 'copy', 'vote'
    phase VARCHAR(20) NOT NULL,  -- Which party phase this round belongs to

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE (session_id, round_id),
    INDEX idx_party_rounds_session (session_id, phase),
    INDEX idx_party_rounds_participant (participant_id),
    INDEX idx_party_rounds_round (round_id)
);
```

#### PartyPhraseset

Links phrasesets to party sessions for match-scoped voting.

```sql
CREATE TABLE party_phrasesets (
    party_phraseset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES party_sessions(session_id) ON DELETE CASCADE,
    phraseset_id UUID NOT NULL REFERENCES phrasesets(phraseset_id) ON DELETE CASCADE,

    -- Metadata
    created_in_phase VARCHAR(20) NOT NULL,  -- 'COPY'
    available_for_voting BOOLEAN NOT NULL DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE (session_id, phraseset_id),
    INDEX idx_party_phrasesets_session (session_id, available_for_voting),
    INDEX idx_party_phrasesets_phraseset (phraseset_id)
);
```

### 2.2 Schema Design Decisions

**Why separate PartyRound/PartyPhraseset tables?**
- Keeps the core `rounds` and `phrasesets` tables clean
- Allows filtering party-specific content easily
- Enables session-scoped queries without JOIN complexity
- Party sessions can be deleted independently

**Why track progress in PartyParticipant?**
- Single source of truth for "has this player finished their tasks?"
- Enables efficient progress queries for UI updates
- Simplifies phase transition logic

**Why store `phase` in PartyRound?**
- Allows identifying which rounds belong to which party phase
- Enables session recap ("here's what happened in Phase 2")
- Useful for analytics and debugging

---

## 3. Backend Services

### 3.1 PartySessionService

**Location:** `backend/services/qf/party_session_service.py`

**Responsibilities:**
- Session lifecycle management (create, start, complete)
- Party code generation and validation
- Player join/leave logic
- Phase transitions
- Session status queries

**Key Methods:**

```python
class PartySessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        host_player_id: UUID,
        min_players: int = 3,
        max_players: int = 8
    ) -> PartySession:
        """Create a new party session with unique party code."""
        pass

    async def get_session_by_code(self, party_code: str) -> Optional[PartySession]:
        """Retrieve session by party code."""
        pass

    async def add_participant(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> PartyParticipant:
        """Add a player to the session (pre-start only)."""
        pass

    async def remove_participant(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> None:
        """Remove a player from lobby (pre-start only)."""
        pass

    async def start_session(self, session_id: UUID) -> PartySession:
        """Lock session, transition to PROMPT phase."""
        pass

    async def advance_phase(self, session_id: UUID) -> PartySession:
        """Move to next phase when all players complete current phase."""
        pass

    async def get_session_status(self, session_id: UUID) -> dict:
        """Get full session state including participants, progress, phase."""
        pass

    async def can_advance_phase(self, session_id: UUID) -> bool:
        """Check if all participants have completed current phase."""
        pass

    async def mark_participant_ready(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> PartyParticipant:
        """Mark participant as ready in lobby."""
        pass

    async def record_round_completion(
        self,
        session_id: UUID,
        player_id: UUID,
        round_id: UUID,
        round_type: str,
        phase: str
    ) -> None:
        """Link round to party session and update participant progress."""
        pass

    async def get_available_phrasesets_for_voting(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> List[UUID]:
        """Get phrasesets in this session that player can vote on."""
        pass

    async def calculate_match_results(self, session_id: UUID) -> dict:
        """Aggregate session performance and calculate awards."""
        pass
```

### 3.2 PartyCoordinationService

**Location:** `backend/services/qf/party_coordination_service.py`

**Responsibilities:**
- Enforce phase-specific rules
- Validate player actions within party context
- Coordinate with existing round services
- Trigger phase transitions

**Key Methods:**

```python
class PartyCoordinationService:
    def __init__(
        self,
        db: AsyncSession,
        session_service: PartySessionService,
        round_service: RoundService,
        vote_service: VoteService
    ):
        self.db = db
        self.session_service = session_service
        self.round_service = round_service
        self.vote_service = vote_service

    async def start_party_prompt_round(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> Round:
        """Start prompt round within party context."""
        # 1. Validate session is in PROMPT phase
        # 2. Validate player hasn't already submitted prompt
        # 3. Call RoundService.start_prompt_round
        # 4. Link round to party via PartyRound
        # 5. Check if all players done -> trigger phase transition
        pass

    async def start_party_copy_round(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> Round:
        """Start copy round within party context."""
        # 1. Validate session is in COPY phase
        # 2. Validate player has copies remaining
        # 3. Assign prompt from party phrasesets (prioritize party prompts)
        # 4. Call RoundService.start_copy_round with specific prompt
        # 5. Link round to party via PartyRound
        # 6. Check if all players done -> trigger phase transition
        pass

    async def start_party_vote_round(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> Round:
        """Start vote round within party context."""
        # 1. Validate session is in VOTE phase
        # 2. Validate player has votes remaining
        # 3. Get available phrasesets (party-scoped, excluding self-content)
        # 4. Call RoundService.start_vote_round with specific phraseset
        # 5. Link round to party via PartyRound
        # 6. Check if all players done -> trigger phase transition
        pass

    async def submit_party_round(
        self,
        session_id: UUID,
        player_id: UUID,
        round_id: UUID,
        submission: str
    ) -> dict:
        """Submit round within party context."""
        # 1. Validate round belongs to this party session
        # 2. Call appropriate service method (submit_prompt/copy/vote)
        # 3. Update participant progress
        # 4. Check for phase transition
        # 5. Return result + session status
        pass
```

### 3.3 PartyScoringService

**Location:** `backend/services/qf/party_scoring_service.py`

**Responsibilities:**
- Aggregate player performance within session
- Calculate awards (Best Writer, Top Impostor, Sharpest Voter)
- Rank players by net earnings

**Key Methods:**

```python
class PartyScoringService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_session_results(self, session_id: UUID) -> dict:
        """
        Calculate comprehensive session results:
        - Overall ranking by net coins
        - Best Writer (most votes on originals)
        - Top Impostor (most votes on copies)
        - Sharpest Voter (best vote accuracy)
        - Individual stats per player
        """
        # 1. Get all participants
        # 2. Get all party rounds for this session
        # 3. Aggregate per player:
        #    - Coins spent (sum of round costs)
        #    - Coins earned (sum of payouts from transactions)
        #    - Net coins (earned - spent)
        #    - Votes received on originals (from phrasesets)
        #    - Votes fooled by copies (from phrasesets)
        #    - Vote accuracy (correct/total votes)
        # 4. Calculate awards
        # 5. Return structured result
        pass

    async def get_player_session_stats(
        self,
        session_id: UUID,
        player_id: UUID
    ) -> dict:
        """Get individual player stats for this session."""
        pass

    async def get_session_phrasesets_summary(
        self,
        session_id: UUID
    ) -> List[dict]:
        """Get summary of all phrasesets created in this session."""
        pass
```

### 3.4 PartyWebSocketManager

**Location:** `backend/services/qf/party_websocket_manager.py`

**Responsibilities:**
- Manage per-session WebSocket connections
- Broadcast session updates to all participants
- Handle player disconnect/reconnect

**Implementation Pattern:**
- Similar to existing `NotificationConnectionManager`
- Group connections by `session_id`
- Broadcast phase transitions, player readiness, progress updates

```python
class PartyWebSocketManager:
    def __init__(self):
        self.connections: Dict[UUID, List[WebSocket]] = {}  # session_id -> [websockets]

    async def connect(self, session_id: UUID, player_id: UUID, websocket: WebSocket):
        """Add player's websocket to session group."""
        pass

    def disconnect(self, session_id: UUID, websocket: WebSocket):
        """Remove websocket from session group."""
        pass

    async def broadcast_to_session(self, session_id: UUID, message: dict):
        """Send message to all connected players in session."""
        pass

    async def notify_phase_transition(
        self,
        session_id: UUID,
        new_phase: str,
        phase_data: dict
    ):
        """Notify all players of phase change."""
        pass

    async def notify_player_progress(
        self,
        session_id: UUID,
        progress_data: dict
    ):
        """Notify all players of updated progress."""
        pass
```

---

## 4. API Endpoints

### 4.1 Party Session Endpoints

**Base Path:** `/qf/party`

#### `POST /party/create`

Create a new party session.

**Request:**
```json
{
  "min_players": 3,
  "max_players": 8
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "party_code": "ABCD1234",
  "host_player_id": "uuid",
  "status": "OPEN",
  "current_phase": "LOBBY",
  "created_at": "2025-01-15T10:00:00Z",
  "participants": [
    {
      "player_id": "uuid",
      "username": "Host Player",
      "is_host": true,
      "status": "JOINED",
      "joined_at": "2025-01-15T10:00:00Z"
    }
  ],
  "min_players": 3,
  "max_players": 8
}
```

#### `POST /party/join`

Join an existing party session.

**Request:**
```json
{
  "party_code": "ABCD1234"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "party_code": "ABCD1234",
  "status": "OPEN",
  "current_phase": "LOBBY",
  "participants": [
    {"player_id": "uuid", "username": "Host", "is_host": true, "status": "READY"},
    {"player_id": "uuid", "username": "You", "is_host": false, "status": "JOINED"}
  ],
  "participant_count": 2,
  "min_players": 3,
  "max_players": 8
}
```

**Errors:**
- `404 session_not_found` - Invalid party code
- `400 session_already_started` - Session in progress
- `400 session_full` - Max players reached
- `409 already_joined` - Player already in session

#### `POST /party/{session_id}/ready`

Mark player as ready in lobby.

**Response:**
```json
{
  "participant_id": "uuid",
  "status": "READY",
  "session": {
    "ready_count": 3,
    "total_count": 4,
    "can_start": false
  }
}
```

#### `POST /party/{session_id}/start`

Start the party session (host only).

**Response:**
```json
{
  "session_id": "uuid",
  "status": "IN_PROGRESS",
  "current_phase": "PROMPT",
  "phase_started_at": "2025-01-15T10:05:00Z",
  "locked_at": "2025-01-15T10:05:00Z",
  "participants": [...]
}
```

**Errors:**
- `403 not_host` - Only host can start
- `400 not_enough_players` - Below min_players threshold
- `400 session_already_started` - Already in progress

#### `GET /party/{session_id}/status`

Get current session status.

**Response:**
```json
{
  "session_id": "uuid",
  "party_code": "ABCD1234",
  "status": "IN_PROGRESS",
  "current_phase": "COPY",
  "phase_started_at": "2025-01-15T10:10:00Z",
  "participants": [
    {
      "player_id": "uuid",
      "username": "Player1",
      "is_host": true,
      "prompts_submitted": 1,
      "copies_submitted": 2,
      "votes_submitted": 0,
      "prompts_required": 1,
      "copies_required": 2,
      "votes_required": 3,
      "phase_complete": true
    },
    {
      "player_id": "uuid",
      "username": "Player2",
      "prompts_submitted": 1,
      "copies_submitted": 1,
      "votes_submitted": 0,
      "prompts_required": 1,
      "copies_required": 2,
      "votes_required": 3,
      "phase_complete": false
    }
  ],
  "progress": {
    "total_prompts": 4,
    "total_copies": 6,
    "total_votes": 0,
    "required_prompts": 4,
    "required_copies": 8,
    "required_votes": 12,
    "players_ready_for_next_phase": 1,
    "total_players": 4
  }
}
```

#### `GET /party/{session_id}/results`

Get final match results (RESULTS phase only).

**Response:**
```json
{
  "session_id": "uuid",
  "party_code": "ABCD1234",
  "completed_at": "2025-01-15T10:45:00Z",
  "rankings": [
    {
      "rank": 1,
      "player_id": "uuid",
      "username": "WinnerPlayer",
      "net_coins": 150,
      "coins_spent": 200,
      "coins_earned": 350,
      "prompts_submitted": 1,
      "copies_submitted": 2,
      "votes_submitted": 3,
      "vote_accuracy": 100.0
    }
  ],
  "awards": {
    "best_writer": {
      "player_id": "uuid",
      "username": "BestWriter",
      "votes_received": 8,
      "metric_value": 8
    },
    "top_impostor": {
      "player_id": "uuid",
      "username": "TopImpostor",
      "votes_fooled": 6,
      "metric_value": 6
    },
    "sharpest_voter": {
      "player_id": "uuid",
      "username": "SharpVoter",
      "vote_accuracy": 100.0,
      "metric_value": 100.0
    }
  },
  "phrasesets_summary": [
    {
      "phraseset_id": "uuid",
      "prompt_text": "the meaning of life is",
      "vote_count": 4,
      "original_player": "Player1",
      "most_votes": "original"
    }
  ]
}
```

### 4.2 Party Round Endpoints

#### `POST /party/{session_id}/rounds/prompt`

Start prompt round within party session.

**Response:**
```json
{
  "round_id": "uuid",
  "party_round_id": "uuid",
  "prompt_text": "my deepest desire is to be (a/an)",
  "expires_at": "2025-01-15T10:15:00Z",
  "cost": 100,
  "session_progress": {
    "your_prompts_submitted": 1,
    "prompts_required": 1,
    "players_done": 2,
    "total_players": 4
  }
}
```

**Errors:**
- `400 wrong_phase` - Session not in PROMPT phase
- `400 already_submitted` - Player already submitted prompt
- `400 insufficient_balance` - Not enough coins

#### `POST /party/{session_id}/rounds/copy`

Start copy round within party session.

**Response:**
```json
{
  "round_id": "uuid",
  "party_round_id": "uuid",
  "original_phrase": "FAMOUS",
  "prompt_round_id": "uuid",
  "expires_at": "2025-01-15T10:20:00Z",
  "cost": 50,
  "discount_active": false,
  "is_second_copy": false,
  "from_party": true,
  "session_progress": {
    "your_copies_submitted": 1,
    "copies_required": 2,
    "players_done": 1,
    "total_players": 4
  }
}
```

**Errors:**
- `400 wrong_phase` - Session not in COPY phase
- `400 copies_complete` - Player submitted all required copies
- `400 no_prompts_available` - No eligible prompts

#### `POST /party/{session_id}/rounds/vote`

Start vote round within party session.

**Response:**
```json
{
  "round_id": "uuid",
  "party_round_id": "uuid",
  "phraseset_id": "uuid",
  "prompt_text": "the secret to happiness is",
  "phrases": ["LOVE", "MONEY", "CONTENTMENT"],
  "expires_at": "2025-01-15T10:30:00Z",
  "from_party": true,
  "session_progress": {
    "your_votes_submitted": 1,
    "votes_required": 3,
    "players_done": 0,
    "total_players": 4
  }
}
```

**Errors:**
- `400 wrong_phase` - Session not in VOTE phase
- `400 votes_complete` - Player submitted all required votes
- `400 no_phrasesets_available` - No eligible phrasesets

#### `POST /party/{session_id}/rounds/{round_id}/submit`

Submit round within party context.

**Request:**
```json
{
  "phrase": "FAMOUS"
}
```

**Response:**
```json
{
  "success": true,
  "phrase": "FAMOUS",
  "round_type": "prompt",
  "session_progress": {
    "your_prompts_submitted": 1,
    "prompts_required": 1,
    "phase_complete": true,
    "players_ready": 3,
    "total_players": 4
  },
  "phase_transition": null
}
```

**Response (with phase transition):**
```json
{
  "success": true,
  "phrase": "WEALTHY",
  "round_type": "copy",
  "session_progress": {
    "your_copies_submitted": 2,
    "copies_required": 2,
    "phase_complete": true,
    "players_ready": 4,
    "total_players": 4
  },
  "phase_transition": {
    "new_phase": "VOTE",
    "message": "All players finished copying! Moving to voting phase.",
    "phase_started_at": "2025-01-15T10:25:00Z"
  }
}
```

#### `POST /party/{session_id}/leave`

Leave party session (lobby only, or mark as disconnected).

**Response:**
```json
{
  "success": true,
  "message": "Left party session"
}
```

---

## 5. WebSocket Communication

### 5.1 WebSocket Endpoint

**Path:** `GET /qf/party/{session_id}/ws?token={token}`

**Authentication:** Short-lived token from `/auth/ws-token`

### 5.2 Message Types (Server → Client)

#### Session Update

```json
{
  "type": "session_update",
  "session_id": "uuid",
  "status": "IN_PROGRESS",
  "current_phase": "COPY",
  "participants": [...],
  "progress": {...},
  "timestamp": "2025-01-15T10:15:00Z"
}
```

#### Player Joined

```json
{
  "type": "player_joined",
  "player_id": "uuid",
  "username": "NewPlayer",
  "participant_count": 4,
  "timestamp": "2025-01-15T10:01:00Z"
}
```

#### Player Left

```json
{
  "type": "player_left",
  "player_id": "uuid",
  "username": "LeftPlayer",
  "participant_count": 3,
  "timestamp": "2025-01-15T10:02:00Z"
}
```

#### Player Ready

```json
{
  "type": "player_ready",
  "player_id": "uuid",
  "username": "ReadyPlayer",
  "ready_count": 3,
  "total_count": 4,
  "timestamp": "2025-01-15T10:03:00Z"
}
```

#### Phase Transition

```json
{
  "type": "phase_transition",
  "old_phase": "PROMPT",
  "new_phase": "COPY",
  "phase_started_at": "2025-01-15T10:10:00Z",
  "message": "All players finished prompts! Time to write copies.",
  "timestamp": "2025-01-15T10:10:00Z"
}
```

#### Progress Update

```json
{
  "type": "progress_update",
  "player_id": "uuid",
  "username": "Player1",
  "action": "submitted_prompt",
  "progress": {
    "prompts_submitted": 1,
    "copies_submitted": 0,
    "votes_submitted": 0
  },
  "session_progress": {
    "players_done_with_phase": 2,
    "total_players": 4
  },
  "timestamp": "2025-01-15T10:08:00Z"
}
```

#### Session Started

```json
{
  "type": "session_started",
  "current_phase": "PROMPT",
  "locked_at": "2025-01-15T10:05:00Z",
  "participant_count": 4,
  "message": "Party started! Everyone write your best original phrase.",
  "timestamp": "2025-01-15T10:05:00Z"
}
```

#### Session Completed

```json
{
  "type": "session_completed",
  "completed_at": "2025-01-15T10:45:00Z",
  "message": "Match complete! Check out the results.",
  "timestamp": "2025-01-15T10:45:00Z"
}
```

### 5.3 Message Types (Client → Server)

Clients only send heartbeat/ping messages. All actions are via REST API.

```json
{
  "type": "ping"
}
```

---

## 6. Phase-by-Phase Game Flow

### 6.1 Phase 0: LOBBY

**What happens:**
- Host creates session, receives party code
- Other players join via code
- Players mark themselves ready
- Host starts when ≥ min_players are ready

**Backend logic:**
```python
# Create session
session = await party_service.create_session(
    host_player_id=current_player.player_id,
    min_players=3,
    max_players=8
)

# Generate unique party code (8 chars, alphanumeric)
party_code = generate_party_code()

# Add host as first participant
await party_service.add_participant(session.session_id, host_player_id)

# Broadcast via WebSocket
await ws_manager.broadcast_to_session(session.session_id, {
    "type": "session_update",
    ...
})
```

**Frontend UI:**
- Show party code prominently
- Live list of joined players
- "Ready" button for each player
- "Start Party" button for host (enabled when ≥ min_players ready)

### 6.2 Phase 1: PROMPT

**What happens:**
- Each player writes 1 original phrase
- Timer: 3 minutes per round (standard prompt round timing)
- When all players submit, transition to COPY

**Backend logic:**
```python
async def start_party_prompt_round(session_id, player_id):
    # 1. Validate phase
    session = await get_session(session_id)
    if session.current_phase != "PROMPT":
        raise WrongPhaseError()

    # 2. Check player hasn't already submitted
    participant = await get_participant(session_id, player_id)
    if participant.prompts_submitted >= 1:
        raise AlreadySubmittedError()

    # 3. Start normal prompt round
    round = await round_service.start_prompt_round(player_id)

    # 4. Link to party
    await create_party_round(session_id, round.round_id, "prompt", "PROMPT")

    # 5. Return round + session progress
    return {
        "round": round,
        "session_progress": await get_session_progress(session_id, player_id)
    }

async def submit_party_prompt(session_id, player_id, round_id, phrase):
    # 1. Submit via normal flow
    result = await round_service.submit_prompt_phrase(round_id, phrase, player_id)

    # 2. Update participant progress
    await increment_participant_counter(session_id, player_id, "prompts_submitted")

    # 3. Broadcast progress update
    await ws_manager.notify_player_progress(session_id, {
        "player_id": player_id,
        "action": "submitted_prompt",
        ...
    })

    # 4. Check if all done
    if await all_participants_done_with_prompts(session_id):
        await advance_to_copy_phase(session_id)

    return result
```

**Phase transition to COPY:**
```python
async def advance_to_copy_phase(session_id):
    session = await get_session(session_id)
    session.current_phase = "COPY"
    session.phase_started_at = datetime.now(UTC)
    await db.commit()

    # Broadcast phase transition
    await ws_manager.notify_phase_transition(session_id, "COPY", {
        "message": "All prompts submitted! Time to write copies."
    })
```

### 6.3 Phase 2: COPY

**What happens:**
- Each player writes 2 copy phrases
- Copies are preferentially drawn from party prompts
- When all players submit 2 copies each, transition to VOTE

**Backend logic:**
```python
async def start_party_copy_round(session_id, player_id):
    # 1. Validate phase
    session = await get_session(session_id)
    if session.current_phase != "COPY":
        raise WrongPhaseError()

    # 2. Check player has copies remaining
    participant = await get_participant(session_id, player_id)
    if participant.copies_submitted >= 2:
        raise CopiesCompleteError()

    # 3. Get eligible prompts (party-first, then global)
    eligible_prompts = await get_eligible_prompts_for_party_copy(
        session_id,
        player_id
    )
    # Exclude: player's own prompts, already copied by this player

    if not eligible_prompts:
        raise NoPromptsAvailableError()

    # 4. Select prompt (prioritize party prompts)
    prompt_round_id = select_prompt_for_copy(eligible_prompts)

    # 5. Start copy round with specific prompt
    round = await round_service.start_copy_round(
        player_id,
        prompt_round_id=prompt_round_id
    )

    # 6. Link to party
    await create_party_round(session_id, round.round_id, "copy", "COPY")

    return round

async def submit_party_copy(session_id, player_id, round_id, phrase):
    # 1. Submit via normal flow
    result = await round_service.submit_copy_phrase(round_id, phrase, player_id)

    # 2. Update participant progress
    await increment_participant_counter(session_id, player_id, "copies_submitted")

    # 3. If phraseset created, link to party
    if result.get("phraseset_id"):
        await create_party_phraseset(session_id, result["phraseset_id"], "COPY")

    # 4. Broadcast progress
    await ws_manager.notify_player_progress(session_id, {...})

    # 5. Check if all done
    if await all_participants_done_with_copies(session_id):
        await advance_to_vote_phase(session_id)

    return result
```

**Phase transition to VOTE:**
```python
async def advance_to_vote_phase(session_id):
    # 1. Update session phase
    session.current_phase = "VOTE"
    session.phase_started_at = datetime.now(UTC)

    # 2. Mark all party phrasesets as available for voting
    await mark_party_phrasesets_available(session_id)

    # 3. Broadcast
    await ws_manager.notify_phase_transition(session_id, "VOTE", {
        "message": "All copies submitted! Time to vote."
    })
```

### 6.4 Phase 3: VOTE

**What happens:**
- Each player votes on 3-4 phrasesets
- Players cannot vote on phrasesets they contributed to
- Votes preferentially drawn from party phrasesets
- When all players submit required votes, transition to RESULTS

**Backend logic:**
```python
async def start_party_vote_round(session_id, player_id):
    # 1. Validate phase
    session = await get_session(session_id)
    if session.current_phase != "VOTE":
        raise WrongPhaseError()

    # 2. Check player has votes remaining
    participant = await get_participant(session_id, player_id)
    votes_required = session.votes_per_player
    if participant.votes_submitted >= votes_required:
        raise VotesCompleteError()

    # 3. Get eligible phrasesets
    eligible = await get_eligible_phrasesets_for_party_vote(
        session_id,
        player_id
    )
    # Exclude: phrasesets where player was prompt/copy contributor
    # Exclude: already voted by this player
    # Prioritize: party phrasesets over global

    if not eligible:
        raise NoPhrasesetsAvailableError()

    # 4. Select phraseset
    phraseset_id = select_phraseset_for_vote(eligible)

    # 5. Start vote round
    round = await round_service.start_vote_round(
        player_id,
        phraseset_id=phraseset_id
    )

    # 6. Link to party
    await create_party_round(session_id, round.round_id, "vote", "VOTE")

    return round

async def submit_party_vote(session_id, player_id, phraseset_id, phrase):
    # 1. Submit via normal flow
    result = await vote_service.submit_vote(
        round_id, phraseset_id, phrase, player_id
    )

    # 2. Update participant progress
    await increment_participant_counter(session_id, player_id, "votes_submitted")

    # 3. Broadcast progress
    await ws_manager.notify_player_progress(session_id, {...})

    # 4. Check if all done
    if await all_participants_done_with_votes(session_id):
        await advance_to_results_phase(session_id)

    return result
```

**Phase transition to RESULTS:**
```python
async def advance_to_results_phase(session_id):
    # 1. Update session phase
    session.current_phase = "RESULTS"
    session.phase_started_at = datetime.now(UTC)
    session.completed_at = datetime.now(UTC)

    # 2. Calculate match results
    results = await party_scoring_service.calculate_session_results(session_id)

    # 3. Store results (cache in Redis or session table JSON field)
    await cache_session_results(session_id, results)

    # 4. Broadcast
    await ws_manager.notify_phase_transition(session_id, "RESULTS", {
        "message": "All votes submitted! Check out the results.",
        "results_available": True
    })
```

### 6.5 Phase 4: RESULTS

**What happens:**
- Display match scoreboard
- Show overall rankings by net coins
- Show category awards
- Show phraseset highlights
- "Play Again" and "Return to Menu" options

**Backend logic:**
```python
async def get_session_results(session_id):
    # 1. Validate session is in RESULTS phase
    session = await get_session(session_id)
    if session.current_phase != "RESULTS":
        raise WrongPhaseError()

    # 2. Retrieve cached results or calculate
    results = await get_cached_results(session_id)
    if not results:
        results = await party_scoring_service.calculate_session_results(session_id)
        await cache_session_results(session_id, results)

    return results

async def calculate_session_results(session_id):
    # 1. Get all participants
    participants = await get_participants(session_id)

    # 2. Get all party rounds
    party_rounds = await get_party_rounds(session_id)
    round_ids = [pr.round_id for pr in party_rounds]

    # 3. Get all transactions for these rounds
    transactions = await get_transactions_for_rounds(round_ids)

    # 4. Get all phrasesets for this session
    party_phrasesets = await get_party_phrasesets(session_id)

    # 5. Aggregate per player
    player_stats = {}
    for participant in participants:
        player_id = participant.player_id

        # Get rounds for this player
        player_rounds = [r for r in party_rounds if r.participant_id == participant.participant_id]
        player_round_ids = [r.round_id for r in player_rounds]

        # Calculate spent (entry costs)
        spent = sum([
            txn.amount for txn in transactions
            if txn.player_id == player_id
            and txn.type in ['prompt_entry', 'copy_entry', 'vote_entry']
            and txn.reference_id in player_round_ids
        ])
        spent = abs(spent)  # Entry costs are negative

        # Calculate earned (payouts)
        earned = sum([
            txn.amount for txn in transactions
            if txn.player_id == player_id
            and txn.type in ['vote_payout', 'prize_payout']
            and txn.reference_id in (player_round_ids + [pp.phraseset_id for pp in party_phrasesets])
        ])

        # Net coins
        net = earned - spent

        # Get phrasesets where this player was prompt contributor
        prompt_phrasesets = [
            pp for pp in party_phrasesets
            if pp.phraseset.prompt_round.player_id == player_id
        ]

        # Count votes received on originals
        votes_on_originals = sum([
            len([v for v in pp.phraseset.votes if v.voted_phrase == pp.phraseset.original_phrase])
            for pp in prompt_phrasesets
        ])

        # Get phrasesets where this player was copy contributor
        copy_phrasesets = [
            pp for pp in party_phrasesets
            if (pp.phraseset.copy_round_1.player_id == player_id or
                pp.phraseset.copy_round_2.player_id == player_id)
        ]

        # Count votes fooled (votes on this player's copies)
        votes_fooled = 0
        for pp in copy_phrasesets:
            if pp.phraseset.copy_round_1.player_id == player_id:
                votes_fooled += len([v for v in pp.phraseset.votes if v.voted_phrase == pp.phraseset.copy_phrase_1])
            if pp.phraseset.copy_round_2.player_id == player_id:
                votes_fooled += len([v for v in pp.phraseset.votes if v.voted_phrase == pp.phraseset.copy_phrase_2])

        # Get votes by this player
        player_votes = [
            v for v in Vote.query.filter(...)
            if v.phraseset_id in [pp.phraseset_id for pp in party_phrasesets]
            and v.player_id == player_id
        ]

        correct_votes = len([v for v in player_votes if v.correct])
        total_votes = len(player_votes)
        vote_accuracy = (correct_votes / total_votes * 100) if total_votes > 0 else 0

        player_stats[player_id] = {
            "player_id": player_id,
            "username": participant.player.username,
            "spent": spent,
            "earned": earned,
            "net": net,
            "votes_on_originals": votes_on_originals,
            "votes_fooled": votes_fooled,
            "correct_votes": correct_votes,
            "total_votes": total_votes,
            "vote_accuracy": vote_accuracy,
            "prompts_submitted": participant.prompts_submitted,
            "copies_submitted": participant.copies_submitted,
            "votes_submitted": participant.votes_submitted
        }

    # 6. Calculate rankings (by net coins)
    rankings = sorted(
        player_stats.values(),
        key=lambda x: x["net"],
        reverse=True
    )
    for i, player in enumerate(rankings):
        player["rank"] = i + 1

    # 7. Calculate awards
    best_writer = max(player_stats.values(), key=lambda x: x["votes_on_originals"])
    top_impostor = max(player_stats.values(), key=lambda x: x["votes_fooled"])
    sharpest_voter = max(player_stats.values(), key=lambda x: x["vote_accuracy"])

    # 8. Get phraseset summaries
    phraseset_summaries = []
    for pp in party_phrasesets:
        ps = pp.phraseset
        vote_counts = {
            ps.original_phrase: len([v for v in ps.votes if v.voted_phrase == ps.original_phrase]),
            ps.copy_phrase_1: len([v for v in ps.votes if v.voted_phrase == ps.copy_phrase_1]),
            ps.copy_phrase_2: len([v for v in ps.votes if v.voted_phrase == ps.copy_phrase_2])
        }
        most_votes_phrase = max(vote_counts, key=vote_counts.get)

        phraseset_summaries.append({
            "phraseset_id": ps.phraseset_id,
            "prompt_text": ps.prompt_text,
            "vote_count": ps.vote_count,
            "original_player": ps.prompt_round.player.username,
            "most_votes": "original" if most_votes_phrase == ps.original_phrase else "copy"
        })

    return {
        "session_id": session_id,
        "completed_at": session.completed_at,
        "rankings": rankings,
        "awards": {
            "best_writer": {
                "player_id": best_writer["player_id"],
                "username": best_writer["username"],
                "votes_received": best_writer["votes_on_originals"],
                "metric_value": best_writer["votes_on_originals"]
            },
            "top_impostor": {
                "player_id": top_impostor["player_id"],
                "username": top_impostor["username"],
                "votes_fooled": top_impostor["votes_fooled"],
                "metric_value": top_impostor["votes_fooled"]
            },
            "sharpest_voter": {
                "player_id": sharpest_voter["player_id"],
                "username": sharpest_voter["username"],
                "vote_accuracy": sharpest_voter["vote_accuracy"],
                "metric_value": sharpest_voter["vote_accuracy"]
            }
        },
        "phrasesets_summary": phraseset_summaries
    }
```

---

## 7. Economy Integration

### 7.1 Core Principle

**All coins are real.** Party Mode uses the exact same transaction flow as solo play:
- Prompt entry: -100 FC
- Copy entry: -50 FC (or -40 FC with discount)
- Vote entry: -10 FC
- Correct vote: +20 FC
- Prize payouts: Variable based on votes

### 7.2 Wallet Integration

```python
# When starting a party round, use existing transaction service
await transaction_service.deduct_balance(
    player_id=player.player_id,
    amount=cost,
    transaction_type="prompt_entry",
    reference_id=round.round_id
)

# Payouts work exactly the same
await transaction_service.add_balance(
    player_id=player.player_id,
    amount=payout,
    transaction_type="vote_payout",
    reference_id=vote.vote_id
)
```

### 7.3 Session-Local Aggregation

Party results show **session-scoped** coin flow:

```python
# Get coins spent in THIS session
session_spent = sum of entry costs for rounds in party_rounds

# Get coins earned in THIS session
session_earned = sum of payouts for rounds/phrasesets in party_rounds

# Net for THIS session
session_net = session_earned - session_spent
```

**Important:** These are **derived metrics**, not separate balances. The player's global `wallet` and `vault` are the source of truth.

### 7.4 Preventing Exploitation

**Can players exploit Party Mode for coins?**

No, because:
1. Entry costs are exactly the same as solo play
2. Payouts come from the same prize pool formula
3. Voting on party phrasesets has the same constraints (no self-voting)
4. Copy discount threshold applies globally, not per-session

**Example edge case:**
- 3 players collude to vote incorrectly and boost one player's copies
- **Result:** That player earns more, but the voters lose coins (no correct vote payout)
- Net effect: Same as any voting pattern in solo play

### 7.5 Minimum Balance Requirements

**Do we need minimum balance to join?**

No formal requirement, but practical considerations:
- Player needs 100 FC for prompt round
- Player needs 100 FC (2×50) for copy rounds
- Player needs 30 FC (3×10) for vote rounds
- **Total minimum:** ~230 FC to complete a match

**Recommendation:** Frontend warning if balance < 250 FC when joining.

---

## 8. Frontend Implementation

### 8.1 New Pages/Components

#### PartyLobby Page

**Route:** `/party/lobby/:sessionId`

**Features:**
- Display party code prominently
- Live player list with ready status
- "Ready" button (toggles ready/not ready)
- "Start Party" button (host only, enabled when ≥ min_players ready)
- "Leave Party" button
- Live updates via WebSocket

**State:**
```typescript
interface PartyLobbyState {
  session: PartySession | null;
  participants: PartyParticipant[];
  currentPlayer: PartyParticipant | null;
  isHost: boolean;
  canStart: boolean;
  loading: boolean;
  error: string | null;
}
```

**WebSocket handlers:**
```typescript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case 'player_joined':
      addParticipant(message);
      showToast(`${message.username} joined!`);
      break;

    case 'player_left':
      removeParticipant(message.player_id);
      showToast(`${message.username} left`);
      break;

    case 'player_ready':
      updateParticipantStatus(message.player_id, 'READY');
      break;

    case 'session_started':
      navigate('/party/play/' + sessionId);
      break;
  }
};
```

#### PartyPlay Page

**Route:** `/party/play/:sessionId`

**Features:**
- Phase indicator banner (PROMPT / COPY / VOTE)
- Session progress widget
- Phase-specific UI (reuse existing round components)
- "Waiting for others..." state between phases
- Live progress updates via WebSocket

**State:**
```typescript
interface PartyPlayState {
  session: PartySession | null;
  currentPhase: PartyPhase;
  activeRound: Round | null;
  sessionProgress: SessionProgress;
  phaseComplete: boolean;
  waitingForOthers: boolean;
}
```

**Phase-specific components:**
```typescript
// Reuse existing components:
- PromptRoundForm (for Phase 1)
- CopyRoundForm (for Phase 2)
- VoteRoundForm (for Phase 3)

// New wrapper:
<PartyRoundWrapper
  phase={currentPhase}
  sessionId={sessionId}
  onSubmit={handleSubmit}
  sessionProgress={sessionProgress}
/>
```

**WebSocket handlers:**
```typescript
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch (message.type) {
    case 'progress_update':
      updateSessionProgress(message.session_progress);
      showToast(`${message.username} ${message.action}`);
      break;

    case 'phase_transition':
      setCurrentPhase(message.new_phase);
      showPhaseTransitionModal(message);
      setPhaseComplete(false);
      break;

    case 'session_completed':
      navigate('/party/results/' + sessionId);
      break;
  }
};
```

#### PartyResults Page

**Route:** `/party/results/:sessionId`

**Features:**
- Match scoreboard (rankings table)
- Award badges (Best Writer, Top Impostor, Sharpest Voter)
- Individual player stats
- Phraseset highlights carousel
- "Play Again" button (creates new session with same players)
- "Return to Dashboard" button

**Layout:**
```
┌─────────────────────────────────────┐
│      🎉 PARTY RESULTS 🎉            │
├─────────────────────────────────────┤
│  Overall Rankings                   │
│  ┌──┬──────────┬─────┬──────┬─────┐│
│  │1 │Winner    │+150 │ 200  │ 350 ││
│  │2 │Runner    │+80  │ 200  │ 280 ││
│  └──┴──────────┴─────┴──────┴─────┘│
├─────────────────────────────────────┤
│  🏆 Awards                          │
│  Best Writer: Winner (8 votes)      │
│  Top Impostor: Faker (6 fooled)     │
│  Sharpest Voter: Sharp (100%)       │
├─────────────────────────────────────┤
│  📊 Your Stats                      │
│  Net Coins: +150                    │
│  Prompts: 1  Copies: 2  Votes: 3    │
│  Vote Accuracy: 100%                │
├─────────────────────────────────────┤
│  [Play Again]  [Return to Dashboard]│
└─────────────────────────────────────┘
```

#### PartyJoin Modal

**Trigger:** "Join Party" button on dashboard

**Features:**
- Input field for party code
- "Join" button
- Loading/error states
- Auto-navigation to lobby on success

#### PartyCreate Modal

**Trigger:** "Start Party" button on dashboard

**Features:**
- Min players selector (3-8)
- Max players selector (3-8)
- "Create Party" button
- Auto-navigation to lobby on success

### 8.2 Context Updates

#### PartyContext

**Location:** `qf_frontend/src/contexts/PartyContext.tsx`

**State:**
```typescript
interface PartyState {
  currentSession: PartySession | null;
  sessionStatus: SessionStatus | null;
  sessionResults: SessionResults | null;
  loading: boolean;
  error: string | null;
  websocket: WebSocket | null;
  connected: boolean;
}
```

**Actions:**
```typescript
interface PartyActions {
  createSession: (config: CreateSessionConfig) => Promise<PartySession>;
  joinSession: (partyCode: string) => Promise<PartySession>;
  leaveSession: (sessionId: string) => Promise<void>;
  markReady: (sessionId: string) => Promise<void>;
  startSession: (sessionId: string) => Promise<void>;
  getSessionStatus: (sessionId: string) => Promise<SessionStatus>;
  getSessionResults: (sessionId: string) => Promise<SessionResults>;

  // Round actions (delegate to coordination service)
  startPartyPromptRound: (sessionId: string) => Promise<Round>;
  startPartyCopyRound: (sessionId: string) => Promise<Round>;
  startPartyVoteRound: (sessionId: string) => Promise<Round>;
  submitPartyRound: (sessionId: string, roundId: string, phrase: string) => Promise<any>;

  // WebSocket management
  connectWebSocket: (sessionId: string) => void;
  disconnectWebSocket: () => void;
}
```

**WebSocket lifecycle:**
```typescript
useEffect(() => {
  if (currentSession && isAuthenticated) {
    connectWebSocket(currentSession.session_id);
  }

  return () => {
    disconnectWebSocket();
  };
}, [currentSession, isAuthenticated]);
```

### 8.3 Routing Updates

**Add to routes:**
```typescript
// In App.tsx or routes.tsx
<Route path="/party/create" element={<PartyCreate />} />
<Route path="/party/join" element={<PartyJoin />} />
<Route path="/party/lobby/:sessionId" element={<PartyLobby />} />
<Route path="/party/play/:sessionId" element={<PartyPlay />} />
<Route path="/party/results/:sessionId" element={<PartyResults />} />
```

### 8.4 Dashboard Updates

**Add Party Mode buttons:**
```typescript
<div className="party-mode-section">
  <h2>Party Mode</h2>
  <div className="party-buttons">
    <button onClick={handleCreateParty}>
      🎉 Start a Party
    </button>
    <button onClick={handleJoinParty}>
      🎮 Join Party
    </button>
  </div>

  {activePartySession && (
    <div className="active-party-banner">
      <p>Active Party: {activePartySession.party_code}</p>
      <button onClick={() => navigate(`/party/lobby/${activePartySession.session_id}`)}>
        Rejoin
      </button>
    </div>
  )}
</div>
```

---

## 9. Testing Strategy

### 9.1 Backend Unit Tests

#### PartySessionService Tests

**File:** `tests/qf/test_party_session_service.py`

```python
async def test_create_session():
    """Test session creation with unique party code."""
    session = await party_service.create_session(host_player_id)
    assert session.party_code is not None
    assert len(session.party_code) == 8
    assert session.status == "OPEN"
    assert session.current_phase == "LOBBY"

async def test_join_session():
    """Test adding participants to session."""
    session = await party_service.create_session(host_player_id)
    participant = await party_service.add_participant(session.session_id, player2_id)
    assert participant.player_id == player2_id
    assert participant.status == "JOINED"

async def test_cannot_join_started_session():
    """Test joining fails after session starts."""
    session = await party_service.create_session(host_player_id)
    await party_service.start_session(session.session_id)

    with pytest.raises(SessionAlreadyStartedError):
        await party_service.add_participant(session.session_id, player2_id)

async def test_phase_transitions():
    """Test automatic phase transitions."""
    session = await setup_session_with_4_players()

    # All submit prompts
    for player in players:
        await coordination_service.submit_party_prompt(session.session_id, player.player_id, ...)

    # Should auto-advance to COPY
    session = await party_service.get_session(session.session_id)
    assert session.current_phase == "COPY"
```

#### PartyCoordinationService Tests

```python
async def test_start_party_prompt_validates_phase():
    """Test starting prompt round in wrong phase fails."""
    session = await setup_session_in_copy_phase()

    with pytest.raises(WrongPhaseError):
        await coordination_service.start_party_prompt_round(session.session_id, player_id)

async def test_copy_assignment_prioritizes_party_prompts():
    """Test copy rounds prefer party prompts over global."""
    session = await setup_session_with_prompts_and_global_prompts()

    round = await coordination_service.start_party_copy_round(session.session_id, player_id)

    # Verify assigned prompt is from party
    prompt_round = await get_round(round.prompt_round_id)
    party_round = await get_party_round(prompt_round.round_id)
    assert party_round.session_id == session.session_id

async def test_vote_excludes_self_contributions():
    """Test voting doesn't assign phrasesets player contributed to."""
    session = await setup_session_in_vote_phase()
    player = players[0]

    # Player contributed to phrasesets 1, 2, 3
    round = await coordination_service.start_party_vote_round(session.session_id, player.player_id)

    # Verify assigned phraseset doesn't include player
    phraseset = await get_phraseset(round.phraseset_id)
    assert phraseset.prompt_round.player_id != player.player_id
    assert phraseset.copy_round_1.player_id != player.player_id
    assert phraseset.copy_round_2.player_id != player.player_id
```

#### PartyScoringService Tests

```python
async def test_calculate_rankings():
    """Test session rankings calculation."""
    session = await setup_completed_session()
    results = await scoring_service.calculate_session_results(session.session_id)

    assert len(results["rankings"]) == 4
    assert results["rankings"][0]["rank"] == 1
    assert results["rankings"][0]["net"] >= results["rankings"][1]["net"]

async def test_award_calculations():
    """Test award winner selection."""
    session = await setup_completed_session()
    results = await scoring_service.calculate_session_results(session.session_id)

    best_writer = results["awards"]["best_writer"]
    assert best_writer["player_id"] is not None
    assert best_writer["votes_received"] > 0
```

### 9.2 Integration Tests

**File:** `tests/qf/integration/test_party_mode_flow.py`

```python
async def test_full_party_flow():
    """Test complete party mode flow from lobby to results."""
    # Setup 4 players
    players = await create_test_players(4)

    # 1. Create session
    session = await party_service.create_session(players[0].player_id)

    # 2. Players join
    for player in players[1:]:
        await party_service.add_participant(session.session_id, player.player_id)

    # 3. Mark ready
    for player in players:
        await party_service.mark_participant_ready(session.session_id, player.player_id)

    # 4. Start session
    session = await party_service.start_session(session.session_id)
    assert session.current_phase == "PROMPT"

    # 5. Each player submits prompt
    for player in players:
        round = await coordination_service.start_party_prompt_round(session.session_id, player.player_id)
        await coordination_service.submit_party_round(session.session_id, player.player_id, round.round_id, f"PHRASE{player.player_id}")

    # Should advance to COPY
    session = await party_service.get_session(session.session_id)
    assert session.current_phase == "COPY"

    # 6. Each player submits 2 copies
    for player in players:
        for i in range(2):
            round = await coordination_service.start_party_copy_round(session.session_id, player.player_id)
            await coordination_service.submit_party_round(session.session_id, player.player_id, round.round_id, f"COPY{i}")

    # Should advance to VOTE
    session = await party_service.get_session(session.session_id)
    assert session.current_phase == "VOTE"

    # 7. Each player submits 3 votes
    for player in players:
        for i in range(3):
            round = await coordination_service.start_party_vote_round(session.session_id, player.player_id)
            phraseset = await get_phraseset(round.phraseset_id)
            await coordination_service.submit_party_round(session.session_id, player.player_id, round.round_id, phraseset.original_phrase)

    # Should advance to RESULTS
    session = await party_service.get_session(session.session_id)
    assert session.current_phase == "RESULTS"

    # 8. Get results
    results = await scoring_service.calculate_session_results(session.session_id)
    assert len(results["rankings"]) == 4
    assert results["awards"]["best_writer"] is not None
```

### 9.3 Frontend Tests

#### PartyContext Tests

**File:** `qf_frontend/src/contexts/__tests__/PartyContext.test.tsx`

```typescript
describe('PartyContext', () => {
  it('creates session and connects websocket', async () => {
    const { result } = renderHook(() => useParty());

    const session = await result.current.createSession({ min_players: 3, max_players: 8 });

    expect(session.party_code).toBeDefined();
    expect(result.current.connected).toBe(true);
  });

  it('handles phase transition messages', async () => {
    const { result } = renderHook(() => useParty());

    // Simulate WebSocket message
    act(() => {
      mockWebSocket.onmessage({
        data: JSON.stringify({
          type: 'phase_transition',
          new_phase: 'COPY',
          message: 'All prompts submitted!'
        })
      });
    });

    expect(result.current.currentSession?.current_phase).toBe('COPY');
  });
});
```

#### E2E Tests

**File:** `qf_frontend/e2e/party-mode.spec.ts`

```typescript
test('complete party flow', async ({ page, context }) => {
  // Create 4 browser contexts (simulate 4 players)
  const players = await Promise.all([
    createAuthenticatedContext(context, 'player1'),
    createAuthenticatedContext(context, 'player2'),
    createAuthenticatedContext(context, 'player3'),
    createAuthenticatedContext(context, 'player4'),
  ]);

  const [host, ...others] = players;

  // Host creates party
  await host.click('text=Start a Party');
  const partyCode = await host.textContent('[data-testid="party-code"]');

  // Others join
  for (const player of others) {
    await player.click('text=Join Party');
    await player.fill('[data-testid="party-code-input"]', partyCode);
    await player.click('text=Join');
  }

  // All mark ready
  for (const player of players) {
    await player.click('text=Ready');
  }

  // Host starts
  await host.click('text=Start Party');

  // All should be on play page
  for (const player of players) {
    await player.waitForURL(/\/party\/play\//);
  }

  // ... continue through phases ...
});
```

### 9.4 Performance Tests

**Load test:** 20 concurrent party sessions with 4 players each

```python
import asyncio
from locust import HttpUser, task, between

class PartyPlayer(HttpUser):
    wait_time = between(1, 3)

    @task
    def play_party(self):
        # Create session
        response = self.client.post("/qf/party/create")
        session = response.json()

        # Connect websocket
        ws = self.environment.runner.ws_connect(
            f"/qf/party/{session['session_id']}/ws?token={self.token}"
        )

        # Start rounds
        self.client.post(f"/qf/party/{session['session_id']}/rounds/prompt")
        # ... etc
```

---

## 10. Migration & Deployment

### 10.1 Database Migration

**File:** `backend/migrations/versions/XXX_add_party_mode.py`

```python
"""Add Party Mode tables

Revision ID: XXX
Revises: YYY
Create Date: 2025-01-XX XX:XX:XX
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'XXX'
down_revision = 'YYY'
branch_labels = None
depends_on = None

def upgrade():
    # PartySession
    op.create_table(
        'party_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('party_code', sa.String(8), unique=True, nullable=False),
        sa.Column('host_player_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('players.player_id', ondelete='CASCADE'), nullable=False),
        sa.Column('min_players', sa.Integer, nullable=False, server_default='3'),
        sa.Column('max_players', sa.Integer, nullable=False, server_default='8'),
        sa.Column('prompts_per_player', sa.Integer, nullable=False, server_default='1'),
        sa.Column('copies_per_player', sa.Integer, nullable=False, server_default='2'),
        sa.Column('votes_per_player', sa.Integer, nullable=False, server_default='3'),
        sa.Column('current_phase', sa.String(20), nullable=False, server_default='LOBBY'),
        sa.Column('phase_started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('phase_expires_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('status', sa.String(20), nullable=False, server_default='OPEN'),
        sa.Column('locked_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True)),
    )
    op.create_index('idx_party_sessions_code', 'party_sessions', ['party_code'])
    op.create_index('idx_party_sessions_status', 'party_sessions', ['status', 'created_at'])
    op.create_index('idx_party_sessions_host', 'party_sessions', ['host_player_id'])

    # PartyParticipant
    op.create_table(
        'party_participants',
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('players.player_id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='JOINED'),
        sa.Column('is_host', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('prompts_submitted', sa.Integer, nullable=False, server_default='0'),
        sa.Column('copies_submitted', sa.Integer, nullable=False, server_default='0'),
        sa.Column('votes_submitted', sa.Integer, nullable=False, server_default='0'),
        sa.Column('joined_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('ready_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('last_activity_at', sa.TIMESTAMP(timezone=True)),
    )
    op.create_unique_constraint('uq_party_participants_session_player', 'party_participants', ['session_id', 'player_id'])
    op.create_index('idx_party_participants_session', 'party_participants', ['session_id'])
    op.create_index('idx_party_participants_player', 'party_participants', ['player_id'])
    op.create_index('idx_party_participants_status', 'party_participants', ['session_id', 'status'])

    # PartyRound
    op.create_table(
        'party_rounds',
        sa.Column('party_round_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('round_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('rounds.round_id', ondelete='CASCADE'), nullable=False),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('party_participants.participant_id', ondelete='CASCADE'), nullable=False),
        sa.Column('round_type', sa.String(10), nullable=False),
        sa.Column('phase', sa.String(20), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_unique_constraint('uq_party_rounds_session_round', 'party_rounds', ['session_id', 'round_id'])
    op.create_index('idx_party_rounds_session', 'party_rounds', ['session_id', 'phase'])
    op.create_index('idx_party_rounds_participant', 'party_rounds', ['participant_id'])
    op.create_index('idx_party_rounds_round', 'party_rounds', ['round_id'])

    # PartyPhraseset
    op.create_table(
        'party_phrasesets',
        sa.Column('party_phraseset_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('party_sessions.session_id', ondelete='CASCADE'), nullable=False),
        sa.Column('phraseset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('phrasesets.phraseset_id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_in_phase', sa.String(20), nullable=False),
        sa.Column('available_for_voting', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_unique_constraint('uq_party_phrasesets_session_phraseset', 'party_phrasesets', ['session_id', 'phraseset_id'])
    op.create_index('idx_party_phrasesets_session', 'party_phrasesets', ['session_id', 'available_for_voting'])
    op.create_index('idx_party_phrasesets_phraseset', 'party_phrasesets', ['phraseset_id'])

def downgrade():
    op.drop_table('party_phrasesets')
    op.drop_table('party_rounds')
    op.drop_table('party_participants')
    op.drop_table('party_sessions')
```

### 10.2 Deployment Steps

#### Phase 1: Backend Deployment

1. **Run migration:**
   ```bash
   alembic upgrade head
   ```

2. **Deploy backend code:**
   ```bash
   git push heroku main
   ```

3. **Verify tables created:**
   ```bash
   heroku pg:psql -c "\dt party_*"
   ```

4. **Test API endpoints:**
   ```bash
   curl -X POST https://quipflip.xyz/api/qf/party/create \
     -H "Authorization: Bearer $TOKEN"
   ```

#### Phase 2: Frontend Deployment

1. **Build frontend:**
   ```bash
   cd qf_frontend
   npm run build
   ```

2. **Deploy to Vercel:**
   ```bash
   vercel --prod
   ```

3. **Test WebSocket connection:**
   - Open browser DevTools
   - Navigate to `/party/create`
   - Verify WebSocket connection in Network tab

#### Phase 3: Monitoring

1. **Watch Heroku logs for errors:**
   ```bash
   heroku logs --tail | grep party
   ```

2. **Monitor database performance:**
   ```sql
   SELECT COUNT(*) FROM party_sessions WHERE created_at > NOW() - INTERVAL '1 hour';
   SELECT COUNT(*) FROM party_participants;
   ```

3. **Check WebSocket connections:**
   ```bash
   heroku ps:scale web=1 --tail
   ```

### 10.3 Rollback Plan

**If issues arise:**

1. **Disable Party Mode in frontend:**
   ```typescript
   // In config.ts
   export const PARTY_MODE_ENABLED = false;
   ```

2. **Hide party buttons:**
   ```typescript
   {PARTY_MODE_ENABLED && (
     <button onClick={handleCreateParty}>Start a Party</button>
   )}
   ```

3. **Rollback migration (if needed):**
   ```bash
   alembic downgrade -1
   ```

---

## 11. Future Enhancements

### 11.1 Phase 1 Launch Features (MVP)

✅ Core functionality documented in this plan:
- Lobby with party code joining
- Coordinated 3-phase gameplay (prompt/copy/vote)
- Real-time WebSocket synchronization
- Match results with rankings and awards

### 11.2 Phase 2 Enhancements (Post-MVP)

**Private Parties:**
- Password-protected sessions
- Invite-only mode
- Friend list integration

**Customization:**
- Configurable prompts_per_player (1-3)
- Configurable copies_per_player (1-4)
- Configurable votes_per_player (2-5)
- Custom time limits per phase
- Custom round timers

**Spectator Mode:**
- Allow late joiners to spectate
- "Join next game" queue
- Live spectator chat

**Advanced Scoring:**
- Streak bonuses (consecutive correct votes)
- Combo multipliers (fooling multiple voters with same copy)
- MVP award (highest overall score)
- Comeback Player award (biggest turnaround)

### 11.3 Phase 3 Advanced Features

**Tournament Mode:**
- Multi-session tournaments
- Bracket generation
- Persistent tournament state
- Champion tracking

**Matchmaking:**
- Skill-based matchmaking
- Quick match queue
- ELO rating system
- Ranked party mode

**Social Features:**
- Party chat during rounds
- Emoji reactions to phrases
- "Favorite phrase" voting
- Post-game highlight reel

**Analytics:**
- Party history
- Personal party stats
- Leaderboards (party-specific)
- Achievement badges

### 11.4 Technical Improvements

**Performance:**
- Redis caching for session state
- Database connection pooling
- WebSocket message compression
- Optimistic UI updates

**Scalability:**
- Horizontal scaling (multiple Heroku dynos)
- Redis pub/sub for cross-dyno WebSocket sync
- Distributed session management
- Auto-scaling based on active sessions

**Reliability:**
- Automatic reconnection on disconnect
- Session recovery after crash
- Timeout handling for inactive players
- Graceful degradation when WebSocket fails

**Observability:**
- Party Mode metrics dashboard
- Session duration tracking
- Phase completion rates
- Error rate monitoring
- WebSocket connection health

---

## 12. Open Questions & Decisions

### 12.1 Resolved Decisions

✅ **Use existing Round/Phraseset/Vote infrastructure**
- Minimizes code duplication
- Ensures consistent game mechanics
- All coins are real and affect global balances

✅ **WebSocket for real-time sync**
- Similar pattern to existing NotificationConnectionManager
- Proven technology stack
- Handles disconnect/reconnect gracefully

✅ **Session-local scoring aggregation**
- Simple SELECT queries with time filters
- No new balance tables needed
- Results are derived, not stored

### 12.2 Questions for Product Review

❓ **Should we allow solo Party Mode?**
- Current plan: min_players = 3
- Alternative: Allow 1-2 player parties for testing/practice
- **Recommendation:** Keep min=3, add "Practice Party" mode later

❓ **What happens if a player disconnects mid-game?**
- Option A: Allow rejoin with session recovery
- Option B: Mark as disconnected, continue without them
- Option C: End session, refund all players
- **Recommendation:** Option B (continue without them, they can rejoin)

❓ **Should we support cross-device party play?**
- Current plan: Yes (session tied to player_id, not device)
- Implication: Player can join from phone, rejoin from desktop
- **Recommendation:** Support this in MVP

❓ **Maximum session duration?**
- What if players abandon mid-session?
- Suggested: 2-hour session timeout
- After timeout: Mark as ABANDONED, refund remaining rounds
- **Recommendation:** Implement 2-hour timeout

❓ **AI backfill for missing players?**
- If player disconnects, should AI complete their rounds?
- Current plan: No AI in Party Mode MVP
- Future: Add "AI assistant" mode
- **Recommendation:** No AI in MVP, add in Phase 2

### 12.3 Technical Debt to Address

⚠️ **Session cleanup job needed**
- Abandoned sessions need periodic cleanup
- Mark as COMPLETED after 2 hours of inactivity
- Delete OPEN sessions older than 24 hours
- **Action:** Add cleanup job to existing cleanup_service.py

⚠️ **Rate limiting for party creation**
- Prevent party code spam
- Limit: 5 party creations per player per hour
- **Action:** Add rate limit middleware

⚠️ **Party code collision handling**
- 8-char alphanumeric = 2.8 trillion combinations
- Collision probability low but nonzero
- **Action:** Retry up to 3 times on unique constraint violation

---

## Appendix A: Party Code Generation

```python
import random
import string

def generate_party_code(length: int = 8) -> str:
    """Generate a unique alphanumeric party code.

    Format: ABCD1234 (uppercase letters + numbers)
    Excludes ambiguous characters: 0, O, I, 1, L
    """
    chars = string.ascii_uppercase.replace('O', '').replace('I', '').replace('L', '')
    digits = string.digits.replace('0', '').replace('1', '')

    # Generate 4 letters + 4 digits
    letters = ''.join(random.choices(chars, k=4))
    numbers = ''.join(random.choices(digits, k=4))

    return letters + numbers

async def generate_unique_party_code(db: AsyncSession) -> str:
    """Generate party code and ensure uniqueness."""
    max_attempts = 3
    for attempt in range(max_attempts):
        code = generate_party_code()
        existing = await db.execute(
            select(PartySession).where(PartySession.party_code == code)
        )
        if not existing.scalar_one_or_none():
            return code

    raise PartyCodeGenerationError("Failed to generate unique party code")
```

---

## Appendix B: Session Progress Calculation

```python
async def get_session_progress(session_id: UUID, db: AsyncSession) -> dict:
    """Calculate session-wide progress metrics."""
    session = await db.get(PartySession, session_id)
    participants = await db.execute(
        select(PartyParticipant).where(PartyParticipant.session_id == session_id)
    )
    participants = participants.scalars().all()

    if session.current_phase == "PROMPT":
        required = session.prompts_per_player
        completed = sum(1 for p in participants if p.prompts_submitted >= required)
    elif session.current_phase == "COPY":
        required = session.copies_per_player
        completed = sum(1 for p in participants if p.copies_submitted >= required)
    elif session.current_phase == "VOTE":
        required = session.votes_per_player
        completed = sum(1 for p in participants if p.votes_submitted >= required)
    else:
        required = 0
        completed = 0

    return {
        "players_done": completed,
        "total_players": len(participants),
        "progress_percentage": (completed / len(participants) * 100) if participants else 0,
        "can_advance": completed == len(participants)
    }
```

---

## Appendix C: WebSocket Connection Example

```typescript
// Frontend WebSocket connection
class PartyWebSocketClient {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private token: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor(sessionId: string, token: string) {
    this.sessionId = sessionId;
    this.token = token;
  }

  connect(onMessage: (message: any) => void) {
    const wsUrl = `wss://quipflip-backend.herokuapp.com/qf/party/${this.sessionId}/ws?token=${this.token}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('🔌 Party WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('📨 Party message received:', message);
      onMessage(message);
    };

    this.ws.onerror = (error) => {
      console.error('❌ Party WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('🔌 Party WebSocket disconnected');
      this.attemptReconnect(onMessage);
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private attemptReconnect(onMessage: (message: any) => void) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

      console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

      setTimeout(() => {
        this.connect(onMessage);
      }, delay);
    } else {
      console.error('❌ Max reconnection attempts reached');
    }
  }
}
```

---

## Summary

This implementation plan provides a complete roadmap for building Party Mode in Quipflip. Key highlights:

✅ **Reuses existing infrastructure** - No duplication of core game logic
✅ **Minimal new tables** - 4 tables for session coordination
✅ **WebSocket real-time sync** - Proven pattern from existing features
✅ **All coins are real** - Integrates seamlessly with economy
✅ **Session-local scoring** - Derived metrics, no separate balances
✅ **Comprehensive testing** - Unit, integration, E2E coverage
✅ **Clear deployment plan** - Phased rollout with rollback strategy
✅ **Future-ready** - Designed for extensibility

**Estimated Development Time:**
- Backend: 2-3 weeks
- Frontend: 2-3 weeks
- Testing: 1 week
- **Total: 5-7 weeks**

**Next Steps:**
1. Review and approve this plan
2. Create GitHub issues from testing checklist
3. Set up project board for tracking
4. Begin backend implementation (data models first)
5. Develop frontend in parallel (mock API initially)
6. Integration testing with real backend
7. Deploy to staging for QA
8. Production launch 🎉
