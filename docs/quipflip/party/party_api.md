# Party Mode API

Party Mode lets a group of players (human + optional AI) play a structured multi-phase match:

1. **LOBBY** – players join, mark ready, host can add AI/ping.
2. **PROMPT** – everyone writes original phrases.
3. **COPY** – everyone copies other people’s phrases.
4. **VOTE** – everyone votes on phrases.
5. **RESULTS/COMPLETED** – ranking, awards, breakdown.

All endpoints require an authenticated `QFPlayer` via the standard access token (`get_current_player`) unless otherwise noted. 

Schemas referenced below are the Pydantic models from `backend/schemas/party.py` which you already have documented.

---

## 1. Session Discovery & Creation

### 1.1 List active parties

**HTTP**: `GET /party/list`
**Auth**: Required

Returns all **joinable** sessions:

* `status == OPEN` (lobby)
* `participant_count < max_players`

**Response**

* `200 OK` – `PartyListResponse`

  * `parties: List[PartyListItemResponse]` – each item has `session_id`, `host_username`, `participant_count`, `min_players`, `max_players`, `created_at`, `is_full`.
  * `total_count: int`

**Errors**

* `401 Unauthorized` – invalid/missing token.
* `500 Internal Server Error` – `"Failed to list parties"`.

---

### 1.2 Create a new party session

**HTTP**: `POST /party/create`
**Auth**: Required (caller becomes host)

**Request body**

* `CreatePartySessionRequest`:

  * `min_players`, `max_players`
  * `prompts_per_player`, `copies_per_player`, `votes_per_player`

**Behavior**

* Creates a new `PartySession` with the player as `host_player_id`.
* Creates a `PartyParticipant` row for the host.
* Returns initial session status from `PartySessionService.get_session_status`.

**Response**

* `200 OK` – `CreatePartySessionResponse`:

  * Identifiers: `session_id`, `party_code`, `host_player_id`
  * State: `status`, `current_phase` (starts as `LOBBY`)
  * Timestamps: `created_at`
  * Config: `min_players`, `max_players`
  * `participants: List[PartyParticipantResponse]` (initially just the host)

**Errors**

* `401 Unauthorized`
* `409 Conflict` – `"already_in_another_session"` if the player is already in another party session.
* `500 Internal Server Error` – `"Failed to create party session"`.

---

### 1.3 Join party by code

**HTTP**: `POST /party/join`
**Auth**: Required

**Request body**

* `JoinPartySessionRequest`:

  * `party_code: str` (exact 8 characters)

**Behavior**

* Looks up session by `party_code`.
* If player is not already in the session, adds them as a `PartyParticipant`.
* Emits `ws_manager.notify_player_joined` to the party WebSocket subscribers. 

**Response**

* `200 OK` – `JoinPartySessionResponse`:

  * `session_id`, `party_code`, `status`, `current_phase`
  * `participants: List[PartyParticipantResponse]`
  * `participant_count: int`
  * `min_players`, `max_players`

**Errors**

* `404 Not Found`

  * `"Party session '<CODE>' not found"` (direct lookup failure), or
  * `"Party session not found"` (thrown by service).
* `400 Bad Request`

  * `"Session has already started"`
  * `"Session is full"`
* `409 Conflict`

  * `"Already in this session"`
  * `"already_in_another_session"`
* `500 Internal Server Error` – `"Failed to join party session"`.

---

### 1.4 Join party by session ID

**HTTP**: `POST /party/{session_id}/join`
**Auth**: Required

Same semantics as **join by code**, but you supply `session_id` directly (used when joining from a party list).

**Path params**

* `session_id: UUID`

**Response**

* `200 OK` – `JoinPartySessionResponse` (same as above)

**Errors**

* `404 Not Found` – `"Party session not found"`
* `400 Bad Request`

  * `"Session has already started"`
  * `"Session is full"`
* `409 Conflict`

  * `"Already in this session"`
  * `"already_in_another_session"`
* `500 Internal Server Error` – `"Failed to join party session"`.

---

### 1.5 Leave party (lobby only)

**HTTP**: `POST /party/{session_id}/leave`
**Auth**: Required

**Path params**

* `session_id: UUID`

**Behavior**

* Only allowed **before** the session starts.
* Removes current player’s `PartyParticipant` row.
* If this was the **last participant**, the session is deleted.
* Broadcasts `ws_manager.notify_player_left` when the session survives. 

**Response**

* `200 OK` – JSON:

  * `success: true`
  * `message: "Left party session"`
  * `session_deleted: bool` – whether the session itself was deleted.

**Errors**

* `404 Not Found`

  * `"Session not found"` if session missing.
  * `"Not in this session"` if player was never a participant.
* `400 Bad Request` – `"Cannot leave session that has started"`
* `500 Internal Server Error` – `"Failed to leave session"`.

---

## 2. Lobby Management (Ready, AI, Ping, Start)

### 2.1 Mark player ready

**HTTP**: `POST /party/{session_id}/ready`
**Auth**: Required

**Path params**

* `session_id: UUID`

**Behavior**

* Marks the caller’s `PartyParticipant` status as `READY` in the lobby.
* Recomputes number of ready players.
* Emits `ws_manager.notify_player_ready` with `ready_count` and `total_count`. 

**Response**

* `200 OK` – `MarkReadyResponse`:

  * `participant_id`
  * `status` (participant status, e.g. `READY`)
  * `session`:

    * `ready_count`
    * `total_count`
    * `can_start` – `ready_count >= min_players`

**Errors**

* `404 Not Found` – `"Session not found"`
* `400 Bad Request` – `"Session has already started"`
* `500 Internal Server Error` – `"Failed to mark ready"`.

---

### 2.2 Add an AI player (host only)

**HTTP**: `POST /party/{session_id}/add-ai`
**Auth**: Required (host only)

**Path params**

* `session_id: UUID`

**Behavior**

* Host-only, lobby-only.
* Creates an AI `QFPlayer` (according to your `PartySessionService.add_ai_player` logic) and attaches it as a `PartyParticipant`.
* Broadcasts `ws_manager.notify_player_joined` with updated count. 

**Response**

* `200 OK` – `AddAIPlayerResponse`:

  * `participant_id`
  * `player_id`
  * `username`
  * `is_ai` (always `true` here)

**Errors**

* `404 Not Found` – `"Session not found"`
* `403 Forbidden` – `"Only the host can add AI players"`
* `400 Bad Request`

  * `"Cannot add AI players after session has started"`
  * `"Session is full"`
* `500 Internal Server Error` – `"Failed to add AI player"`.

---

### 2.3 Ping all players (host only)

**HTTP**: `POST /party/{session_id}/ping`
**Auth**: Required (host only)

**Path params**

* `session_id: UUID`

**Behavior**

* Host-only.
* Builds a `PingWebSocketMessage` with:

  * `from_username`
  * `timestamp` (UTC ISO string)
  * `join_url` – `"/party/{session_id}"`
* For each **non-host, non-AI** participant, sends this message via the global `NotificationConnectionManager` (not the party-specific WS).
* Emits `ws_manager.notify_host_ping` into the party WS for live feedback. 

**Response**

* `200 OK` – `PartyPingResponse`:

  * `success: true`
  * `message: "Ping sent to all players"`

**Errors**

* `404 Not Found` – `"Session not found"`
* `403 Forbidden` – `"Only the host can ping players"`
* `500 Internal Server Error` – `"Failed to send ping"`.

---

### 2.4 Process AI submissions (host only)

**HTTP**: `POST /party/{session_id}/process-ai`
**Auth**: Required (host only)

**Path params**

* `session_id: UUID`

**Behavior**

* Host-only.
* Calls `PartyCoordinationService.process_ai_submissions` for the **current phase** with a `TransactionService`.
* Intended for manual kicks or scheduled jobs to ensure AI players keep up.

**Response**

* `200 OK` – JSON:

  * `success: true`
  * `stats: ...` – whatever structure `process_ai_submissions` returns (phase-specific counts, etc.).

**Errors**

* `404 Not Found` – `"Session not found"`
* `403 Forbidden` – `"Only the host can trigger AI submissions"`
* `500 Internal Server Error` – `"Failed to process AI submissions"`.

---

### 2.5 Start party session (host only)

**HTTP**: `POST /party/{session_id}/start`
**Auth**: Required (host only)

**Path params**

* `session_id: UUID`

**Behavior**

* Host-only.
* Transitions session out of lobby via `PartySessionService.start_session`.
* Locks the session against further joins (`locked_at`).
* Emits `ws_manager.notify_session_started` with:

  * `session_id`
  * `current_phase` (usually `PROMPT`)
  * `participant_count`
  * `message` – `"Party started! Everyone write your best original phrase."`
* Synchronously triggers AI submissions for the new phase via `PartyCoordinationService._trigger_ai_submissions_for_new_phase`. Errors here are logged but **do not** abort the session start. 

**Response**

* `200 OK` – `StartPartySessionResponse`:

  * `session_id`
  * `status`
  * `current_phase`
  * `phase_started_at`
  * `locked_at`
  * `participants: List[PartyParticipantResponse]`

**Errors**

* `404 Not Found` – `"Session not found"`
* `403 Forbidden` – `"Only the host can start the session"`
* `400 Bad Request`

  * `"Session has already started"`
  * Error message from `NotEnoughPlayersError` (e.g. “Need at least X players…”).
* `500 Internal Server Error` – `"Failed to start party session"`.

---

## 3. Session Status & Results

### 3.1 Get current session status

**HTTP**: `GET /party/{session_id}/status`
**Auth**: Required

**Path params**

* `session_id: UUID`

**Behavior**

* Calls `PartySessionService.get_session_status(session_id)` and wraps it as `PartySessionStatusResponse`.

**Response**

* `200 OK` – `PartySessionStatusResponse`:

  * Config: `min_players`, `max_players`
  * State: `status`, `current_phase`
  * Timestamps: `created_at`, `started_at`, `completed_at`, `phase_started_at`
  * `participants: List[PartyParticipantResponse]`
  * `progress: PartySessionProgressResponse`

**Errors**

* `404 Not Found` – `"Session not found"`
* `500 Internal Server Error` – `"Failed to get session status"`.

---

### 3.2 Get party results

**HTTP**: `GET /party/{session_id}/results`
**Auth**: Required

**Path params**

* `session_id: UUID`

**Behavior**

* Validates that the session exists and is in `RESULTS` or `COMPLETED` phase. Otherwise fails.
* Calls `PartyScoringService.calculate_session_results(session_id)` and returns it as `PartyResultsResponse`. 

**Response**

* `200 OK` – `PartyResultsResponse`:

  * `session_id`, `party_code`, `completed_at`
  * `rankings: List[PartyPlayerStatsResponse]`
  * `awards: Dict[str, PartyAwardResponse]`
  * `phrasesets_summary: List[PartyPhrasesetSummaryResponse]`

**Errors**

* `404 Not Found` – `"Session not found"`
* `400 Bad Request` – `"Results not available yet (current phase: <PHASE>)"`
* `500 Internal Server Error` – `"Failed to get party results"`.

---

## 4. Starting Party Rounds (Prompt / Copy / Vote)

All three endpoints:

* Require the caller to already be a `PartyParticipant` in the given `session_id`.
* Ensure the session is in the correct `current_phase`.
* Enforce per-player quotas (`prompts_per_player`, `copies_per_player`, `votes_per_player`).
* Enforce coin balance via `TransactionService` and raise `InsufficientBalanceError` if needed.

Each returns a `StartPartyRoundResponse`, with `round_type` set accordingly and `party_context` + `session_progress` to drive your UI.

---

### 4.1 Start a prompt round

**HTTP**: `POST /party/{session_id}/rounds/prompt`
**Auth**: Required

**Path params**

* `session_id: UUID`

**Behavior**

* Calls `PartyCoordinationService.start_party_prompt_round(...)` to create a new prompt `Round` and associated `PartyRound`.
* Counts “active” participants (`status == 'ACTIVE'`) and how many of them have hit their prompt quota.
* Returns the round plus progress info. 

**Response**

* `200 OK` – `StartPartyRoundResponse`:

  * `round_id`
  * `party_round_id`
  * `round_type: "prompt"`
  * `expires_at`
  * `cost`
  * `prompt_text`
  * `status`
  * `session_progress`:

    * `your_prompts_submitted`
    * `prompts_required`
    * `players_done`
    * `total_players`
  * `party_context`:

    * `session_id`
    * `current_phase`
    * `your_progress` – per-player counters for prompts/copies/votes vs required.
    * `session_progress` – `players_ready_for_next_phase`, `total_players`.

**Errors**

* `404 Not Found` – `"Session not found"`
* `400 Bad Request`

  * `WrongPhaseError` message (e.g. trying to start prompt in COPY phase).
  * `AlreadySubmittedError` message (e.g. quota exceeded).
  * `"Insufficient balance"`
* `500 Internal Server Error` – `"Failed to start prompt round"`.

---

### 4.2 Start a copy round

**HTTP**: `POST /party/{session_id}/rounds/copy`
**Auth**: Required

**Path params**

* `session_id: UUID`

**Behavior**

* Calls `PartyCoordinationService.start_party_copy_round(...)`.
* Ensures there are prompts available for copying; otherwise errors.
* Computes active players and how many met their copy quota.

**Response**

* `200 OK` – `StartPartyRoundResponse`:

  * `round_id`
  * `party_round_id`
  * `round_type: "copy"`
  * `expires_at`
  * `cost`
  * `original_phrase` – the phrase to be copied
  * `status`
  * `session_progress`:

    * `your_copies_submitted`
    * `copies_required`
    * `players_done`
    * `total_players`
  * `party_context` – same structure as prompt.

**Errors**

* `404 Not Found` – `"Session not found"`
* `400 Bad Request`

  * `WrongPhaseError` message
  * `AlreadySubmittedError` message
  * `"No prompts available for copying"`
  * `"Insufficient balance"`
* `500 Internal Server Error` – `"Failed to start copy round"`.

---

### 4.3 Start a vote round

**HTTP**: `POST /party/{session_id}/rounds/vote`
**Auth**: Required

**Path params**

* `session_id: UUID`

**Behavior**

* Calls `PartyCoordinationService.start_party_vote_round(...)`.
* Ensures there are phrasesets available for voting.
* Computes active players and who has met their vote quota.

**Response**

* `200 OK` – `StartPartyRoundResponse`:

  * `round_id`
  * `party_round_id`
  * `round_type: "vote"`
  * `expires_at`
  * `cost` – `settings.vote_cost` (may differ from generic round cost).
  * `phraseset_id`
  * `prompt_text`
  * `phrases: List[str]` – shuffled candidate phrases.
  * `status`
  * `session_progress`:

    * `your_votes_submitted`
    * `votes_required`
    * `players_done`
    * `total_players`
  * `party_context` – same structure as others.

**Errors**

* `404 Not Found` – `"Session not found"`
* `400 Bad Request`

  * `WrongPhaseError` message
  * `AlreadySubmittedError` message
  * `"No phrasesets available for voting"`
  * `"Insufficient balance"`
* `500 Internal Server Error` – `"Failed to start vote round"`.

---

### 4.4 Generic submit endpoint (currently *not* used)

**HTTP**: `POST /party/{session_id}/rounds/{round_id}/submit`
**Auth**: Required

**Path params**

* `session_id: UUID`
* `round_id: UUID`

**Request body**

* `SubmitPartyRoundRequest`:

  * `phrase: str`

**Current behavior**

* The function is effectively a stub: it unconditionally raises an HTTP 400 telling clients to use the specific endpoints (prompt/copy/vote). Due to the error being wrapped in a broad `except Exception`, in practice this endpoint ends up returning a 500 `"Failed to submit round"` instead. 

**Practical note**

* Do **not** use this endpoint from the frontend. Always:

  * Start round via `/rounds/prompt|copy|vote`, and
  * Submit using whatever dedicated submission flow you implement (e.g. within those services / separate endpoints you’ll add later).

---

## 5. WebSocket: Real-time Party Updates

### 5.1 Party WebSocket endpoint

**WS**: `GET /party/{session_id}/ws` (WebSocket handshake)
**Auth**: Required (via token query param or cookie)

**Path params**

* `session_id: UUID`

**Query params**

* `token: str` (optional if cookie is set)

  * Access token (same as normal auth) – if missing from both query and cookies, the connection is rejected.
* `context: str` (optional)

  * Arbitrary free-form string handed through to `ws_manager.connect` / `disconnect` (e.g., `"lobby"`, `"round-view"`, etc.).

**Authentication flow**

1. Extract `token` from query or cookie (`settings.access_token_cookie_name`).
2. Validate using `AuthService.decode_access_token` (GameType.QF).
3. Extract `sub` as `player_id`.
4. Verify that this player is **currently a participant** in the specified `session_id`.
5. If any step fails, the websocket is closed early with a warning log. 

**Connection behavior**

* On success, calls:

  ```python
  await ws_manager.connect(session_id, player_id, websocket, db, context=context)
  ```

* Then enters a loop:

  ```python
  while True:
      await websocket.receive_text()
  ```

  Incoming messages are effectively ignored; the loop just keeps the connection alive until the client disconnects.

* On disconnect or error, calls:

  ```python
  await ws_manager.disconnect(session_id, player_id, db, context=context)
  ```

**Server-sent events (via `ws_manager`)**

While the actual payload shapes are defined in `PartyWebSocketManager`, this router triggers the following events:

* `notify_player_joined` – when someone joins (including AI).
* `notify_player_left` – when someone leaves in lobby.
* `notify_player_ready` – when someone toggles ready.
* `notify_session_started` – when host starts the session.
* `notify_host_ping` – when host uses the `/ping` endpoint.

The client should:

* Treat this WS as **read-only** (no meaningful messages sent from client).
* Subscribe once when entering a party session page.
* Update lobby UI, progress meters, etc. based on incoming messages.
* Continue to use REST endpoints for all gameplay transitions (starting rounds, advancing phases) and poll `/party/{session_id}/status` as needed so that the game flow is not gated on WebSocket delivery.
