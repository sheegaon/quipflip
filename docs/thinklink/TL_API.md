# ThinkLink (TL) API Documentation

ThinkLink endpoints live under the `/tl` prefix and are implemented in `backend/routers/tl`, sharing authentication middleware and response envelopes with the common routers documented in [API.md](../API.md). Authentication, health, and WebSocket token exchange are defined centrally there; this guide focuses on game-specific behavior.

## Base URL

```
Development: http://localhost:8000/tl
Production (Frontend): https://thinklink.xyz
Production (API): https://thinklink.xyz/api (proxied to Heroku backend)
```

## Authentication

All endpoints except `/health` and `/` require a valid JSON Web Token (JWT) access token. See [API.md - Authentication](../API.md#authentication) for cookie-based and header-based token usage.

## Data Model Reference

Field-level definitions for database entities live in [TL_DATA_MODELS.md](TL_DATA_MODELS.md). This API guide focuses on HTTP requests and response envelopes; whenever you see a round, guess, cluster, or transaction object referenced here, the authoritative schema lives in that document.

## Response Format

### Success Response
```json
{
  // Response data based on endpoint
}
```

### Error Response
```json
{
  "detail": "Human-readable error message"
}
```

### HTTP Status Codes
- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Invalid request or business logic error
- `401 Unauthorized` - Missing or invalid credentials
- `403 Forbidden` - Admin access required
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

### Common Error Messages
- `insufficient_balance` - Not enough ThinkCoins for operation
- `round_not_found` - Round ID doesn't exist
- `unauthorized` - Player doesn't own this round
- `round_not_active` - Round is no longer active
- `round_already_ended` - Round has 3 strikes
- `off_topic` - Guess too different from prompt
- `too_similar` - Guess too similar to prior guess in round
- `invalid_phrase` - Phrase failed validation (format, dictionary, prompt overlap)
- `no_prompts_available` - No prompts available to start round
- `invalid_admin_access` - User is not an admin

---

## Endpoints

### Health & Info

#### `GET /`
Get API information.

**Response:**
```json
{
  "message": "ThinkLink API - Semantic Matching Game",
  "version": "1.0.0",
  "environment": "development",
  "docs": "/docs"
}
```

#### `GET /health`
Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "memory"  // or "connected"
}
```

---

## Game Endpoints

### Player Endpoints

#### `GET /tl/player/dashboard`
Get current player's ThinkLink dashboard (balance, stats, round status).

**Authentication:** Required (JWT token)

**Response:**
```json
{
  "player_id": "uuid",
  "username": "player123",
  "wallet": 1000,
  "vault": 250,
  "tutorial_completed": true,
  "rounds_completed": 45,
  "total_earnings": 2500,
  "current_balance": 1250
}
```

#### `GET /tl/player/balance`
Get current player's balance summary.

**Authentication:** Required

**Response:**
```json
{
  "wallet": 1000,
  "vault": 250,
  "total": 1250
}
```

---

### Round Endpoints

#### `GET /tl/rounds/available`
Check if player can start a new round and get balance info.

**Authentication:** Required

**Response:**
```json
{
  "can_start_round": true,
  "error_message": null,
  "tl_wallet": 1000,
  "tl_vault": 250,
  "entry_cost": 100,
  "max_payout": 300,
  "starting_balance": 1000
}
```

**Response (Insufficient Balance):**
```json
{
  "can_start_round": false,
  "error_message": "insufficient_balance",
  "tl_wallet": 50,
  "tl_vault": 250,
  "entry_cost": 100,
  "max_payout": 300,
  "starting_balance": 1000
}
```

**Usage:** Call before showing "Start Round" button to validate player has enough coins.

---

#### `POST /tl/rounds/start`
Start a new ThinkLink round.

**Authentication:** Required

**Request:**
```json
{
  // No body - endpoint is stateless
}
```

**Response (Success):**
```json
{
  "round_id": "uuid",
  "prompt_id": "uuid",
  "prompt_text": "Name something people forget at home",
  "wallet_before": 1000,
  "wallet_after": 900,
  "entry_cost": 100,
  "status": "active",
  "strikes": 0,
  "created_at": "2025-12-03T10:30:00Z"
}
```

**Errors:**
- `insufficient_balance` - Not enough coins (minimum 100)
- `no_prompts_available` - No active prompts available

**Business Logic:**
1. Verify player has >= 100 ThinkCoins
2. Select random active prompt
3. Build corpus snapshot (up to 1000 active answers + clusters)
4. Deduct 100 coins
5. Create TLRound with status='active', strikes=0

---

#### `POST /tl/rounds/{round_id}/guess`
Submit a guess in an active round.

**Authentication:** Required

**Request:**
```json
{
  "guess_text": "My wallet"
}
```

**Response (Match):**
```json
{
  "was_match": true,
  "matched_answer_count": 3,
  "matched_cluster_ids": ["cluster-uuid-1", "cluster-uuid-2"],
  "new_strikes": 0,
  "current_coverage": 0.45,
  "round_status": "active"
}
```

**Response (No Match):**
```json
{
  "was_match": false,
  "matched_answer_count": 0,
  "matched_cluster_ids": [],
  "new_strikes": 1,
  "current_coverage": 0.35,
  "round_status": "active"
}
```

**Response (Round Ended):**
```json
{
  "was_match": false,
  "matched_answer_count": 0,
  "matched_cluster_ids": [],
  "new_strikes": 3,
  "current_coverage": 0.35,
  "round_status": "abandoned"  // 3 strikes reached
}
```

**Errors:**
- `round_not_found` - Round doesn't exist
- `unauthorized` - Player doesn't own round
- `round_not_active` - Round already ended
- `round_already_ended` - 3 strikes reached
- `invalid_phrase` - Failed phrase validation
- `off_topic` - Similarity to prompt < 0.40
- `too_similar` - Similarity to prior guess >= 0.80

**Business Logic:**
1. Verify round exists and is active
2. **Phrase validation** (no strikes if fails):
   - Check format (2-5 words, A-Z and spaces only, 4-100 chars)
   - Check dictionary (NASPA words)
   - Check no significant word overlap with prompt
3. Generate embedding (OpenAI text-embedding-3-small)
4. **On-topic check** (no strikes if fails): Similarity to prompt >= 0.40
5. **Self-similarity check** (no strikes if fails): Not >= 0.80 similar to any prior guess
6. **Find matches** in snapshot answers: Cosine similarity >= 0.55
7. If matches found:
   - Add matched clusters to round.matched_clusters
   - Mark was_match=true
   - NO strike
8. If no matches:
   - Add strike (strikes++)
   - If strikes >= 3: round.status='abandoned'
   - Mark caused_strike=true
9. Log TLGuess record
10. Calculate current_coverage and return

**Validation Errors** (invalid_phrase, off_topic, too_similar) do NOT:
- Consume strikes
- Create guess entries (fail fast)
- Update round state

---

#### `POST /tl/rounds/{round_id}/abandon`
Abandon active round with partial refund.

**Authentication:** Required

**Request:**
```json
{
  // No body
}
```

**Response:**
```json
{
  "round_id": "uuid",
  "status": "abandoned",
  "refund_amount": 95
}
```

**Errors:**
- `round_not_found` - Round doesn't exist
- `unauthorized` - Player doesn't own round
- `round_not_active` - Already ended

**Business Logic:**
1. Verify round exists and is active
2. Calculate refund: entry_cost - 5 penalty = 95 coins
3. Update round.status='abandoned'
4. Add coins back to player wallet
5. Log TLTransaction

---

#### `GET /tl/rounds/{round_id}`
Get round details and guess history.

**Authentication:** Required

**Response:**
```json
{
  "round_id": "uuid",
  "prompt_text": "Name something people forget at home",
  "status": "active",
  "strikes": 1,
  "matched_clusters": ["cluster-1", "cluster-2"],
  "current_coverage": 0.45,
  "guesses": [
    {
      "guess_id": "uuid",
      "text": "My keys",
      "was_match": true,
      "matched_cluster_ids": ["cluster-1"],
      "created_at": "2025-12-03T10:31:00Z"
    },
    {
      "guess_id": "uuid",
      "text": "Bad!",
      "was_match": false,
      "matched_cluster_ids": [],
      "caused_strike": true,
      "created_at": "2025-12-03T10:32:00Z"
    }
  ],
  "created_at": "2025-12-03T10:30:00Z"
}
```

**Errors:**
- `round_not_found` - Round doesn't exist

---

### Game Info Endpoints

#### `GET /tl/game/prompts/preview`
Get a random prompt preview without starting a round (for discovery).

**Authentication:** Not required

**Response:**
```json
{
  "prompt_text": "Name something people forget at home",
  "hint": "What answers would you guess?"
}
```

---

### Admin Endpoints

#### `POST /tl/admin/prompts/seed`
Seed prompts from a list (admin only).

**Authentication:** Required + Admin

**Request:**
```json
{
  "prompts": [
    "Name something people forget at home",
    "Name something you find in a kitchen",
    "Name a reason to call the fire department"
  ]
}
```

**Response:**
```json
{
  "created_count": 2,
  "skipped_count": 1,
  "total_count": 3
}
```

**Errors:**
- `unauthorized` - Not admin
- `seed_failed` - Server error during seeding

**Business Logic:**
1. For each prompt text:
   - Check if already exists
   - Generate embedding (OpenAI)
   - Create TLPrompt with is_active=true

---

#### `GET /tl/admin/corpus/{prompt_id}`
Get corpus statistics for a prompt (admin only).

**Authentication:** Required + Admin

**Response:**
```json
{
  "prompt_id": "uuid",
  "prompt_text": "Name something people forget at home",
  "active_answer_count": 847,
  "cluster_count": 142,
  "total_weight": 1250.5,
  "largest_cluster_size": 12,
  "smallest_cluster_size": 1
}
```

**Errors:**
- `unauthorized` - Not admin
- `prompt_not_found` - Prompt doesn't exist
- `stats_failed` - Server error

**Usage:** Monitor corpus health and identify over-large clusters.

---

#### `POST /tl/admin/corpus/{prompt_id}/prune`
Manually trigger corpus pruning for a prompt (admin only).

**Authentication:** Required + Admin

**Request:**
```json
{
  // No body
}
```

**Response:**
```json
{
  "prompt_id": "uuid",
  "removed_count": 247,
  "current_active_count": 753,
  "target_count": 1000
}
```

**Errors:**
- `unauthorized` - Not admin
- `prompt_not_found` - Prompt doesn't exist
- `prune_failed` - Server error

**Business Logic:**
1. Get all active answers for prompt
2. Calculate usefulness for each: `contributed_matches / (shows + 1)`
3. Keep top ~1000 by usefulness
4. Mark rest as is_active=false
5. Return removed count and current count

---

## Phrase Validation Details

Phrase validation occurs in `submit_guess` and enforces:

### Format Checks
- **Length**: 4-100 characters (including spaces)
- **Characters**: A-Z and spaces only (case-insensitive)
- **Word Count**: 2-5 words
- **Words**: Each word 2-15 characters (except common words like 'a', 'I')

### Dictionary Checks
- **Dictionary**: NASPA (North American Scrabble Players Association)
- **Exceptions**: Certain common pronouns and articles ('a', 'i', 'the', etc.) are always allowed
- **Stemming**: Basic suffix stripping (ing, ed, er, etc.) for fuzzy matching

### Context Checks
- **Prompt Overlap**: Cannot reuse significant words (4+ chars, non-common) from the prompt
- **Self-Similarity**: Cannot submit guess too similar (>= 0.80 cosine) to prior guesses in same round

**Example Rejections:**
- `"Key"` - Too short (3 chars)
- `"Keys"` - Single word (need 2+)
- `"My keys123"` - Contains numbers
- `"I forget things"` - Reuses "forget" from prompt "Name something people forget at home"
- `"Some xyzzy word"` - "xyzzy" not in dictionary
- `"My Wallet"` on round with prior guess "My Wallet" - Identical text

**Examples That Pass:**
- `"My Wallet"` - 2 words, dictionary words, letters only
- `"Lost keys at office"` - 4 words, no prompt words (prompt is "forget at home")
- `"The Phone"` - "the" is common word allowed, "phone" in dictionary

---

## Matching & Coverage Details

### Match Threshold
Cosine similarity >= 0.55 to any answer in a cluster counts as match.

### Coverage Calculation
```
coverage = sum(matched_cluster_weights) / total_snapshot_weight
```

Where cluster weight = sum of answer weights, and answer weight = `1 + log(1 + min(answer_players_count, 20))`.

### Payout Formula
```
gross_payout = round(300 * (coverage ** 1.5))
net_payout = gross_payout (earnings <= 100)
net_payout = gross_payout - (0.30 * (gross_payout - 100)) (earnings > 100)
```

**Examples:**
- 0% coverage: $0
- 50% coverage: $95
- 100% coverage: $300
- If payout is $150: vault gets 30% of $(150-100) = $15, player gets $135

---

## Error Handling

### Validation Errors Don't Count as Strikes
When a guess fails validation (invalid_phrase, off_topic, too_similar):
- Error returned to client
- No strike added
- No TLGuess entry created
- Round state unchanged

This allows players to refine guesses without penalty.

### No Matches Adds a Strike
When a guess passes all validations but finds no matches:
- A strike is added
- TLGuess entry created with caused_strike=true
- Round ends if strikes >= 3

### Round Finalization
When a round ends (3 strikes or abandon):
- final_coverage calculated as matched_weight / snapshot_weight
- gross_payout calculated using payout formula
- TLTransaction created for payout (if >= 1 coin)
- round.status set to 'abandoned'

---

## Rate Limiting

Currently not implemented. Future v2 may add limits like:
- Max 10 guesses per minute per round
- Max 100 guesses per day per player
- Max 5 rounds per hour per player

---

## Websocket (Future)

v1 does not implement real-time updates. Future versions may add:
- Round state updates (new matches, strikes)
- Leaderboard live updates
- Challenge notifications
