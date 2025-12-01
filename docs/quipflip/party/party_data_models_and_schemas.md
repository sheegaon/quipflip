# Party Mode Data Models & Schemas

This document describes:

* The **4 SQLAlchemy data models** that back Party Mode:

  * `PartySession`
  * `PartyParticipant`
  * `PartyRound`
  * `PartyPhraseset`
* The **Pydantic schemas** in `backend/schemas/party.py` used by the Party Mode API.

Party Mode is a wrapper around the core Quipflip entities (`QFPlayer`, `Round`, `Phraseset`), adding session-level orchestration (lobby → prompt → copy → vote → results) and per-match stats.

---

## 1. SQLAlchemy Models (database tables)

All four models use `get_uuid_column()` for UUID primary keys and foreign keys, and inherit from `backend.database.Base`.

### 1.1 `PartySession`

**File:** `backend/models/party_session.py`
**Table:** `party_sessions`

Represents a single Party Mode match (i.e., one group session joined by multiple players).

**Columns**

* `session_id` (UUID, PK)

  * Primary key for the party session.
* `party_code` (string(8), unique, not null)

  * 8-character join code shared with players.
* `host_player_id` (UUID, FK → `qf_players.player_id`, not null, on delete CASCADE)

  * The `QFPlayer` who created/hosts this party session.

**Configuration**

* `min_players` (integer, not null, default `6`)

  * Minimum players required to start the session.
* `max_players` (integer, not null, default `9`)

  * Maximum number of players allowed in the session.
* `prompts_per_player` (integer, not null, default `1`)

  * How many prompt rounds each player will get.
* `copies_per_player` (integer, not null, default `2`)

  * How many copy rounds each player will get.
* `votes_per_player` (integer, not null, default `3`)

  * How many votes each player will be able to cast.

**Phase tracking**

* `current_phase` (string(20), not null, default `'LOBBY'`)

  * High-level phase of the party:

    * `'LOBBY'` – players joining, host configuring.
    * `'PROMPT'` – prompt rounds active.
    * `'COPY'` – copy rounds active.
    * `'VOTE'` – vote rounds active.
    * `'RESULTS'` – results being shown.
    * `'COMPLETED'` – fully finished.
* `phase_started_at` (timestamp with timezone, nullable)

  * When the current phase began.
* `phase_expires_at` (timestamp with timezone, nullable)

  * When the current phase is scheduled to expire (used for timers / timeouts).

**Status**

* `status` (string(20), not null, default `'OPEN'`)

  * Overall lifecycle of the session:

    * `'OPEN'` – in lobby, joinable.
    * `'IN_PROGRESS'` – actively running (prompt/copy/vote).
    * `'COMPLETED'` – session finished normally.
    * `'ABANDONED'` – session effectively dead (no more activity / host drops).
* `locked_at` (timestamp with timezone, nullable)

  * When the session was “locked” (e.g., no new joiners once game starts).

**Timestamps**

* `created_at` (timestamp with timezone, not null, default `datetime.now(UTC)`)

  * When the session record was created.
* `started_at` (timestamp with timezone, nullable)

  * When the game actually started (transition out of `LOBBY`).
* `completed_at` (timestamp with timezone, nullable)

  * When the game reached `COMPLETED`/`RESULTS` and was finalized.

**Relationships**

* `host_player = relationship("QFPlayer", foreign_keys=[host_player_id])`

  * The host `QFPlayer` object.
* `participants = relationship("PartyParticipant", back_populates="session", cascade="all, delete-orphan")`

  * All party participants (human + AI) attached to this session.
* `party_rounds = relationship("PartyRound", back_populates="session", cascade="all, delete-orphan")`

  * Link objects tying the session to underlying `Round` records.
* `party_phrasesets = relationship("PartyPhraseset", back_populates="session", cascade="all, delete-orphan")`

  * Link objects tying the session to the `Phraseset` records used for voting.

---

### 1.2 `PartyParticipant`

**File:** `backend/models/party_participant.py`
**Table:** `party_participants`

Represents a single player’s participation inside a specific `PartySession` (including AI players). Tracks status, connection state, and per-phase progress.

**Columns**

* `participant_id` (UUID, PK)

  * Primary key for this participant record.
* `session_id` (UUID, FK → `party_sessions.session_id`, not null, CASCADE)

  * The `PartySession` this participant belongs to.
* `player_id` (UUID, FK → `qf_players.player_id`, not null, CASCADE)

  * Underlying core `QFPlayer` record.

**Status**

* `status` (string(20), not null, default `'JOINED'`)

  * High-level state of this participant relative to the party:

    * `'JOINED'` – connected but not ready.
    * `'READY'` – marked ready for the next phase.
    * `'ACTIVE'` – actively playing in the current phase.
    * `'COMPLETED'` – finished their participation.
    * `'DISCONNECTED'` – lost connection / dropped.
* `is_host` (boolean, not null, default `False`)

  * Flag for whether this participant is the host for this session.

**Progress tracking**

* `prompts_submitted` (integer, not null, default `0`)

  * Number of prompt rounds this participant has successfully submitted.
* `copies_submitted` (integer, not null, default `0`)

  * Number of copy rounds this participant has submitted.
* `votes_submitted` (integer, not null, default `0`)

  * Number of votes cast by this participant.

**Timestamps**

* `joined_at` (timestamp with timezone, not null, default `datetime.now(UTC)`)

  * When the participant joined the party.
* `ready_at` (timestamp with timezone, nullable)

  * When the participant last marked themselves as ready.
* `last_activity_at` (timestamp with timezone, not null, default `datetime.now(UTC)`)

  * Last time this participant did anything (ping, submit, etc.). Useful for timeouts.
* `disconnected_at` (timestamp with timezone, nullable)

  * When they were detected as disconnected, if ever.

**Connection tracking**

* `connection_status` (string(20), not null, default `'connected'`)

  * Low-level connection state:

    * `'connected'` – currently reachable.
    * `'disconnected'` – currently offline / unresponsive.

**Constraints**

* `UniqueConstraint("session_id", "player_id", name="uq_party_participants_session_player")`

  * A given `QFPlayer` can only appear once per `PartySession`.

**Relationships**

* `session = relationship("PartySession", back_populates="participants")`

  * Owning session.
* `player = relationship("QFPlayer")`

  * Underlying player record.
* `party_rounds = relationship("PartyRound", back_populates="participant", cascade="all, delete-orphan")`

  * All `PartyRound` links corresponding to rounds this participant played.

---

### 1.3 `PartyRound`

**File:** `backend/models/party_round.py`
**Table:** `party_rounds`

Links a core `Round` record into a `PartySession` context, tagged with round type and party phase. This lets you reuse normal Quipflip rounds while tracking them per-party and per-participant.

**Columns**

* `party_round_id` (UUID, PK)

  * Primary key for this link.
* `session_id` (UUID, FK → `party_sessions.session_id`, not null, CASCADE)

  * Party session this round belongs to.
* `round_id` (UUID, FK → `qf_rounds.round_id`, not null, CASCADE)

  * Underlying Quipflip `Round` object.
* `participant_id` (UUID, FK → `party_participants.participant_id`, not null, CASCADE)

  * Participant for whom this round is being played (e.g., whose prompt / copy / votes are being tracked).

**Classification**

* `round_type` (string(10), not null)

  * Logical type of the round:

    * `'prompt'`
    * `'copy'`
    * `'vote'`
* `phase` (string(20), not null)

  * Which party phase this round belongs to:

    * `'PROMPT'`
    * `'COPY'`
    * `'VOTE'`
  * Lets you distinguish “this is a prompt round, played during the PROMPT phase” etc.

**Timestamps**

* `created_at` (timestamp with timezone, not null, default `datetime.now(UTC)`)

  * When this link record was created.

**Constraints**

* `UniqueConstraint("session_id", "round_id", name="uq_party_rounds_session_round")`

  * A given core `Round` can be attached only once per `PartySession`.

**Relationships**

* `session = relationship("PartySession", back_populates="party_rounds")`

  * Owning party session.
* `round = relationship("Round")`

  * Underlying `Round` domain object.
* `participant = relationship("PartyParticipant", back_populates="party_rounds")`

  * Participant that played this round.

---

### 1.4 `PartyPhraseset`

**File:** `backend/models/party_phraseset.py`
**Table:** `party_phrasesets`

Links `Phraseset` records into a party session for scoped voting and results summary.

**Columns**

* `party_phraseset_id` (UUID, PK)

  * Primary key for the link record.
* `session_id` (UUID, FK → `party_sessions.session_id`, not null, CASCADE)

  * Party session this phraseset is associated with.
* `phraseset_id` (UUID, FK → `qf_phrasesets.phraseset_id`, not null, CASCADE)

  * Underlying core `Phraseset` object.

**Metadata**

* `created_in_phase` (string(20), not null)

  * Phase in which this phraseset was created (typically `'COPY'`).
  * Lets you scope phrasesets to their origin phase for statistics or filtering.
* `available_for_voting` (boolean, not null, default `False`)

  * Whether this phraseset is currently available to show up in party voting.

**Timestamps**

* `created_at` (timestamp with timezone, not null, default `datetime.now(UTC)`)

  * When this link was created.

**Constraints**

* `UniqueConstraint("session_id", "phraseset_id", name="uq_party_phrasesets_session_phraseset")`

  * A given `Phraseset` can appear only once per party session.

**Relationships**

* `session = relationship("PartySession", back_populates="party_phrasesets")`

  * Owning party session.
* `phraseset = relationship("Phraseset")`

  * Underlying `Phraseset` record.

---

## 2. Pydantic Party Schemas (`backend/schemas/party.py`)

These schemas define the API surface for Party Mode. They’re used as request bodies, response envelopes, and internal DTOs for the party router.

All schemas inherit from either:

* `BaseModel` (bare Pydantic, for request bodies)
* `BaseSchema` (your project’s base schema, used for responses)

---

### 2.1 Request Schemas

#### 2.1.1 `CreatePartySessionRequest`

```python
class CreatePartySessionRequest(BaseModel):
    """Request to create a new party session."""
    min_players: int = Field(default=6, ge=2, le=9, description="Minimum players to start")
    max_players: int = Field(default=9, ge=2, le=9, description="Maximum players allowed")
    prompts_per_player: int = Field(default=1, ge=1, le=3, description="Prompts per player")
    copies_per_player: int = Field(default=2, ge=1, le=4, description="Copies per player")
    votes_per_player: int = Field(default=3, ge=2, le=5, description="Votes per player")
```

* Mirrors the config portion of `PartySession`.
* Enforces reasonable bounds so a host can’t create insane configurations.

#### 2.1.2 `JoinPartySessionRequest`

```python
class JoinPartySessionRequest(BaseModel):
    """Request to join an existing party session."""
    party_code: str = Field(..., min_length=8, max_length=8, description="8-character party code")
```

* A player joins a party by `party_code` only.
* The backend resolves this to a `PartySession` and creates a `PartyParticipant`.

#### 2.1.3 `SubmitPartyRoundRequest`

```python
class SubmitPartyRoundRequest(BaseModel):
    """Request to submit a party round."""
    phrase: str = Field(..., min_length=2, max_length=100, description="Submitted phrase")
```

* Used for submitting user text for a party round (prompt/copy/vote payload).
* Subject to length constraints.

---

### 2.2 Core Participant & Session Responses

These are the workhorse DTOs, used across multiple endpoints.

#### 2.2.1 `PartyParticipantResponse`

```python
class PartyParticipantResponse(BaseSchema):
    """Participant information in a party session."""
    participant_id: str
    player_id: str
    username: str
    is_ai: bool
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
```

Represents a participant in API responses:

* Includes identity, AI flag, host flag, and current `status`.
* Progress counters (`*_submitted` + `*_required`) let the UI compute completion and gating.

#### 2.2.2 `PartySessionProgressResponse`

```python
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
```

Aggregated progress metrics at the **session** level:

* Total vs. required counts per phase.
* How many players are ready vs total players.

#### 2.2.3 `PartySessionResponse`

```python
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
```

Full representation of a party session:

* Mirrors the `PartySession` DB model plus:

  * Denormalized participant list and progress.
  * Enough timestamps to build phase/overall timelines.

#### 2.2.4 `CreatePartySessionResponse`

```python
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
```

Returned right after **session creation**:

* Emphasis on `party_code` (so host can share it) and initial lobby info.
* Participants list will initially contain just the host (plus any auto-created AI if you add that in future).

#### 2.2.5 `JoinPartySessionResponse`

```python
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
```

Returned when a player joins via `party_code`:

* Contains enough to render the lobby and to know how “full” the session is.
* `participant_count` saves recalculating on the client.

#### 2.2.6 `PartySessionStatusResponse`

```python
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
```

Essentially the same shape as `PartySessionResponse`, typically used for polling/status endpoints.

---

### 2.3 Lobby & Ready / Administrative Responses

#### 2.3.1 `MarkReadyResponse`

```python
class MarkReadyResponse(BaseSchema):
    """Response after marking ready."""
    participant_id: str
    status: str
    session: Dict
        # ready_count, total_count, can_start
```

* Returned when a participant toggles ready.
* `session` is a small dict with at least:

  * `ready_count`
  * `total_count`
  * `can_start` (bool)

#### 2.3.2 `AddAIPlayerResponse`

```python
class AddAIPlayerResponse(BaseSchema):
    """Response after adding an AI player."""
    participant_id: str
    player_id: str
    username: str
    is_ai: bool
```

* Confirms creation of an AI participant, with its assigned `player_id` + display name.

#### 2.3.3 `PartyPingResponse`

```python
class PartyPingResponse(BaseSchema):
    """Response after pinging all party participants."""
    success: bool
    message: str
```

* Used by any “ping everyone / keepalive” type endpoint.

#### 2.3.4 `StartPartySessionResponse`

```python
class StartPartySessionResponse(BaseSchema):
    """Response after starting a party session."""
    session_id: str
    status: str
    current_phase: str
    phase_started_at: datetime
    locked_at: datetime
    participants: List[PartyParticipantResponse]
```

* Returned when host transitions from `LOBBY` to the first game phase.
* `locked_at` indicates that no new players can join.

---

### 2.4 Round Lifecycle Responses

These handle prompt/copy/vote start & submit.

#### 2.4.1 `StartPartyRoundResponse`

```python
class StartPartyRoundResponse(BaseSchema):
    """Response after starting a party round."""
    round_id: str
    party_round_id: str
    round_type: str
    expires_at: datetime
    cost: int
    prompt_text: Optional[str] = None
    original_phrase: Optional[str] = None
    phraseset_id: Optional[str] = None
    phrases: Optional[List[str]] = None
    status: Optional[str] = None
    session_progress: Dict
    party_context: Optional[Dict] = None
```

Used when the system assigns a new party round to a player:

* `round_id` / `party_round_id` tie back to `Round` + `PartyRound`.
* `round_type` is `prompt` / `copy` / `vote`.
* `expires_at` & `cost` used by the client for timer + coin display.
* Optional fields are filled depending on round type:

  * `prompt_text`, `original_phrase`, `phraseset_id`, `phrases`, etc.
* `session_progress` is a small dict with up-to-date progress metrics.
* `party_context` is a grab-bag for any extra context you want to inject.

#### 2.4.2 `SubmitPartyRoundResponse`

```python
class SubmitPartyRoundResponse(BaseSchema):
    """Response after submitting a party round."""
    success: bool
    phrase: str
    round_type: str
    session_progress: Dict
    phase_transition: Optional[Dict] = None
```

* Confirms server-side acceptance of a round submission.
* `session_progress` gives updated stats.
* `phase_transition`, when present, describes an automatic phase change (e.g. `'COPY' → 'VOTE'`).

---

### 2.5 Stats & Results

These power post-game screens and analytics.

#### 2.5.1 `PartyPlayerStatsResponse`

```python
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
```

Per-player aggregates for a single party session:

* Coin-based metrics (`spent`, `earned`, `net`).
* Voting metrics, including “fooled others” vs. correct guesses.
* Participation metrics (how much they actually played).

#### 2.5.2 `PartyAwardResponse`

```python
class PartyAwardResponse(BaseSchema):
    """Award winner information."""
    player_id: str
    username: str
    metric_value: float
```

Represents a single award (e.g., “Best Copycat”, “Most Fooled”).

* `metric_value` is whatever metric the award is based on (votes, accuracy, etc.).

#### 2.5.3 `PartyPhrasesetSummaryResponse`

```python
class PartyPhrasesetSummaryResponse(BaseSchema):
    """Summary of a phraseset in the party match."""
    phraseset_id: str
    prompt_text: str
    original_phrase: str
    vote_count: int
    original_player: str
    most_votes: str
    votes_breakdown: Dict[str, int]
```

Summary of a `Phraseset` and how it performed:

* `original_player` – who wrote the original.
* `most_votes` – which phrase got the most votes.
* `votes_breakdown` – mapping of phrase → vote count.

#### 2.5.4 `PartyResultsResponse`

```python
class PartyResultsResponse(BaseSchema):
    """Complete party match results."""
    session_id: str
    party_code: str
    completed_at: Optional[datetime]
    rankings: List[PartyPlayerStatsResponse]
    awards: Dict[str, PartyAwardResponse]
    phrasesets_summary: List[PartyPhrasesetSummaryResponse]
```

End-of-game payload:

* Combined view of `rankings`, `awards`, and per-phraseset summaries.
* Used to build the results screen without additional API calls.

---

### 2.6 Lobby Listing

Used to list active/joinable party sessions.

#### 2.6.1 `PartyListItemResponse`

```python
class PartyListItemResponse(BaseSchema):
    """Information about a joinable party session."""
    session_id: str
    host_username: str
    participant_count: int
    min_players: int
    max_players: int
    created_at: datetime
    is_full: bool
```

One row in a “join a party” list:

* `is_full` tells the client whether to disable the “Join” button.
* `participant_count` vs `max_players` used for occupancy UI.

#### 2.6.2 `PartyListResponse`

```python
class PartyListResponse(BaseSchema):
    """List of active/joinable party sessions."""
    parties: List[PartyListItemResponse]
    total_count: int
```

* Wrapper for a paged or filtered list of joinable sessions.
