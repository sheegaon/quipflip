High level:

* **Party mode wraps the existing Quipflip engine** (prompt/copy/vote, phrasesets, scoring, Flipcoin economy) in a multi-round “match” container with lobbies, phases, progress tracking, AI players, WebSockets, and end-of-match stats.
* The main pieces are:

  * **Data models**: `PartySession`, `PartyParticipant`, `PartyRound`, `PartyPhraseset`.
  * **Services**: `PartySessionService`, `PartyCoordinationService`, `PartyScoringService`, `PartyWebSocketManager`.
  * **HTTP API** (`party_api.md`) that wires those into routes like `/party/create`, `/party/{session_id}/start`, `/party/{session_id}/rounds/prompt|copy|vote`, `/party/{session_id}/status`, `/party/{session_id}/results`, plus a party WebSocket endpoint.

Below is the “how they fit together” narrative.

---

## 1. Data layer: what a party session *is*

Party mode adds four main tables on top of the core `Round`, `Phraseset`, `QFTransaction`, etc.:

1. **PartySession** – the match container

   * Fields: `session_id`, `host_player_id`, `party_code`, `status` (`lobby`, `in_progress`, `completed`), `current_phase` (`PROMPT`, `COPY`, `VOTE`, `RESULTS`), `min_players`, `max_players`, per-phase quotas `prompts_per_player`, `copies_per_player`, `votes_per_player`, and timestamps like `started_at`, `completed_at`, `locked_at`.
   * Represents one lobby/match from creation → play → final results.

2. **PartyParticipant** – players in a session

   * Fields: `participant_id`, `session_id`, `player_id`, `username`, `is_host`, `is_ai`, plus counters: `prompts_submitted`, `copies_submitted`, `votes_submitted`.
   * Tracks per-player progress against the per-phase quotas stored on the session.

3. **PartyRound** – links a normal QF *round* into the party context

   * Fields: `party_round_id`, `session_id`, `participant_id`, `round_id` (FK to core `Round`), `round_type` (`prompt`, `copy`, `vote`), `phase` (the party phase when it happened).
   * This is how party mode knows “this specific prompt/copy/vote round belongs to this match and this participant”.

4. **PartyPhraseset** – links a core `Phraseset` (prompt + copies) into the party

   * Fields: `party_phraseset_id`, `session_id`, `phraseset_id`, `created_in_phase`, `available_for_voting` etc.
   * Used for “which phrasesets should party members vote on” and for end-of-match summaries.

**Response models** like `PartySessionStatusResponse`, `PartySessionProgressResponse`, `PartyResultsResponse`, `PartyPlayerStatsResponse`, and `PartyPhrasesetSummaryResponse` are basically read-only views built off these tables plus the core Quipflip tables.

---

## 2. Service responsibilities

### 2.1 PartySessionService – lobby + phase + progress

`PartySessionService` owns all the *session/participant* state:

* **Lobby / membership**

  * Create session, generate join code, enforce min/max players.
  * Join / leave, ensure only one host, mark AI participants, etc. (via `PartyParticipant` rows).

* **Phase control + status**

  * `start_session(session_id, host_player_id)` → flips `status` to `in_progress`, sets `current_phase='PROMPT'`, timestamps `started_at`, and locks the session from new joins.
  * `get_session_status(session_id)` builds `PartySessionStatusResponse` with session meta, participants, and a nested `PartySessionProgressResponse` summarizing how many prompts/copies/votes have been submitted versus required.
  * `can_advance_phase(session_id)` checks whether all non-AI participants hit their per-phase quotas.
  * `advance_phase(session_id)` updates `current_phase` in order PROMPT → COPY → VOTE → RESULTS and sets `completed_at` once done.

* **Per-player progress counters**

  * `increment_participant_progress(session_id, player_id, round_type)` bumps `prompts_submitted`, `copies_submitted`, or `votes_submitted` and returns the updated `PartyParticipant`.

Essentially this is the “source of truth” for lobby membership, phases, and how far along each player is.

---

### 2.2 PartyCoordinationService – glue to the core game engine

`PartyCoordinationService` is where party mode actually *plays Quipflip*.

It does **not** implement game rules itself; instead it:

* Validates the session/phase and per-player quotas using `PartySessionService`.
* Calls into the **core** `RoundService` and `VoteService` (from `QF_API.md`) to create and submit real prompt/copy/vote rounds.
* Uses `PartySessionService.link_round_to_party` and `link_phraseset_to_party` to stitch those core objects back to `PartyRound` / `PartyPhraseset`.
* Updates progress via `increment_participant_progress`.
* Broadcasts progress and phase changes via `PartyWebSocketManager` (see below).

Concretely:

#### Prompt phase

* `start_party_prompt_round(session_id, player, transaction_service)`

  * Checks the session exists and is in `PROMPT` phase.
  * Ensures the player is a `PartyParticipant` and hasn’t exhausted `prompts_per_player`.
  * Calls `round_service.start_prompt_round(...)` to create a normal prompt round.
  * Links that round into `PartyRound` with `round_type='prompt', phase='PROMPT'`.

* `submit_party_prompt(session_id, player, round_id, phrase, transaction_service)`

  * Delegates to `round_service.submit_prompt_phrase(...)`.
  * On success, calls `increment_participant_progress(..., round_type='prompt')`.
  * Calls `ws_manager.notify_player_progress(...)` with per-player and session-level summary.
  * If `can_advance_phase` flips true (everyone done with prompts), calls `advance_phase` and broadcasts a phase transition to `COPY`, then immediately kicks off AI copies via `_trigger_ai_submissions_for_new_phase`.

#### Copy phase

* `start_party_copy_round(session_id, player, transaction_service)`

  * Verifies session exists and `current_phase='COPY'`, and that player is in the session and has remaining copies.
  * Chooses a prompt via `_get_eligible_prompt_for_copy`, which:

    * Prefers prompts created inside this party (`PartyRound` rows) in PROMPT phase, excluding player’s own prompts and ones they already copied.
    * Falls back to the global prompt queue (`QueueService`) but filters out prompts authored by *any* party member, and only uses rounds that are `status='submitted'`.
  * Calls `round_service.start_copy_round` with the chosen `prompt_round_id`, explicitly forcing the round service to honor that specific prompt (and requeue it if it originally came from the global queue and becomes unavailable).
  * Links the new copy round into `PartyRound` (`round_type='copy', phase='COPY'`).

* `submit_party_copy(...)`

  * Delegates to `round_service.submit_copy_phrase(...)`.
  * Increments `copies_submitted` via `increment_participant_progress`.
  * If this submission caused a new `Phraseset` to be constructed (prompt + 2 copies), links that `phraseset_id` to the party via `PartyPhraseset`.
  * Similar to prompts, when `can_advance_phase` becomes true, advances to `VOTE` and triggers AI votes for the new phase. (Same pattern as PROMPT → COPY.)

#### Vote phase

* `_get_eligible_phraseset_for_vote(session_id, player_id)`

  * Fetches `PartyPhraseset` joined to `Phraseset` where `available_for_voting=true` and `Phraseset.status='voting'`.
  * Excludes any phrasesets where this player contributed (prompt or either copy) and any phrasesets they already voted on.
  * Returns an eligible `phraseset_id` or `None`.

* `start_party_vote_round(session_id, player, transaction_service)`

  * Confirms `current_phase='VOTE'` and votes remaining.
  * Finds an eligible phraseset (usually from `PartyPhraseset`), starts a normal QF vote round via `vote_service.start_vote_round(...)`, then binds it into `PartyRound`. (Pattern is analogous to copy.)

* `submit_party_vote(...)`

  * Loads `Round` and `Phraseset`, then calls `vote_service.submit_vote(...)`.
  * Increments `votes_submitted`.
  * Broadcasts `notify_player_progress`.
  * When everyone finishes, `can_advance_phase` → `advance_phase`, broadcasting a final phase transition to `RESULTS`.

#### AI integration

`PartyCoordinationService` also coordinates **AI players**:

* It uses `AIService` (documented in `AI_SERVICE.md`) for AI copies and votes: `generate_copy_phrase` and `generate_vote_choice`.
* `process_ai_submissions(session_id, phase, ...)` loops over AI participants in the session and:

  * In PROMPT: calls the normal prompt start/submit functions (if you allow AI prompts).
  * In COPY: repeatedly calls `start_party_copy_round` + `submit_party_copy` using AI phrases until AI quotas are met or no eligible prompts remain.
  * In VOTE: uses `_get_eligible_phraseset_for_vote` + `submit_party_vote` with AI choices.
* `_trigger_ai_submissions_for_new_phase` is called after phase transitions so AI work keeps pace with humans.

**Net: PartyCoordinationService is the orchestration layer** that makes “party mode” feel like a guided multi-round experience while reusing the exact same QF game rules and economy.

---

### 2.3 PartyScoringService – end-of-match stats and awards

Once a session is in `RESULTS`, `PartyScoringService.calculate_session_results(session_id)` runs the score/report pipeline:

* It pulls:

  * The `PartySession` and its participants.
  * All `PartyRound` and `PartyPhraseset` rows for that session.
  * The underlying `Round`, `Phraseset`, and `QFTransaction` rows so it knows what prompts, copies, votes, and payouts actually happened.

* It then builds:

  * `rankings`: ordered list of players with composite scores (you choose what you consider “score” – net earnings, fooled votes, etc.).
  * `awards`: a map from `player_id` to `PartyPlayerStatsResponse` (prompts, copies, votes, coins spent/earned, “fooled players”, “spotted originals”, etc.).
  * `phrasesets_summary`: list of `PartyPhrasesetSummaryResponse` objects showing each phraseset, the original/copies, vote distribution, and which party participants contributed.

This structure is what backs `GET /party/{session_id}/results`.

---

### 2.4 PartyWebSocketManager – real-time updates

`PartyWebSocketManager` owns WebSocket connections for party sessions:

* The router exposes a WS endpoint (e.g. `/party/{session_id}/ws`) that:

  * Authenticates the player.
  * Attaches the connection to `PartyWebSocketManager` for that `session_id`.

* The manager exposes methods like:

  * `notify_player_joined`, `notify_player_left`, `notify_player_ready`, `notify_host_ping`.
  * `notify_session_started`, `notify_session_updated`, `notify_session_completed`.
  * `notify_phase_transition` for PROMPT→COPY→VOTE→RESULTS.
  * `notify_player_progress` used by `PartyCoordinationService` to send per-player progress and session summary on each submission.

The HTTP routes call into the services, and **the services call `PartyWebSocketManager`** so that the frontend can treat the WebSocket as a read-only feed of lobby and progress events.

---

## 3. HTTP API → services → core engine: end-to-end flow

Putting it all together, a typical match looks like this:

### 3.1 Lobby

1. **List sessions** – `GET /party/sessions`

   * Router calls `PartySessionService.list_open_sessions(...)` and returns a simplified list of `PartySession` rows (codes, host username, player counts).

2. **Create session** – `POST /party/create`

   * Router passes host player to `PartySessionService.create_session(...)`.
   * Service creates `PartySession` + host `PartyParticipant` with `is_host=True`.

3. **Join / leave** – `POST /party/join`, `POST /party/leave`

   * On join, service ensures capacity, adds `PartyParticipant`, returns updated session/participants; router calls `ws_manager.notify_player_joined`.
   * On leave, service updates or deletes participant; router calls `notify_player_left`.

4. **Ready toggles, AI players, pings**

   * `POST /party/{session_id}/add-ai` uses `PartySessionService.add_ai_participant(...)`.
   * `POST /party/{session_id}/ready` toggles a ready flag; router calls `notify_player_ready`.
   * `POST /party/{session_id}/ping` pushes a `notify_host_ping` WS event for people to re-focus.

### 3.2 Session start + phase progression

5. **Start match** – `POST /party/{session_id}/start`

   * Validates host, min players, etc.
   * `PartySessionService.start_session` sets `status='in_progress'`, `current_phase='PROMPT'`.
   * Router calls `ws_manager.notify_session_started`.
   * `PartyCoordinationService._trigger_ai_submissions_for_new_phase` may pre-seed AI prompts if configured.

6. **During each phase**

   * Players use **party-aware** endpoints:

     * `POST /party/{session_id}/rounds/prompt` → `start_party_prompt_round`.
     * `POST /party/{session_id}/rounds/copy` → `start_party_copy_round`.
     * `POST /party/{session_id}/rounds/vote` → `start_party_vote_round`.
   * Those call into `PartyCoordinationService`, which:

     * Validates phase & quotas against `PartySessionService`.
     * Calls `RoundService` / `VoteService` to create the actual QF rounds.
     * Links them into `PartyRound`.
   * Players then use the **existing** core QF endpoints to submit phrase / copy / vote for those round IDs / phraseset IDs. That’s intentional reuse of the standard flow.

7. **Submissions update progress + phases**

   * When a player submits:

     * Core service (`RoundService`/`VoteService`) does game logic + transactions.
     * `PartyCoordinationService` increments that player’s counters, pushes a `notify_player_progress` WS message with updated per-player and global progress, and checks `can_advance_phase`.
   * When everyone in the session is done with that phase:

     * `PartySessionService.advance_phase` updates `current_phase`.
     * `PartyWebSocketManager.notify_phase_transition` announces the new phase.
     * `_trigger_ai_submissions_for_new_phase` kicks in to let AI catch up.

8. **Session status polling**

   * `GET /party/{session_id}/status` calls `PartySessionService.get_session_status` to return a snapshot that mirrors what you’re seeing on WebSockets (participants, phase, quotas, progress).

### 3.3 Results + teardown

9. **Results** – `GET /party/{session_id}/results`

   * Router calls `PartyScoringService.calculate_session_results(session_id)` to compute rankings, player stats, and phraseset summaries as described above.
   * Response is `PartyResultsResponse`, which the frontend can render as the “final scoreboard + recap” screen.

10. **WebSocket lifecycle**

    * When the match ends (phase becomes `RESULTS`), the router and/or `PartyCoordinationService` call `notify_session_completed`; clients can close their WS or switch to showing static results.

---

## 4. Short mental model

* **PartySessionService** – “state and rules of the match”: lobby, phases, quotas, per-player counters.
* **PartyCoordinationService** – “do the work”: call the existing Quipflip prompt/copy/vote APIs in a party-aware way, wire them back to party models, and coordinate AI + phase transitions.
* **PartyScoringService** – “final scorekeeper”: aggregate all the rounds and transactions into a nice scoreboard + recap for the match.
* **PartyWebSocketManager** – “live feed”: broadcast lobby events, progress, and phase changes to all connected clients.

Everything sits on top of the **existing QF engine** (`RoundService`, `VoteService`, `QFTransaction`, queues, game rules). Party mode is mostly orchestration, state, and UX-level glue rather than new game logic.
