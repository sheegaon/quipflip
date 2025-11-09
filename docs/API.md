# Quipflip API Documentation

## Base URL

```
Development: http://localhost:8000
Production (Frontend): https://quipflip.xyz
Production (API): https://quipflip.xyz/api (proxied to Heroku backend)
```

**Note:** In production, the frontend uses Vercel's rewrite feature to proxy `/api/*` requests to the Heroku backend. This ensures same-origin requests for maximum browser compatibility (especially iOS Safari/Chrome).

## Authentication

All endpoints except `/health` and `/` require a valid JSON Web Token (JWT) access token.

**Cookie-Based Authentication (Preferred):**
- The API uses HTTP-only cookies for secure token storage
- Access tokens are stored in `quipflip_access_token` cookie (2-hour lifetime)
- Refresh tokens are stored in `quipflip_refresh_token` cookie (30-day lifetime)
- Cookies are automatically sent with requests when using `withCredentials: true`
- Provides XSS protection since JavaScript cannot access HTTP-only cookies
- **iOS Compatible:** The Vercel proxy ensures cookies work on all iOS browsers (Safari, Chrome, etc.)

**Authorization Header (Backward Compatibility):**
```
Authorization: Bearer <access_token>
```
- Still supported for API clients that cannot use cookies
- The backend checks cookies first, then falls back to the Authorization header

**Token Lifecycle:**
- Login/registration endpoints automatically set both access and refresh token cookies
- Access tokens expire after 2 hours
- Call `POST /auth/refresh` to get new tokens (uses refresh token cookie automatically)
- Logout clears both cookies from the browser

**Getting Tokens:**
- Use `POST /player/guest` to create a guest account instantly (no email/password required).
- Use `POST /player` to register with an email and password (the backend generates a username and pseudonym automatically).
- Use `POST /auth/login` with your email and password to obtain fresh tokens.
- Use `POST /player/upgrade` to convert a guest account to a full account.
- All authentication endpoints set HTTP-only cookies for both access and refresh tokens.

## Data Model Reference

Field-level definitions for database entities live in [DATA_MODELS.md](DATA_MODELS.md). This API guide focuses on HTTP requests and response envelopes; whenever you see a player, round, phraseset, quest, or transaction object referenced here, the authoritative schema lives in that document.

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
- `no_phrasesets_available` - No phrasesets available for voting
- `max_outstanding_quips` - Player has 10 open/closing phrasesets

---

## Endpoints

### Health & Info

#### `GET /`
Get API information.

**Response:**
```json
{
  "message": "Quipflip API - Phase 2 MVP",
  "version": "1.1.0",
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

#### `POST /player/guest`
Create a guest account instantly (no authentication required). Guest accounts allow immediate play without email/password signup.

**Request:**
```bash
curl -X POST http://localhost:8000/player/guest
```

**Response (201 Created):**
```json
{
  "player_id": "3555a0e9-d46d-4a36-8756-f0e9c836d822",
  "username": "Prompt Pirate",
  "access_token": "<jwt access token>",
  "refresh_token": "<refresh token>",
  "expires_in": 7200,
  "balance": 5000,
  "email": "guest1234@quipflip.xyz",
  "password": "QuipGuest",
  "message": "Guest account created! Your temporary credentials are:\nEmail: guest1234@quipflip.xyz\nPassword: QuipGuest\n\nYou can upgrade to a full account anytime to choose your own email and password.",
  "token_type": "bearer"
}
```

**Important:**
- Guest credentials are auto-generated and shown only once
- Save these credentials to log in later
- Guest accounts can be upgraded to full accounts via `POST /player/upgrade`
- Guest accounts have stricter rate limits (50 req/min general, 10 req/min voting vs 100/20 for full accounts)

#### `POST /player`
Create a new player account (no authentication required).

**Request:**
```bash
curl -X POST http://localhost:8000/player \
  -H "Content-Type: application/json" \
  -d '{
        "email": "prompt.pirate@example.com",
        "password": "SuperSecure123!"
      }'
```

**Note:** The backend assigns both the public username and hidden pseudonym; clients should not send custom values.

See [Player](DATA_MODELS.md#player) for persisted fields.

**Response (201 Created):**
```json
{
  "player_id": "3555a0e9-d46d-4a36-8756-f0e9c836d822",
  "username": "Prompt Pirate",
  "access_token": "<jwt access token>",
  "refresh_token": "<refresh token>",
  "expires_in": 7200,
  "balance": 5000,
  "message": "Player created! Your account is ready to play. An access token and refresh token have been issued for authentication.",
  "token_type": "bearer"
}
```

**Important:** Store the refresh token securely in HTTP-only cookies or secure storage.

#### `POST /player/upgrade`
Upgrade a guest account to a full account with custom email and password. Preserves all progress, balance, and stats.

**Request:**
```bash
curl -X POST http://localhost:8000/player/upgrade \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <guest_access_token>" \
  -d '{
        "email": "prompt.pirate@example.com",
        "password": "SuperSecure123!"
      }'
```

**Response (200 OK):**
```json
{
  "player_id": "3555a0e9-d46d-4a36-8756-f0e9c836d822",
  "username": "Prompt Pirate",
  "access_token": "<new jwt access token>",
  "refresh_token": "<new refresh token>",
  "expires_in": 7200,
  "message": "Account upgraded successfully! You can now log in with your new credentials.",
  "token_type": "bearer"
}
```

**Errors:**
- `400 not_a_guest` - Account is already a full account
- `409 email_taken` - Email already in use by another account
- `422 <password error>` - Password doesn't meet requirements (min 8 chars, uppercase, lowercase, number)

### Authentication Endpoints

#### `GET /auth/suggest-username`
Generate a random, available display name. Useful for previewing what the registration flow will assign.

**Response:**
```json
{
  "suggested_username": "Prompt Pirate"
}
```

#### `POST /auth/login`
Exchange an email and password for a new access token + refresh token pair.

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
        "email": "prompt.pirate@example.com",
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
  "expires_in": 7200,
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
  "username": "Prompt Pirate",
  "email": "prompt.pirate@example.com",
  "balance": 5000,
  "starting_balance": 5000,
  "daily_bonus_available": false,
  "daily_bonus_amount": 100,
  "last_login_date": "2025-01-06T18:45:00Z",
  "created_at": "2025-01-01T12:00:00Z",
  "outstanding_prompts": 0,
  "is_guest": false
}
```

#### `POST /player/claim-daily-bonus`
Claim daily login bonus (100f).

**Response:**
```json
{
  "success": true,
  "amount": 100,
  "new_balance": 5100
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
    "cost": 40,
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
      "result_viewed": false
    }
  ]
}
```

#### `GET /player/phrasesets`
Retrieve a paginated list of the current player's prompt and copy contributions.

- Query params: `role` (`all`, `prompt`, `copy`), `status` (`all` or any [phraseset status](DATA_MODELS.md#phraseset)), `limit` (1-100), `offset` (>=0).
- Response mirrors `PhrasesetListResponse` with summaries derived from [Phraseset](DATA_MODELS.md#phraseset) rows.

```json
{
  "phrasesets": [
    {
      "phraseset_id": "uuid",
      "prompt_round_id": "uuid",
      "prompt_text": "the meaning of life is",
      "your_role": "prompt",
      "status": "voting",
      "created_at": "2025-01-06T11:55:00Z",
      "vote_count": 3,
      "has_copy1": true,
      "has_copy2": false,
      "your_payout": null,
      "result_viewed": false,
      "new_activity_count": 1
    }
  ],
  "total": 42,
  "has_more": true
}
```

#### `GET /player/phrasesets/summary`
Dashboard-friendly counts of in-progress and finalized phrasesets. Useful for quick stats cards.

```json
{
  "in_progress": {"prompts": 2, "copies": 1, "unclaimed_prompts": 0, "unclaimed_copies": 0},
  "finalized": {"prompts": 18, "copies": 22, "unclaimed_prompts": 1, "unclaimed_copies": 0},
  "total_unclaimed_amount": 175
}
```

#### `GET /player/unclaimed-results`
Returns finalized phrasesets where the player still has unclaimed payouts. Mirrors [ResultView](DATA_MODELS.md#resultview) tracking.

```json
{
  "unclaimed": [
    {
      "phraseset_id": "uuid",
      "prompt_text": "my deepest desire is to be (a/an)",
      "your_role": "copy",
      "your_phrase": "POPULAR",
      "finalized_at": "2025-01-05T18:12:04Z",
      "your_payout": 95
    }
  ],
  "total_unclaimed_amount": 95
}
```

#### `GET /player/dashboard`
Batched endpoint that composes balance, current round, pending results, phraseset summary, unclaimed results, and round availability. Ideal for a single dashboard fetch.

```json
{
  "player": { "username": "Prompt Pirate", "balance": 4985, "daily_bonus_available": true, "created_at": "2025-01-01T12:00:00Z" },
  "current_round": { "round_id": null, "round_type": null, "state": null, "expires_at": null },
  "pending_results": [],
  "phraseset_summary": { "in_progress": {"prompts": 1, "copies": 0, "unclaimed_prompts": 0, "unclaimed_copies": 0}, "finalized": {"prompts": 5, "copies": 8, "unclaimed_prompts": 1, "unclaimed_copies": 0}, "total_unclaimed_amount": 120 },
  "unclaimed_results": [],
  "round_availability": { "can_prompt": true, "can_copy": false, "can_vote": true, "prompts_waiting": 3, "phrasesets_waiting": 7, "copy_discount_active": false, "copy_cost": 50, "current_round_id": null, "prompt_cost": 100, "vote_cost": 10, "vote_payout_correct": 20, "abandoned_penalty": 50 }
}
```

#### `GET /player/statistics`
Get comprehensive player statistics including win rates, earnings breakdown, and performance metrics.

**Response:**
```json
{
  "player_id": "uuid",
  "username": "Prompt Pirate",
  "email": "prompt.pirate@example.com",
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
    "total_earnings": 1330,
    "prompt_spending": 1200,
    "copy_spending": 600,
    "vote_spending": 500,
    "total_spending": 2300
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

Statistics aggregate data from [Player](DATA_MODELS.md#player), [Round](DATA_MODELS.md#round-unified-for-prompt-copy-and-vote), [Phraseset](DATA_MODELS.md#phraseset), and [Transaction](DATA_MODELS.md#transaction-ledger) tables.

#### `GET /player/statistics/weekly-leaderboard`
Get the weekly leaderboard split by role (prompt, copy, voter), with players ranked by win rate for the trailing seven days.

**Response:**
```json
{
  "prompt_leaderboard": {
    "role": "prompt",
    "leaders": [
      {
        "player_id": "5d62d8cf-287d-4d07-9dde-4dbf7b815f9a",
        "username": "Witty Walrus",
        "role": "prompt",
        "total_costs": 400,
        "total_earnings": 800,
        "net_earnings": 400,
        "win_rate": 75.5,
        "total_rounds": 12,
        "rank": 1,
        "is_current_player": false
      }
    ]
  },
  "copy_leaderboard": {
    "role": "copy",
    "leaders": [
      {
        "player_id": "d47fce78-6ea0-4dc9-a1d5-9b82e25bd6e6",
        "username": "Sassy Sparrow",
        "role": "copy",
        "total_costs": 300,
        "total_earnings": 450,
        "net_earnings": 150,
        "win_rate": 66.7,
        "total_rounds": 9,
        "rank": 1,
        "is_current_player": true
      }
    ]
  },
  "voter_leaderboard": {
    "role": "voter",
    "leaders": [
      {
        "player_id": "a12bce89-7fb1-5ed0-b2e6-0c93f36ce7f7",
        "username": "Clever Crow",
        "role": "voter",
        "total_costs": 200,
        "total_earnings": 380,
        "net_earnings": 180,
        "win_rate": 82.0,
        "total_rounds": 15,
        "rank": 1,
        "is_current_player": false
      }
    ]
  },
  "generated_at": "2025-01-12T17:05:42.188529+00:00"
}
```

**Notes:**
- Results are split into three separate leaderboards, one for each role (prompt, copy, voter).
- Each leaderboard is sorted by highest `win_rate` (percentage of rounds where earnings exceeded costs). Ties break alphabetically by username.
- `win_rate` is a percentage (0-100) representing the proportion of rounds where the player earned more than they spent in that role.
- Only the top five players per role are returned by default. If the current player is outside the top five in a given role, their row is appended with `rank: null` and `is_current_player: true`.
- AI players (identified by email addresses ending in `@quipflip.internal`) are excluded from all leaderboards.
- The scoring service caches leaderboard calculations in Redis for one hour (`leaderboard:weekly:v4`) and refreshes the cache automatically whenever a phraseset finalizes.
- The `generated_at` timestamp communicates when the snapshot was last recalculated so clients can defer refreshes when data is still fresh.
- Leaderboards are computed concurrently for performance optimization.

#### `GET /player/tutorial/status`
Get the tutorial status for the current player.

**Response:**
```json
{
  "tutorial_completed": false,
  "tutorial_progress": "dashboard",
  "tutorial_started_at": "2025-01-06T10:15:00Z",
  "tutorial_completed_at": null
}
```

**Notes:**
- `tutorial_progress` values: "not_started", "welcome", "dashboard", "prompt_round", "copy_round", "vote_round", "completed"
- New players start with "not_started"

#### `POST /player/tutorial/progress`
Update the tutorial progress for the current player.

**Request:**
```json
{
  "progress": "prompt_round"
}
```

**Response:**
```json
{
  "success": true,
  "tutorial_status": {
    "tutorial_completed": false,
    "tutorial_progress": "prompt_round",
    "tutorial_started_at": "2025-01-06T10:15:00Z",
    "tutorial_completed_at": null
  }
}
```

**Errors:**
- `400 Bad Request` - Invalid progress value

**Notes:**
- Setting progress to "completed" marks tutorial as complete
- First non-"not_started" progress sets `tutorial_started_at`

#### `POST /player/tutorial/reset`
Reset the tutorial progress (useful for testing or replaying tutorial).

**Response:**
```json
{
  "tutorial_completed": false,
  "tutorial_progress": "not_started",
  "tutorial_started_at": null,
  "tutorial_completed_at": null
}
```

#### `POST /player/password`
Change the player's password after validating the current password and strength requirements. Returns fresh tokens.

```json
{
  "message": "Password updated successfully.",
  "access_token": "<jwt access token>",
  "refresh_token": "<refresh token>",
  "expires_in": 7200,
  "token_type": "bearer"
}
```

#### `PATCH /player/email`
Update the player's email address (requires current password confirmation).

```json
{
  "email": "new.address@example.com"
}
```

#### `PATCH /player/username`
Update the player's username (requires current password confirmation). The username must be 3-80 characters and contain only alphanumeric characters and spaces. The backend ensures the canonical username (lowercase, alphanumeric only) is not already in use.

**Request Body:**
```json
{
  "new_username": "NewDisplayName",
  "password": "current_password"
}
```

**Response:**
```json
{
  "username": "NewDisplayName",
  "message": "Username updated successfully."
}
```

**Errors:**
- `401 Unauthorized` - `invalid_password`: Incorrect password
- `409 Conflict` - `username_taken`: Username already in use (case-insensitive)
- `422 Unprocessable Entity` - `invalid_username`: Username contains invalid characters or is too short

#### `DELETE /player/account`
Permanently delete the authenticated player's account, associated quests, rounds, and tokens. Responds with `204 No Content` on success and clears the refresh-token cookie.

---

### Round Endpoints

#### `POST /rounds/prompt`
Start a prompt round (-100f).

**Request Body:** _None_

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
- `insufficient_balance` - Balance < 100f
- `max_outstanding_quips` - Player has 10 open/closing phrasesets

#### `POST /rounds/copy`
Start a copy round (-50f or -40f).

**Request Body:** _None_

**Response:**
```json
{
  "round_id": "uuid",
  "original_phrase": "FAMOUS",
  "prompt_round_id": "uuid",
  "expires_at": "2025-01-06T12:36:00",
  "cost": 40,
  "discount_active": true
}
```

**Errors:**
- `no_prompts_available` - No prompts in queue
- `already_in_round` - Player already in active round
- `insufficient_balance` - Balance < cost

#### `POST /rounds/vote`
Start a vote round (-10f).

**Request Body:** _None_

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
- `no_phrasesets_available` - No phrasesets in queue
- `already_in_round` - Player already in active round
- `insufficient_balance` - Balance < 10f

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

#### `POST /rounds/{round_id}/abandon`
Immediately abandon an active prompt, copy, or vote round. The player receives an instant refund minus the configured abandonment penalty. Prompt rounds mark the phraseset as abandoned, copy rounds re-queue the prompt for other players, and vote rounds simply clear the active state.

**Request Body:** _None_

**Response:**
```json
{
  "round_id": "uuid",
  "round_type": "prompt",
  "status": "abandoned",
  "refund_amount": 95,
  "penalty_kept": 5,
  "message": "Round abandoned"
}
```

**Errors:**
- `round_not_found` - Round does not exist or belongs to another player
- `Round is not active` - Attempted to abandon a round that has already completed or expired
- `abandon_failed` - Unexpected server error while processing the abandonment

#### `POST /rounds/{round_id}/feedback`
Submit thumbs up/down feedback for a prompt round.

Feedback records persist to [PromptFeedback](DATA_MODELS.md#promptfeedback).

**Request Body:**
```json
{
  "feedback_type": "like"
}
```

**Response:**
```json
{
  "success": true,
  "feedback_type": "like",
  "message": "Feedback submitted successfully"
}
```

**Errors:**
- `not_found` - Round not found
- `forbidden` - Not authorized to submit feedback for this round
- `invalid_round_type` - Can only submit feedback for prompt rounds

**Notes:**
- Only works for prompt rounds
- Can update existing feedback (upsert behavior)
- `feedback_type` can be "like" or "dislike"

#### `GET /rounds/{round_id}/feedback`
Get existing feedback for a round.

**Response:**
```json
{
  "feedback_type": "like",
  "feedback_id": "uuid",
  "last_updated_at": "2025-01-06T12:00:00Z"
}
```

**Response (no feedback):**
```json
{
  "feedback_type": null,
  "feedback_id": null,
  "last_updated_at": null
}
```

### Survey Feedback Endpoints

Authenticated players can share structured beta feedback through the dedicated survey router.

#### `POST /feedback/beta-survey`
Submit a beta survey response for the current player.

**Request Body:**
```json
{
  "survey_id": "beta_oct_2025",
  "answers": [
    {
      "question_id": "q1",
      "value": 4
    },
    {
      "question_id": "q2",
      "value": ["prompt", "vote"]
    }
  ]
}
```

**Response (new submission):**
```json
{
  "status": "submitted",
  "message": "thank you"
}
```

**Response (duplicate submission):**
```json
{
  "status": "already_submitted",
  "message": "already submitted"
}
```

**Errors:**
- `unknown_survey` – request references an unrecognised survey ID

#### `GET /feedback/beta-survey/status`
Return eligibility + completion state for the current player.

**Response:**
```json
{
  "eligible": true,
  "has_submitted": false,
  "total_rounds": 12
}
```

#### `GET /feedback/beta-survey`
List the 100 most recent beta survey submissions. **Admin only.**

**Response:**
```json
{
  "submissions": [
    {
      "response_id": "uuid",
      "player_id": "uuid",
      "survey_id": "beta_oct_2025",
      "payload": {
        "answers": [
          {
            "question_id": "q1",
            "value": 4
          }
        ]
      },
      "created_at": "2025-01-06T12:00:00Z"
    }
  ]
}
```

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
  "copy_cost": 50,
  "current_round_id": null,
  "prompt_cost": 100,
  "vote_cost": 10,
  "vote_payout_correct": 20,
  "abandoned_penalty": 50
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

See [Round](DATA_MODELS.md#round-unified-for-prompt-copy-and-vote) for persisted round attributes.

---

### Phraseset Endpoints

Phraseset payloads map onto [Phraseset](DATA_MODELS.md#phraseset), [Vote](DATA_MODELS.md#vote), and [ResultView](DATA_MODELS.md#resultview) database records.

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
- `No active vote round` - Player has no active vote round
- `Not in a vote round` - Active round isn't a vote round
- `Phraseset does not match active round`

#### `GET /phrasesets/{phraseset_id}/details`
Get full contributor view for a phraseset the player participated in (contributor or voter).

**Access Control:** Restricted to contributors (prompt/copy submitters) and voters only.

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
    {"player_id": "uuid", "username": "Prompt Pirate", "pseudonym": "Prompt Pirate", "is_you": true, "phrase": "FAMOUS"},
    {"player_id": "uuid", "username": "Copy Cat", "pseudonym": "Copy Cat", "is_you": false, "phrase": "POPULAR"},
    {"player_id": "uuid", "username": "Shadow Scribe", "pseudonym": "Shadow Scribe", "is_you": false, "phrase": "WEALTHY"}
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
      "voter_pseudonym": "Voter 1",
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
  "result_viewed": true,
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
- `404 Phraseset not found` - Invalid phraseset ID
- `403 Not a contributor or voter for this phraseset` - Player did not participate in this phraseset

**Notes:**
- `results` is only populated when the phraseset status resolves to `finalized`
- Includes personal context fields: `your_role`, `your_phrase`, `your_payout`, `result_viewed`
- `is_you` flag indicates which contributor is the current player

#### `GET /phrasesets/{phraseset_id}/public-details`
Get full details for any COMPLETED phraseset (public access for browsing/reviewing).

**Access Control:** Public - anyone can view, but only for finalized phrasesets.

**Purpose:** This endpoint allows players to review any completed round from the completed phrasesets list, even if they didn't participate. Used by the phraseset review feature.

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
    {"player_id": "uuid", "username": "Prompt Pirate", "pseudonym": "Prompt Pirate", "is_you": false, "phrase": "FAMOUS"},
    {"player_id": "uuid", "username": "Copy Cat", "pseudonym": "Copy Cat", "is_you": false, "phrase": "POPULAR"},
    {"player_id": "uuid", "username": "Shadow Scribe", "pseudonym": "Shadow Scribe", "is_you": false, "phrase": "WEALTHY"}
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
      "voter_pseudonym": "Voter 1",
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
  "your_role": null,
  "your_phrase": null,
  "your_payout": null,
  "result_viewed": false,
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
- `404 Phraseset not found` - Invalid phraseset ID
- `403 Phraseset not finalized` - Can only view finalized phrasesets publicly

**Notes:**
- Only works for finalized phrasesets (status = "finalized")
- Does NOT require the player to be a contributor or voter
- Personal context fields are always null: `your_role`, `your_phrase`, `your_payout`
- `is_you` is always false in the contributors array (no personal context)
- `result_viewed` is always false (not tracking views for public access)
- `results` is always populated (since only finalized phrasesets are accessible)
- Use this endpoint when displaying phrasesets from the `/phrasesets/completed` list

#### `GET /phrasesets/{phraseset_id}/results`
Get phraseset results (collects prize on first view).

**Response:**
```json
{
  "prompt_text": "my deepest desire is to be (a/an)",
  "votes": [
    {"phrase": "FAMOUS", "vote_count": 3, "is_original": true},
    {"phrase": "POPULAR", "vote_count": 1, "is_original": false},
    {"phrase": "WEALTHY", "vote_count": 0, "is_original": false}
  ],
  "your_phrase": "FAMOUS",
  "your_role": "prompt",
  "your_points": 3,
  "total_points": 5,
  "your_payout": 108,
  "total_pool": 180,
  "total_votes": 4,
  "already_collected": true,
  "finalized_at": "2025-01-06T13:00:00Z",
  "correct_vote_count": 3,
  "incorrect_vote_count": 1,
  "correct_vote_points": 1,
  "incorrect_vote_points": 2,
  "prize_pool_base": 200,
  "vote_cost": 10,
  "vote_payout_correct": 20,
  "system_contribution": 0,
  "second_copy_contribution": 0
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

#### `GET /phrasesets/{phraseset_id}/history`
Get the complete event timeline for a phraseset, showing all submissions, votes, and finalization.

**Access Control:** This endpoint has two layers of access restriction:
1. **Finalized phrasesets only** - Active phrasesets cannot be viewed
2. **Participants only** - You must be a contributor (prompt/copy submitter) or voter

Attempting to view a non-finalized phraseset or a phraseset you didn't participate in will return a 403 error. This prevents players from viewing phrases and contributor identities before voting completes, and ensures privacy for participants.

**Purpose:** This endpoint provides a comprehensive review of a phraseset's lifecycle, making it ideal for building a detailed review UX that shows:
- Who submitted the original phrase and when
- When each copy was submitted and by whom
- The chronological sequence of votes with voter identities
- Whether each vote was correct or incorrect
- When the phraseset was finalized

**Response:**
```json
{
  "phraseset_id": "uuid",
  "prompt_text": "my deepest desire is to be (a/an)",
  "original_phrase": "FAMOUS",
  "copy_phrase_1": "POPULAR",
  "copy_phrase_2": "WEALTHY",
  "status": "finalized",
  "created_at": "2025-01-06T10:00:00Z",
  "finalized_at": "2025-01-06T12:30:00Z",
  "total_votes": 8,
  "events": [
    {
      "event_type": "prompt_submitted",
      "timestamp": "2025-01-06T10:00:00Z",
      "player_id": "uuid",
      "username": "Prompt Pirate",
      "pseudonym": "Prompt Pirate",
      "phrase": "FAMOUS",
      "correct": null,
      "metadata": {
        "round_id": "uuid",
        "prompt_text": "my deepest desire is to be (a/an)"
      }
    },
    {
      "event_type": "copy_submitted",
      "timestamp": "2025-01-06T10:15:00Z",
      "player_id": "uuid",
      "username": "Copy Cat",
      "pseudonym": "Copy Cat",
      "phrase": "POPULAR",
      "correct": null,
      "metadata": {
        "round_id": "uuid",
        "copy_number": 1
      }
    },
    {
      "event_type": "copy_submitted",
      "timestamp": "2025-01-06T10:18:00Z",
      "player_id": "uuid",
      "username": "Shadow Scribe",
      "pseudonym": "Shadow Scribe",
      "phrase": "WEALTHY",
      "correct": null,
      "metadata": {
        "round_id": "uuid",
        "copy_number": 2
      }
    },
    {
      "event_type": "vote_submitted",
      "timestamp": "2025-01-06T11:00:00Z",
      "player_id": "uuid",
      "username": "Voter One",
      "pseudonym": "Voter One",
      "phrase": "FAMOUS",
      "correct": true,
      "metadata": {
        "vote_id": "uuid",
        "payout": 20
      }
    },
    {
      "event_type": "vote_submitted",
      "timestamp": "2025-01-06T11:05:00Z",
      "player_id": "uuid",
      "username": "Voter Two",
      "pseudonym": "Voter Two",
      "phrase": "POPULAR",
      "correct": false,
      "metadata": {
        "vote_id": "uuid",
        "payout": 0
      }
    },
    {
      "event_type": "finalized",
      "timestamp": "2025-01-06T12:30:00Z",
      "player_id": null,
      "username": null,
      "pseudonym": null,
      "phrase": null,
      "correct": null,
      "metadata": {
        "total_votes": 8,
        "total_pool": 300
      }
    }
  ]
}
```

**Event Types:**
- `prompt_submitted` - Original phrase submission
- `copy_submitted` - Copy phrase submission (includes `copy_number` in metadata: 1 or 2)
- `vote_submitted` - Vote cast (includes `correct` field and vote payout in metadata)
- `finalized` - Phraseset completed and prizes distributed

**Notes:**
- Events are returned in chronological order
- All events include UTC timestamps
- Both `username` (for debugging) and `pseudonym` (for display) are included
- Vote events include the `correct` boolean indicating if the voter chose the original phrase
- The `metadata` field contains event-specific additional information
- Only finalized phrasesets will have a `finalized` event

**Errors:**
- `404 Not Found` - Phraseset not found
- `403 Forbidden` - Either the phraseset is not finalized (still active/voting) OR you are not a participant
- `400 Bad Request` - Invalid phraseset ID format

**Security Notes:**
- **Finalization requirement:** Only finalized phrasesets can be viewed, preventing:
  - Viewing the original phrase before voting (unfair advantage)
  - Seeing copy phrases and contributors during active voting
  - Real-time tracking of vote patterns before finalization
- **Participant requirement:** Only contributors and voters can view history, ensuring privacy
- **Handles incomplete phrasesets:** If a phraseset was abandoned before all rounds completed, only the completed events will be shown

#### `GET /phrasesets/completed`
Get a list of finalized phrasesets with summary metadata.

**Purpose:** This endpoint allows browsing through completed rounds to select which ones to review in detail. Use it to build a list/grid UI showing all finished games. The original phrase is intentionally excluded to preserve the mystery for players who weren't involved in the round.

**Query Parameters:**
- `limit` (optional, default: 10) - Ignored, kept for API compatibility
- `offset` (optional, default: 0) - Ignored, kept for API compatibility

**Important:** This endpoint returns up to 500 phrasesets. All pagination and sorting should be handled client-side.

**Response:**
```json
{
  "phrasesets": [
    {
      "phraseset_id": "uuid",
      "prompt_text": "my deepest desire is to be (a/an)",
      "created_at": "2025-01-06T10:00:00Z",
      "finalized_at": "2025-01-06T12:30:00Z",
      "vote_count": 8,
      "total_pool": 300
    },
    {
      "phraseset_id": "uuid",
      "prompt_text": "the secret to happiness is (a/an)",
      "created_at": "2025-01-05T14:20:00Z",
      "finalized_at": "2025-01-05T16:45:00Z",
      "vote_count": 12,
      "total_pool": 350
    }
  ]
}
```

**Notes:**
- Returns up to 500 phrasesets maximum
- When ≤ 500 total: Results ordered by finalization time (most recent first)
- When > 500 total: Prioritizes phrasesets with least AI player involvement, then by finalization time
  - AI players identified by email ending with `@quipflip.internal`
  - Sorts by: AI contributor count ASC, AI voter count ASC, finalized_at DESC
  - This ensures human-created rounds are prioritized over AI-generated rounds
- Only includes phrasesets with status = "finalized"
- Timestamps are in UTC ISO 8601 format
- `created_at` is when the original prompt was submitted
- `finalized_at` is when voting completed and prizes were distributed
- `total_pool` is the final prize pool amount distributed to contributors
- `original_phrase` is NOT included in this response (preserves mystery for non-participants)
- **No total count provided** - client receives up to 500 items for client-side handling

**Example Usage:**
```bash
# Fetch all available completed phrasesets (up to 500)
GET /phrasesets/completed

# Same result (limit/offset ignored)
GET /phrasesets/completed?limit=500&offset=0
```

**Client-Side Implementation:**
```typescript
// Fetch all available rounds once
const response = await fetch('/phrasesets/completed');
const { phrasesets } = await response.json();

// Implement sorting and pagination in the UI
const sorted = phrasesets.sort((a, b) => /* custom sort */);
const page1 = sorted.slice(0, 10);   // First 10 items
const page2 = sorted.slice(10, 20);  // Next 10 items
```

**Use Cases:**
- Building a "Browse Completed Rounds" page with client-side sorting/filtering
- Creating a review history UI with custom sort options
- Showing recent activity to players
- Allowing players to revisit and analyze past rounds

---

### Quest Endpoints

Quest responses correspond to [Quest](DATA_MODELS.md#quest) rows (with extra derived fields) and reference configuration stored in `quest_templates` (see [QuestTemplate](DATA_MODELS.md#questtemplate)).

#### `GET /quests`
Get all quests for the current player.

**Response:**
```json
{
  "quests": [
    {
      "quest_id": "uuid",
      "quest_type": "daily_login_streak",
      "name": "Daily Login Streak",
      "description": "Log in for consecutive days",
      "status": "active",
      "progress": {
        "current_streak": 3,
        "target": 7
      },
      "reward_amount": 50,
      "category": "daily",
      "created_at": "2025-01-06T10:00:00Z",
      "completed_at": null,
      "claimed_at": null,
      "progress_percentage": 42.8,
      "progress_current": 3,
      "progress_target": 7
    }
  ],
  "total_count": 5,
  "active_count": 3,
  "completed_count": 1,
  "claimed_count": 1,
  "claimable_count": 1
}
```

**Notes:**
- Returns all quests for the player regardless of status
- `status` can be "active", "completed", or "claimed"
- `progress_percentage` is calculated as (current/target) * 100, capped at 100
- Quest types include daily challenges, milestones, and achievements

#### `GET /quests/active`
Get only active quests for the current player.

**Response:**
```json
[
  {
    "quest_id": "uuid",
    "quest_type": "daily_login_streak",
    "name": "Daily Login Streak",
    "description": "Log in for consecutive days",
    "status": "active",
    "progress": {
      "current_streak": 3,
      "target": 7
    },
    "reward_amount": 50,
    "category": "daily",
    "created_at": "2025-01-06T10:00:00Z",
    "completed_at": null,
    "claimed_at": null,
    "progress_percentage": 42.8,
    "progress_current": 3,
    "progress_target": 7
  }
]
```

#### `GET /quests/claimable`
Get completed but unclaimed quests for the current player.

**Response:**
```json
[
  {
    "quest_id": "uuid",
    "quest_type": "first_prompt",
    "name": "First Prompt",
    "description": "Submit your first prompt",
    "status": "completed",
    "progress": {
      "rounds_completed": 1,
      "target": 1
    },
    "reward_amount": 25,
    "category": "milestone",
    "created_at": "2025-01-06T10:00:00Z",
    "completed_at": "2025-01-06T11:30:00Z",
    "claimed_at": null,
    "progress_percentage": 100,
    "progress_current": 1,
    "progress_target": 1
  }
]
```

#### `GET /quests/active`
List only active quests (status = `active`). Response shape matches `GET /quests` but filters to active entries.

#### `GET /quests/claimable`
List quests that are completed but not yet claimed. Useful for badge counters in the client.

#### `GET /quests/{quest_id}`
Get a single quest by ID.

**Response:**
```json
{
  "quest_id": "uuid",
  "quest_type": "daily_login_streak",
  "name": "Daily Login Streak",
  "description": "Log in for consecutive days",
  "status": "active",
  "progress": {
    "current_streak": 3,
    "target": 7
  },
  "reward_amount": 50,
  "category": "daily",
  "created_at": "2025-01-06T10:00:00Z",
  "completed_at": null,
  "claimed_at": null,
  "progress_percentage": 42.8,
  "progress_current": 3,
  "progress_target": 7
}
```

**Errors:**
- `404 Not Found` - Quest not found
- `403 Forbidden` - Not authorized to view this quest

#### `POST /quests/{quest_id}/claim`
Claim a completed quest reward.

**Response:**
```json
{
  "success": true,
  "quest_id": "uuid",
  "reward_amount": 25,
  "new_balance": 1125,
  "message": "Quest reward claimed successfully!"
}
```

**Errors:**
- `404 Not Found` - Quest not found
- `400 Bad Request` - Quest not completed yet
- `409 Conflict` - Quest reward already claimed

**Notes:**
- Only completed quests can be claimed
- Claiming a quest adds the reward amount to player balance
- Quest status changes from "completed" to "claimed"
- Operation is idempotent - claiming an already claimed quest returns success

---

### Admin Endpoints

Admin endpoints allow authorized users to view and modify game configuration. Authentication is required for all admin endpoints.

#### `GET /admin/config`
Get current game configuration values (from database overrides or environment defaults).

**Response:**
```json
{
  "starting_balance": 5000,
  "daily_bonus_amount": 100,
  "prompt_cost": 100,
  "copy_cost_normal": 50,
  "copy_cost_discount": 40,
  "vote_cost": 10,
  "vote_payout_correct": 20,
  "abandoned_penalty": 5,
  "prize_pool_base": 200,
  "max_outstanding_quips": 10,
  "copy_discount_threshold": 10,
  "prompt_round_seconds": 180,
  "copy_round_seconds": 180,
  "vote_round_seconds": 60,
  "grace_period_seconds": 5,
  "vote_max_votes": 20,
  "vote_closing_threshold": 5,
  "vote_closing_window_minutes": 1,
  "vote_minimum_threshold": 3,
  "vote_minimum_window_minutes": 10,
  "phrase_min_words": 2,
  "phrase_max_words": 5,
  "phrase_max_length": 100,
  "phrase_min_char_per_word": 2,
  "phrase_max_char_per_word": 15,
  "significant_word_min_length": 4,
  "ai_provider": "openai",
  "ai_openai_model": "gpt-5-nano",
  "ai_gemini_model": "gemini-2.5-flash-lite",
  "ai_timeout_seconds": 30,
  "ai_backup_delay_minutes": 15,
  "ai_backup_batch_size": 3,
  "ai_backup_sleep_minutes": 60,
  "ai_stale_handler_enabled": true,
  "ai_stale_threshold_days": 3,
  "ai_stale_check_interval_hours": 12
}
```

**Notes:**
- Returns all configurable game settings
- Values may come from database overrides or environment defaults
- New fields added for stale AI handler:
  - `ai_stale_handler_enabled` - Enable/disable stale content handler (default: true)
  - `ai_stale_threshold_days` - Days before content is considered stale (minimum 3, default: 3)
  - `ai_stale_check_interval_hours` - Hours between stale handler cycles (minimum 1, default: 12)

#### `PATCH /admin/config`
Update a game configuration value. Requires admin password validation.

**Request:**
```json
{
  "config_key": "ai_stale_threshold_days",
  "config_value": 5
}
```

**Response:**
```json
{
  "success": true,
  "message": "Configuration updated successfully",
  "updated_key": "ai_stale_threshold_days",
  "new_value": 5
}
```

**Errors:**
- `400 Bad Request` - Invalid configuration key or value
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Not authorized (admin access required)
- `422 Validation Error` - Value fails validation (e.g., ai_stale_threshold_days < 3)

**Notes:**
- All configuration changes are persisted to the database
- Changes take effect immediately for new rounds/operations
- Validation rules are enforced (e.g., minimum values, data types)
- See [Game Rules](GAME_RULES.md) for detailed explanation of each setting

---

## Example Workflows

### Complete Game Flow

```bash
# 1. Check balance
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/player/balance

# 2. Start prompt round
curl -X POST -H "Authorization: Bearer <access_token>" http://localhost:8000/rounds/prompt

# 3. Submit phrase
curl -X POST -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"phrase":"famous"}' \
  http://localhost:8000/rounds/{round_id}/submit

# 4. Start copy round (as different player)
curl -X POST -H "Authorization: Bearer <other_access_token>" http://localhost:8000/rounds/copy

# 5. Submit copy word
curl -X POST -H "Authorization: Bearer <other_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"phrase":"popular"}' \
  http://localhost:8000/rounds/{round_id}/submit

# 6. Start vote round (after 2 copies submitted)
curl -X POST -H "Authorization: Bearer <voter_access_token>" http://localhost:8000/rounds/vote

# 7. Submit vote
curl -X POST -H "Authorization: Bearer <voter_access_token>" \
  -H "Content-Type: application/json" \
  -d '{"phrase":"FAMOUS"}' \
  http://localhost:8000/phrasesets/{phraseset_id}/vote

# 8. View results (after finalization)
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/phrasesets/{phraseset_id}/results
```

---

## Rate Limiting

Per-player rate limiting is enforced via Redis:

- General authenticated traffic: 100 requests per 60-second window (scoped to player ID).
- Vote submissions: 20 votes per 60-second window (stricter dependency on `/phrasesets/{phraseset_id}/vote`).

Clients should surface friendly messaging for `429 Too Many Requests` responses and honour the optional `Retry-After` header.

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
- **Starting balance**: 5000f
- **Daily bonus**: 100f
- **Prompt cost**: 100f
- **Copy cost**: 50f normal, 40f with discount
- **Vote cost**: 10f
- **Vote payout (correct)**: 20f
- **Phraseset prize pool**: 200f base (plus copy/vote contributions)
- **Copy discount threshold**: >10 prompts waiting
- **Max outstanding prompts**: 10 per player

### Validation
- **Word length**: 2-15 characters
- **Word format**: Letters A-Z only (case insensitive, stored uppercase)
- **Dictionary**: NASPA word list
- **Copy validation**: Must differ from original phrase

### Phraseset Voting Lifecycle
1. **Open**: 0-2 votes submitted
2. **Closing**: 3+ votes, 10-minute window starts
3. **Rapid closing**: 5+ votes, 60-second window starts
4. **Closed**: Window expired, no new votes
5. **Finalized**: Results calculated, prizes distributed

### Prize Distribution
- Prize pool split among prompt + 2 copy contributors
- Share proportional to votes received for your word
- System contributes 10f if copy used discount pricing

## Frontend Integration

### CORS
CORS is enabled for all origins in development. For production:
- Configure `CORS_ORIGINS` environment variable
- **Important**: Set `withCredentials: true` in axios/fetch to send HTTP-only cookies
- Example: `axios.create({ baseURL: API_URL, withCredentials: true })`

### State Management
**Required state to track:**
- Username (stored in localStorage for session persistence check)
- Authentication state (derived from successful API calls, not stored)
- Current balance (update from `/player/balance`)
- Active round state (poll `/player/current-round` or update after actions)
- Pending results count (from `/player/pending-results`)

**Note**: Tokens are now stored in HTTP-only cookies and managed by the browser automatically. The frontend no longer needs to handle token storage or refresh logic.

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
1. **First visit**: Call `POST /player` or `POST /player/guest` → cookies set automatically, store username in localStorage
2. **Return visit**: Check localStorage for username → call `GET /player/balance` to verify session (cookies sent automatically)
3. **Token expires**: Cookies handle refresh automatically, or call `POST /auth/refresh` if needed
4. **Check daily bonus**: If `daily_bonus_available` → offer to claim
5. **Start round**: Check `GET /rounds/available` → start desired round type
6. **During round**: Display timer, submit word before expiry
7. **Check results**: Poll `/player/pending-results` → view when ready
8. **Logout**: Call `POST /auth/logout` → cookies cleared automatically

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
- All currency amounts in whole Flipcoins (integer values: 100 = 100f)
- Words automatically converted to uppercase
- Grace period allows submissions up to 5 seconds past expiry
- `/docs` and `/redoc` provide interactive API testing
