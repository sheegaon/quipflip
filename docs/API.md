# Quipflip API Documentation

## Base URL

```
Development: http://localhost:8000
Production: https://your-app.herokuapp.com
```

## Authentication

All endpoints except `/health`, `/`, and the new authentication routes require a valid
JSON Web Token (JWT) access token. During the transition period, legacy API keys are still
honored when supplied in the `X-API-Key` header, but new clients should migrate to JWTs.

**Access Token Header:**
```
Authorization: Bearer <access_token>
```

**Refresh Token Storage:**
- Refresh tokens are issued alongside access tokens.
- The API sets a HTTP-only cookie named `quipflip_refresh_token`.
- Clients can also send the refresh token explicitly in request bodies if needed.

**Getting Tokens:**
- Use `POST /player` to register with a username, email, and password.
- Use `POST /auth/login` with your credentials to obtain fresh tokens.
- Tokens expire after 15 minutes; call `POST /auth/refresh` (or rely on the cookie) to obtain a new pair.

**Legacy API Keys:**
- Responses continue to include a `legacy_api_key` for backward compatibility.
- Supply the key in the `X-API-Key` header if you cannot adopt JWTs immediately.
- Keys can still be rotated with `POST /player/rotate-key`.

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
- `201 Created` - Resource created (POST /player)
- `400 Bad Request` - Invalid request or business logic error
- `401 Unauthorized` - Missing or invalid credentials
- `404 Not Found` - Resource not found
- `409 Conflict` - State conflict (e.g., already voted)
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Common Error Messages
- `insufficient_balance` - Not enough balance for operation
- `already_in_round` - Player already has active round
- `expired` - Round expired past grace period
- `already_voted` - Already voted on this phraseset
- `already_claimed_today` - Daily bonus already claimed
- `duplicate_phrase` - Copy submission matched an existing phrase too closely
- `invalid_word` - Word validation failed
- `no_prompts_available` - No prompts available for copy
- `no_wordsets_available` - No phrasesets available for voting
- `max_outstanding_prompts` - Player has 10 open/closing phrasesets

---

## Endpoints

### Health & Info

#### `GET /`
Get API information.

**Response:**
```json
{
  "message": "Quipflip API - Phase 1 MVP",
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

### Player Endpoints

#### `POST /player`
Create a new player account (no authentication required).

**Request:**
```bash
curl -X POST http://localhost:8000/player \
  -H "Content-Type: application/json" \
  -d '{
        "username": "Prompt Pirate",
        "email": "prompt.pirate@example.com",
        "password": "SuperSecure123!"
      }'
```

**Response (201 Created):**
```json
{
  "player_id": "3555a0e9-d46d-4a36-8756-f0e9c836d822",
  "username": "Prompt Pirate",
  "access_token": "<jwt access token>",
  "refresh_token": "<refresh token>",
  "legacy_api_key": "dff60a88-04c8-4a11-a8d8-874add980d12",
  "expires_in": 900,
  "balance": 1000,
  "message": "Player created! Your account is ready to play. An access token and refresh token have been issued for authentication.",
  "token_type": "bearer"
}
```

**Important:** Store the refresh token securely. Legacy clients may continue to use `legacy_api_key` as a fallback.

#### `POST /player/rotate-key`
Rotate API key for security (requires authentication).

**Request:**
```bash
curl -X POST http://localhost:8000/player/rotate-key \
  -H "X-API-Key: your-current-api-key"
```

**Response:**
```json
{
  "new_api_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "API key rotated successfully. Use the new key for all future requests. Your old key is now invalid."
}
```

**Important:**
- Your old API key becomes invalid immediately
- Update all clients with the new key
- Use if you suspect key compromise

### Authentication Endpoints

#### `POST /auth/login`
Exchange a username and password for a new access token + refresh token pair.

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
        "username": "Prompt Pirate",
        "password": "SuperSecure123!"
      }'
```

**Response:**
```json
{
  "player_id": "3555a0e9-d46d-4a36-8756-f0e9c836d822",
  "username": "Prompt Pirate",
  "access_token": "<jwt access token>",
  "refresh_token": "<refresh token>",
  "legacy_api_key": "dff60a88-04c8-4a11-a8d8-874add980d12",
  "expires_in": 900,
  "token_type": "bearer"
}
```

#### `POST /auth/refresh`
Use an existing refresh token (or the refresh cookie) to obtain a new access token.

```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh token>"}'
```

Returns the same shape as `POST /auth/login` with a rotated refresh token.

#### `POST /auth/logout`
Invalidate a refresh token and clear the server cookie.

```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh token>"}'
```

Responds with `204 No Content`.

#### `GET /player/balance`
Get player balance and status.

**Response:**
```json
{
  "balance": 1000,
  "starting_balance": 1000,
  "daily_bonus_available": false,
  "daily_bonus_amount": 100,
  "last_login_date": "2025-01-06",
  "outstanding_prompts": 0
}
```

#### `POST /player/claim-daily-bonus`
Claim daily login bonus (\$100).

**Response:**
```json
{
  "success": true,
  "amount": 100,
  "new_balance": 1100
}
```

**Errors:**
- `already_claimed_today` - Already claimed bonus today
- `not_eligible` - Created account today

#### `GET /player/current-round`
Get currently active round.

**Response (active prompt round):**
```json
{
  "round_id": "uuid",
  "round_type": "prompt",
  "state": {
    "round_id": "uuid",
    "status": "active",
    "expires_at": "2025-01-06T12:34:56",
    "cost": 100,
    "prompt_text": "my deepest desire is to be (a/an)"
  },
  "expires_at": "2025-01-06T12:34:56"
}
```

**Response (active copy round):**
```json
{
  "round_id": "uuid",
  "round_type": "copy",
  "state": {
    "round_id": "uuid",
    "status": "active",
    "expires_at": "2025-01-06T12:34:56",
    "cost": 90,
    "original_phrase": "FAMOUS",
    "discount_active": true
  },
  "expires_at": "2025-01-06T12:34:56"
}
```

**Response (active vote round):**
```json
{
  "round_id": "uuid",
  "round_type": "vote",
  "state": {
    "round_id": "uuid",
    "status": "active",
    "expires_at": "2025-01-06T12:34:56",
    "phraseset_id": "uuid",
    "prompt_text": "the secret to happiness is (a/an)",
    "phrases": ["LOVE", "MONEY", "CONTENTMENT"]
  },
  "expires_at": "2025-01-06T12:34:56"
}
```

**Response (no active round):**
```json
{
  "round_id": null,
  "round_type": null,
  "state": null,
  "expires_at": null
}
```

**Notes:**
- `state` structure varies by `round_type` (prompt/copy/vote)
- `status` can be "active" or "submitted"
- Frontend should poll this endpoint or check after each action

#### `GET /player/pending-results`
Get list of finalized phrasesets awaiting result viewing.

**Response:**
```json
{
  "pending": [
    {
      "phraseset_id": "uuid",
      "prompt_text": "the meaning of life is",
      "completed_at": "2025-01-06T12:00:00",
      "role": "prompt",
      "payout_claimed": false
    }
  ]
}
```

#### `GET /player/statistics`
Get comprehensive player statistics including win rates, earnings breakdown, and performance metrics.

**Response:**
```json
{
  "player_id": "uuid",
  "username": "Prompt Pirate",
  "overall_balance": 1250,
  "prompt_stats": {
    "role": "prompt",
    "total_rounds": 15,
    "total_earnings": 450,
    "average_earnings": 30.0,
    "win_rate": 66.7,
    "total_phrasesets": 12,
    "average_votes_received": 3.5
  },
  "copy_stats": {
    "role": "copy",
    "total_rounds": 20,
    "total_earnings": 380,
    "average_earnings": 19.0,
    "win_rate": 55.0,
    "total_phrasesets": 18,
    "average_votes_received": 2.8
  },
  "voter_stats": {
    "role": "voter",
    "total_rounds": 50,
    "total_earnings": 200,
    "average_earnings": 4.0,
    "win_rate": 80.0,
    "correct_votes": 40,
    "vote_accuracy": 80.0
  },
  "earnings": {
    "prompt_earnings": 450,
    "copy_earnings": 380,
    "vote_earnings": 200,
    "daily_bonuses": 300,
    "total_earnings": 1330
  },
  "frequency": {
    "total_rounds_played": 85,
    "days_active": 12,
    "rounds_per_day": 7.1,
    "last_active": "2025-01-06T14:30:00Z",
    "member_since": "2024-12-25T10:00:00Z"
  },
  "favorite_prompts": [
    "my deepest desire is to be (a/an)",
    "the secret to happiness is (a/an)",
    "I would never"
  ],
  "best_performing_phrases": [
    {
      "phrase": "FAMOUS",
      "votes": 8,
      "earnings": 150
    },
    {
      "phrase": "CONTENTMENT",
      "votes": 6,
      "earnings": 120
    }
  ]
}
```

**Notes:**
- Returns comprehensive statistics for all three roles
- Win rate is percentage of rounds with positive earnings
- Vote accuracy is percentage of correct votes
- Best performing phrases ranked by votes received

---

### Round Endpoints

#### `POST /rounds/prompt`
Start a prompt round (-\$100).

**Request Body:**
```json
{}
```

**Response:**
```json
{
  "round_id": "uuid",
  "prompt_text": "my deepest desire is to be (a/an)",
  "expires_at": "2025-01-06T12:35:56",
  "cost": 100
}
```

**Errors:**
- `already_in_round` - Player already in active round
- `insufficient_balance` - Balance < \$100
- `max_outstanding_prompts` - Player has 10 open/closing phrasesets

#### `POST /rounds/copy`
Start a copy round (-\$100 or -\$90).

**Response:**
```json
{
  "round_id": "uuid",
  "original_phrase": "FAMOUS",
  "prompt_round_id": "uuid",
  "expires_at": "2025-01-06T12:36:00",
  "cost": 90,
  "discount_active": true
}
```

**Errors:**
- `no_prompts_available` - No prompts in queue
- `already_in_round` - Player already in active round
- `insufficient_balance` - Balance < cost

#### `POST /rounds/vote`
Start a vote round (-\$1).

**Response:**
```json
{
  "round_id": "uuid",
  "phraseset_id": "uuid",
  "prompt_text": "the secret to happiness is (a/an)",
  "phrases": ["LOVE", "MONEY", "CONTENTMENT"],  // Randomized order
  "expires_at": "2025-01-06T12:30:15"
}
```

**Errors:**
- `no_wordsets_available` - No phrasesets in queue
- `already_in_round` - Player already in active round
- `insufficient_balance` - Balance < \$1

#### `POST /rounds/{round_id}/submit`
Submit phrase for prompt or copy round.

**Request Body:**
```json
{
  "phrase": "famous"
}
```

**Response:**
```json
{
  "success": true,
  "phrase": "FAMOUS"
}
```

**Errors:**
- `invalid_phrase` - Word not in dictionary or invalid format
- `duplicate_phrase` - Copy word matches original or is too similar
- `expired` - Past grace period
- `not_found` - Round not found or not owned by player

#### `GET /rounds/available`
Get round availability status.

**Response:**
```json
{
  "can_prompt": true,
  "can_copy": true,
  "can_vote": false,
  "prompts_waiting": 12,
  "phrasesets_waiting": 0,
  "copy_discount_active": true,
  "copy_cost": 90,
  "current_round_id": null
}
```

#### `GET /rounds/{round_id}`
Get round details.

**Response:**
```json
{
  "round_id": "uuid",
  "type": "prompt",
  "status": "submitted",
  "expires_at": "2025-01-06T12:35:56",
  "prompt_text": "my deepest desire is to be (a/an)",
  "original_phrase": null,
  "submitted_phrase": "FAMOUS",
  "cost": 100
}
```

---

### Phraseset Endpoints

#### `POST /phrasesets/{phraseset_id}/vote`
Submit vote for phraseset.

**Request Body:**
```json
{
  "phrase": "LOVE"
}
```

**Response:**
```json
{
  "correct": true,
  "payout": 5,
  "original_phrase": "LOVE",
  "your_choice": "LOVE"
}
```

**Errors:**
- `expired` - Past grace period
- `already_voted` - Already voted on this phraseset
- `player_not_in_round` - Not in active vote round

#### `GET /phrasesets/{phraseset_id}/details`
Get full contributor view for a phraseset the player participated in.

**Response:**
```json
{
  "phraseset_id": "uuid",
  "prompt_round_id": "uuid",
  "prompt_text": "my deepest desire is to be (a/an)",
  "status": "finalized",
  "original_phrase": "FAMOUS",
  "copy_phrase_1": "POPULAR",
  "copy_phrase_2": "WEALTHY",
  "contributors": [
    {"player_id": "uuid", "username": "Prompt Pirate", "is_you": true, "phrase": "FAMOUS"},
    {"player_id": "uuid", "username": "Copy Cat", "is_you": false, "phrase": "POPULAR"},
    {"player_id": "uuid", "username": "Shadow Scribe", "is_you": false, "phrase": "WEALTHY"}
  ],
  "vote_count": 10,
  "third_vote_at": "2025-01-06T12:10:00Z",
  "fifth_vote_at": "2025-01-06T12:11:05Z",
  "closes_at": "2025-01-06T12:12:05Z",
  "votes": [
    {
      "vote_id": "uuid",
      "voter_id": "uuid",
      "voter_username": "Voter 1",
      "voted_phrase": "FAMOUS",
      "correct": true,
      "voted_at": "2025-01-06T12:10:30Z"
    }
  ],
  "total_pool": 300,
  "results": {
    "vote_counts": {
      "FAMOUS": 6,
      "POPULAR": 2,
      "WEALTHY": 2
    },
    "payouts": {
      "prompt": {"player_id": "uuid", "payout": 150, "points": 6},
      "copy1": {"player_id": "uuid", "payout": 100, "points": 2},
      "copy2": {"player_id": "uuid", "payout": 50, "points": 2}
    },
    "total_pool": 300
  },
  "your_role": "prompt",
  "your_phrase": "FAMOUS",
  "your_payout": 150,
  "payout_claimed": true,
  "activity": [
    {
      "activity_id": "uuid",
      "activity_type": "vote_recorded",
      "created_at": "2025-01-06T12:10:30Z",
      "player_id": "uuid",
      "player_username": "Voter 1",
      "metadata": {"phrase": "FAMOUS"}
    }
  ],
  "created_at": "2025-01-06T12:00:00Z",
  "finalized_at": "2025-01-06T12:12:05Z"
}
```

**Errors:**
- `Phraseset not found` - Invalid phraseset ID
- `Not a contributor to this phraseset` - Player did not submit the prompt or copies

#### `GET /phrasesets/{phraseset_id}/results`
Get phraseset results (collects prize on first view).

**Response:**
```json
{
  "prompt_text": "my deepest desire is to be (a/an)",
  "votes": [
    {"phrase": "FAMOUS", "vote_count": 4, "is_original": true},
    {"phrase": "POPULAR", "vote_count": 3, "is_original": false},
    {"phrase": "WEALTHY", "vote_count": 3, "is_original": false}
  ],
  "your_phrase": "FAMOUS",
  "your_role": "prompt",
  "your_points": 4,
  "your_payout": 62,
  "total_pool": 250,
  "total_votes": 10,
  "already_collected": true,
  "finalized_at": "2025-01-06T13:00:00"
}
```

**Errors:**
- `Phraseset not found` - Invalid phraseset ID
- `Phraseset not yet finalized` - Still collecting votes
- `Not a contributor to this phraseset` - Player wasn't prompt/copy contributor

#### `POST /phrasesets/{phraseset_id}/claim`
Explicitly mark a phraseset payout as claimed (idempotent).

**Response:**
```json
{
  "success": true,
  "amount": 150,
  "new_balance": 1320,
  "already_claimed": false
}
```

**Errors:**
- `Phraseset not found` - Invalid phraseset ID
- `Not a contributor to this phraseset` - Player did not submit the prompt or copies

---

## Example Workflows

### Complete Game Flow

```bash
# 1. Check balance
curl -H "X-API-Key: your-key" http://localhost:8000/player/balance

# 2. Start prompt round
curl -X POST -H "X-API-Key: your-key" http://localhost:8000/rounds/prompt

# 3. Submit phrase
curl -X POST -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"phrase":"famous"}' \
  http://localhost:8000/rounds/{round_id}/submit

# 4. Start copy round (as different player)
curl -X POST -H "X-API-Key: other-key" http://localhost:8000/rounds/copy

# 5. Submit copy word
curl -X POST -H "X-API-Key: other-key" \
  -H "Content-Type: application/json" \
  -d '{"phrase":"popular"}' \
  http://localhost:8000/rounds/{round_id}/submit

# 6. Start vote round (after 2 copies submitted)
curl -X POST -H "X-API-Key: voter-key" http://localhost:8000/rounds/vote

# 7. Submit vote
curl -X POST -H "X-API-Key: voter-key" \
  -H "Content-Type: application/json" \
  -d '{"phrase":"FAMOUS"}' \
  http://localhost:8000/phrasesets/{phraseset_id}/vote

# 8. View results (after finalization)
curl -H "X-API-Key: your-key" http://localhost:8000/phrasesets/{phraseset_id}/results
```

---

## Rate Limiting

Rate limiting has not yet been implemented in the backend. It remains a roadmap item for future phases; clients should still implement sensible retry/backoff behaviour to prepare for eventual enforcement.

---

## Interactive API Documentation

Visit `/docs` for interactive Swagger UI documentation where you can test all endpoints.

Visit `/redoc` for alternative ReDoc documentation.

---

## Game Configuration

### Timing
- **Prompt round**: 3 minutes (180 seconds)
- **Copy round**: 3 minutes (180 seconds)
- **Vote round**: 60 seconds
- **Grace period**: 5 seconds (not shown to users - allows late submissions)

### Economics
- **Starting balance**: \$1000
- **Daily bonus**: \$100
- **Prompt cost**: \$100
- **Copy cost**: \$100 normal, \$90 with discount
- **Vote cost**: \$1
- **Vote payout (correct)**: \$5
- **Phraseset prize pool**: \$300
- **Copy discount threshold**: >10 prompts waiting
- **Max outstanding prompts**: 10 per player

### Validation
- **Word length**: 2-15 characters
- **Word format**: Letters A-Z only (case insensitive, stored uppercase)
- **Dictionary**: NASPA word list
- **Copy validation**: Must differ from original phrase

### WordSet Voting Lifecycle
1. **Open**: 0-2 votes submitted
2. **Closing**: 3+ votes, 10-minute window starts
3. **Rapid closing**: 5+ votes, 60-second window starts
4. **Closed**: Window expired, no new votes
5. **Finalized**: Results calculated, prizes distributed

### Prize Distribution
- Prize pool split among prompt + 2 copy contributors
- Share proportional to votes received for your word
- System contributes \$10 if copy used discount pricing

## Frontend Integration

### CORS
CORS is enabled for all origins in development. For production:
- Configure `CORS_ORIGINS` environment variable
- Include credentials in requests if using cookies
- API key authentication via headers is recommended

### State Management
**Required state to track:**
- Current player API key (persistent storage)
- Current balance (update from `/player/balance`)
- Active round state (poll `/player/current-round` or update after actions)
- Pending results count (from `/player/pending-results`)

**Recommended polling intervals:**
- Balance/status: Every 30 seconds or after actions
- Current round: Every 5 seconds if timer is active
- Pending results: Every 60 seconds or after round completion

### Timer Management
- Display countdown using `expires_at` timestamp
- Don't show grace period to users (5 seconds)
- Calculate time remaining: `expires_at - current_time`
- Show "expired" when timer reaches 0
- User can still submit within grace period

### Error Handling
- Check `status` code first (200/400/401/404/409)
- Parse `detail` field for user-friendly message
- Handle `insufficient_balance` by prompting to claim daily bonus
- Handle `already_in_round` by fetching current round state
- Handle `expired` by refreshing available rounds

### Typical User Flow
1. **First visit**: Call `POST /player` → store API key
2. **Return visit**: Load API key → call `GET /player/balance`
3. **Check daily bonus**: If `daily_bonus_available` → offer to claim
4. **Start round**: Check `GET /rounds/available` → start desired round type
5. **During round**: Display timer, submit word before expiry
6. **Check results**: Poll `/player/pending-results` → view when ready

### TypeScript Types (Example)
```typescript
interface Player {
  balance: number
  daily_bonus_available: boolean
  outstanding_prompts: number
}

interface ActiveRound {
  round_id: string | null
  round_type: 'prompt' | 'copy' | 'vote' | null
  expires_at: string | null
  state: PromptState | CopyState | VoteState | null
}

interface PromptState {
  round_id: string
  status: 'active' | 'submitted'
  expires_at: string
  cost: number
  prompt_text: string
}

interface CopyState {
  round_id: string
  status: 'active' | 'submitted'
  expires_at: string
  cost: number
  original_phrase: string
  discount_active: boolean
}

interface VoteState {
  round_id: string
  status: 'active' | 'submitted'
  expires_at: string
  phraseset_id: string
  prompt_text: string
  phrases: string[]
}
```

## Notes

- All timestamps in UTC ISO 8601 format
- All currency amounts in whole dollars (integer values: 100 = \$100)
- Words automatically converted to uppercase
- Grace period allows submissions up to 5 seconds past expiry
- `/docs` and `/redoc` provide interactive API testing
