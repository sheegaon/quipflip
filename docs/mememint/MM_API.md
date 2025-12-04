# Meme Mint (MM) API Documentation

Meme Mint endpoints live under the `/mm` prefix and are implemented in `backend/routers/mm`. Shared authentication and health/status probes are documented in [API.md](../API.md); this guide focuses on Meme Mint gameplay and account endpoints.

## Base URL

```
Development: http://localhost:8000/mm
```

## Authentication

Meme Mint uses the shared authentication contract from [API.md](../API.md). Authentication is **global**; include `game_type=mm` on auth/session calls to receive Meme Mint balances/tutorial flags in the `game_data` envelope.

- HTTP-only cookies are set on login/refresh using the configured `access_token_cookie_name` and `refresh_token_cookie_name` (defaults mirror Quipflip).
- Authorization headers (`Bearer <token>`) are also accepted by the MM auth dependency.
- Most endpoints require authentication; unauthenticated access is only allowed where noted (e.g., registration and guest creation).
- `GET /auth/session?game_type=mm` is the preferred way to bootstrap the current player state without assuming a default game.

## Data Model Reference

Game-specific schemas are defined in [MM_DATA_MODELS.md](MM_DATA_MODELS.md). Player balances, rounds, and leaderboard entries described below reuse those schemas; this guide focuses on HTTP payloads.

## Response Format

Meme Mint uses the same success and error envelope described in [API.md](../API.md). Error payloads surface via the `detail` field with appropriate HTTP status codes (400 for business rule violations such as insufficient balance, 404 when resources are missing, etc.).

---

## Player & Account Endpoints (`/mm/player`)

These endpoints extend the shared player router and issue JWT cookies for authentication.

### `POST /player`
Create a new Meme Mint account. Returns tokens, player identifiers, and starting balances configured via `SystemConfigBase` overrides.

### `POST /player/guest`
Create a guest player with auto-generated credentials and issued auth cookies. The response includes the generated email/password along with wallet and vault balances.

### `POST /player/upgrade`
Convert a guest account to a full account by supplying an email and password. Issues fresh access and refresh tokens on success.

### `POST /player/login`
Authenticate by email/password or username/password. Returns new tokens and balance information. Cookies are set automatically in browser clients.

### `POST /player/refresh`
Rotate access and refresh tokens. Accepts the refresh token from the request body or the refresh cookie.

### `POST /player/logout`
Revoke the refresh token, clear auth cookies, and remove the player from active sessions.

### `POST /player/password`
Change the current player's password after verifying credentials. Issues new tokens as part of the response.

### `PATCH /player/email`
Update the player's email address. Requires authentication.

### `PATCH /player/username`
Update the player's username. Validation errors return `422` with the validation message in `detail`.

### `DELETE /player/account`
Delete the authenticated player's account and associated data. Clears cookies on success.

### `GET /player/me` and `GET /player/balance`
Return the current player's Meme Mint balance using the shared `PlayerBalance` schema enriched with:
- `daily_bonus_available` – whether the player can claim the daily reward
- `daily_bonus_amount` – configured reward size
- `starting_balance` – game-specific starting funds
- `flag_dismissal_streak`, `locked_until`, `is_guest`, and timestamps (`created_at`, `last_login_date`)

### `POST /player/claim-daily-bonus`
Attempt to claim the daily bonus. On success returns the claimed amount plus updated wallet and vault balances. Returns `400` if the bonus has already been claimed for the day.

### `GET /player/daily-state`
Report the player's remaining free caption submissions for the current day and the configured per-day allowance.

**Response:**
```json
{
  "free_captions_remaining": 1,
  "free_captions_per_day": 1
}
```

### `GET /player/config`
Expose client-facing configuration derived from `SystemConfigBase`, including round entry cost, caption submission cost, free caption quota, captions per round, house rake percentage, and the daily bonus amount.

### `GET /player/dashboard`
Return a batched payload optimized for the dashboard. Data is cached for 10 seconds per player and includes:
- `player` – the same payload as `/player/balance`
- `round_availability` – voting/caption permissions, costs, remaining free captions, and bonus eligibility
- `current_vote_round` and `current_caption_round` – always `null` in the current implementation because Meme Mint does not track active rounds on the player record

---

## Rounds Endpoints (`/mm/rounds` prefix)

### `POST /rounds/vote`
Start a vote round. Charges the configured entry cost and returns the chosen image plus a list of captions to vote on.

**Response:**
```json
{
  "round_id": "3f8f4f7a-5f8b-4f6e-9a66-6b7a2f2c9c1f",
  "image_id": "2c5f3c8d-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
  "image_url": "https://.../mm_images/example.png",
  "thumbnail_url": "https://.../mm_images/thumb_example.png",
  "attribution_text": "Photo by ...",
  "captions": [
    { "caption_id": "...", "text": "Sample caption" }
  ],
  "expires_at": "2024-01-01T12:00:00Z",
  "cost": 5
}
```

Returns `400` if no eligible content exists or the player lacks funds.

### `POST /rounds/vote/{round_id}/submit`
Submit a vote for a caption shown in a vote round. Rejects duplicate submissions and expired rounds.

**Request:**
```json
{ "caption_id": "f1f2f3f4-f5f6-4f7f-8f9f-0f1f2f3f4f5f" }
```

**Response:**
```json
{
  "success": true,
  "chosen_caption_id": "f1f2f3f4-f5f6-4f7f-8f9f-0f1f2f3f4f5f",
  "payout": 2,
  "correct": true,
  "new_wallet": 17,
  "new_vault": 4
}
```

### `POST /rounds/caption`
Submit a caption for the image associated with a prior vote round. The first caption each day is free; subsequent submissions cost the configured caption fee unless free slots remain. Supports `original` and `riff` caption types with optional `parent_caption_id` for riffs.

**Request:**
```json
{
  "round_id": "3f8f4f7a-5f8b-4f6e-9a66-6b7a2f2c9c1f",
  "text": "Your meme caption",
  "kind": "original",
  "parent_caption_id": null
}
```

**Response:**
```json
{
  "success": true,
  "caption_id": "9e6d6b68-5c73-4d4d-9c1a-9b0a1c2d3e4f",
  "cost": 0,
  "used_free_slot": true,
  "new_wallet": 20
}
```

Returns `400` for validation errors, insufficient balance, or missing rounds.

### `GET /rounds/available`
Report whether the player can start a vote round or submit a caption, along with current cost settings, remaining free captions, and bonus availability.

**Response:**
```json
{
  "can_vote": true,
  "can_submit_caption": true,
  "current_round_id": null,
  "round_entry_cost": 5,
  "caption_submission_cost": 10,
  "free_captions_remaining": 1,
  "daily_bonus_available": true
}
```

### `GET /rounds/{round_id}`
Retrieve details for a previously started round owned by the requesting player. Returns image metadata, captions shown, chosen caption (if already submitted), and status (`active` or `completed`).

**Response:**
```json
{
  "round_id": "3f8f4f7a-5f8b-4f6e-9a66-6b7a2f2c9c1f",
  "type": "vote",
  "status": "active",
  "expires_at": "2024-01-01T12:00:00Z",
  "image_id": "2c5f3c8d-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
  "image_url": "https://.../mm_images/example.png",
  "cost": 5,
  "captions": [
    { "caption_id": "...", "text": "Sample caption" }
  ],
  "chosen_caption_id": null
}
```

---

## Circles Endpoints (`/mm/circles` prefix)

Circles (groups) allow players to organize, share memes, and collaborate within the Meme Mint community. Players can create circles, invite members, and participate in shared meme activities.

### `POST /circles`
Create a new circle (group).

**Request:**
```json
{
  "name": "Meme Squad",
  "description": "Our circle for sharing the best memes"
}
```

**Response (201 Created):**
```json
{
  "circle_id": "uuid",
  "name": "Meme Squad",
  "description": "Our circle for sharing the best memes",
  "creator_id": "uuid",
  "created_at": "2024-01-06T12:00:00Z",
  "member_count": 1,
  "is_member": true,
  "is_creator": true
}
```

### `GET /circles`
List all circles the current player belongs to or has created.

**Response:**
```json
{
  "circles": [
    {
      "circle_id": "uuid",
      "name": "Meme Squad",
      "description": "Our circle for sharing the best memes",
      "creator_id": "uuid",
      "created_at": "2024-01-06T12:00:00Z",
      "member_count": 5,
      "is_member": true,
      "is_creator": true
    }
  ]
}
```

### `GET /circles/{circle_id}`
Get detailed information about a specific circle.

**Response:**
```json
{
  "circle_id": "uuid",
  "name": "Meme Squad",
  "description": "Our circle for sharing the best memes",
  "creator_id": "uuid",
  "created_at": "2024-01-06T12:00:00Z",
  "member_count": 5,
  "is_member": true,
  "is_creator": false
}
```

**Errors:**
- `404 Circle not found` - Invalid circle ID

### `POST /circles/{circle_id}/join`
Request to join a circle. Requires approval from a circle admin/creator.

**Response:**
```json
{
  "success": true,
  "message": "Join request sent"
}
```

**Errors:**
- `404 Circle not found` - Invalid circle ID
- `409 Already a member` - Player is already in the circle
- `409 Request pending` - Join request already submitted

### `GET /circles/{circle_id}/members`
List all members in a circle. Requires membership.

**Response:**
```json
{
  "members": [
    {
      "player_id": "uuid",
      "username": "Meme Master",
      "joined_at": "2024-01-01T10:00:00Z",
      "is_creator": true
    }
  ]
}
```

**Errors:**
- `403 Forbidden` - Not a member of this circle

### `POST /circles/{circle_id}/members`
Add a member to the circle (creator/admin only).

**Request:**
```json
{
  "player_id": "uuid"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Member added"
}
```

**Errors:**
- `403 Forbidden` - Only circle creator can add members
- `404 Player not found` - Invalid player ID

### `DELETE /circles/{circle_id}/members/{player_id}`
Remove a member from the circle (creator/admin only).

**Response:**
```json
{
  "success": true,
  "message": "Member removed"
}
```

**Errors:**
- `403 Forbidden` - Only circle creator can remove members
- `404 Member not found` - Player not in circle

### `DELETE /circles/{circle_id}/leave`
Leave a circle. The creator cannot leave their own circle.

**Response:**
```json
{
  "success": true,
  "message": "Left circle"
}
```

**Errors:**
- `400 Creator cannot leave` - Circle creator must delete the circle instead
- `404 Not a member` - Player is not in the circle

### `GET /circles/{circle_id}/join-requests`
List pending join requests for a circle (creator/admin only).

**Response:**
```json
{
  "requests": [
    {
      "request_id": "uuid",
      "player_id": "uuid",
      "player_username": "Meme Lover",
      "requested_at": "2024-01-06T11:00:00Z"
    }
  ]
}
```

**Errors:**
- `403 Forbidden` - Only circle creator can view join requests

### `POST /circles/{circle_id}/join-requests/{request_id}/approve`
Approve a pending join request (creator/admin only).

**Response:**
```json
{
  "success": true,
  "message": "Join request approved",
  "player_username": "Meme Lover"
}
```

**Errors:**
- `403 Forbidden` - Only circle creator can approve requests
- `404 Request not found` - Invalid request ID

### `POST /circles/{circle_id}/join-requests/{request_id}/deny`
Deny a pending join request (creator/admin only).

**Response:**
```json
{
  "success": true,
  "message": "Join request denied"
}
```

**Errors:**
- `403 Forbidden` - Only circle creator can deny requests
- `404 Request not found` - Invalid request ID

---

## Image Endpoint (`/mm/images` prefix)

### `GET /images/{filename}`
Serve a Meme Mint image. In production the endpoint issues a `302` redirect to the GitHub-hosted asset with caching headers; in local development it serves the file directly from `backend/data/mm_images`. Requests with path traversal patterns return `400`, and missing files return `404`.
