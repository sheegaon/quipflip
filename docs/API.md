# API Documentation Index

The backend now mirrors the code split between shared infrastructure and game-specific routers.

- [Quipflip (QF) API](QF_API.md) – endpoints mounted under `/qf/*` and implemented in `backend/routers/qf`.
- [Initial Reaction (IR) API](IR_API.md) – endpoints mounted under `/ir/*` and implemented in `backend/routers/ir`.

## Shared Endpoints

Authentication, health checks, and WebSocket token exchange are defined once in `backend/routers` and reused by both games:

- `GET /health` and `GET /status` for service monitoring and discovery.
- `POST /auth/login`, `POST /auth/login/username`, `POST /auth/refresh`, `POST /auth/logout` for cookie-backed JWTs.
- `GET /auth/suggest-username`, `GET /auth/ws-token` for username generation and WebSocket authentication.

Refer to each game guide for gameplay-specific routes and payloads. Both games share the same authentication contract and HTTP error envelope.

## Authentication Endpoints

### POST /auth/login
Authenticate a player via email/password and issue JWT tokens.

**Request Body:**
```json
{
  "email": "player@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "player_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "CosmicPanda42"
}
```

**HTTP Status Codes:**
- `200` - Login successful, tokens issued
- `401` - Invalid credentials or authentication failure
- `422` - Invalid request format

**Error Messages:**
- `invalid_credentials` - Email/password combination not found
- `account_locked` - Player account is temporarily suspended
- `validation_error` - Request body validation failed

**Cookies Set:**
- `access_token` (HttpOnly, Secure) - JWT access token
- `refresh_token` (HttpOnly, Secure) - Long-lived refresh token

### POST /auth/login/username
Authenticate a player via username/password and issue JWT tokens.

**Request Body:**
```json
{
  "username": "CosmicPanda42",
  "password": "securepassword123"
}
```

**Response (200):** Same as `/auth/login`

**HTTP Status Codes:** Same as `/auth/login`

**Error Messages:** Same as `/auth/login`

### GET /auth/suggest-username
Generate a suggested username for registration.

**Request:** No body required

**Response (200):**
```json
{
  "suggested_username": "MysticOwl89"
}
```

**HTTP Status Codes:**
- `200` - Username generated successfully

### POST /auth/refresh
Exchange a refresh token for new JWT credentials.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Alternative:** Can use refresh token from HttpOnly cookie instead of request body

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "player_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "CosmicPanda42"
}
```

**HTTP Status Codes:**
- `200` - Token refresh successful
- `401` - Invalid, expired, or revoked refresh token
- `422` - Invalid request format

**Error Messages:**
- `missing_refresh_token` - No refresh token provided in request or cookie
- `invalid_refresh_token` - Token is malformed, expired, or revoked
- `token_not_found` - Refresh token not found in database

**Cookies Updated:**
- `access_token` (HttpOnly, Secure) - New JWT access token
- `refresh_token` (HttpOnly, Secure) - New refresh token (rotation)

### POST /auth/logout
Invalidate refresh token, clean up sessions, and clear cookies.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Alternative:** Can use refresh token from HttpOnly cookie instead of request body

**Response:** No content (204)

**HTTP Status Codes:**
- `204` - Logout successful, cookies cleared
- `422` - Invalid request format

**Side Effects:**
- Refresh token is revoked in database
- Player is removed from all active party sessions
- Auth cookies are cleared from browser

**Cookies Cleared:**
- `access_token` - Removed
- `refresh_token` - Removed

### GET /auth/ws-token
Generate a short-lived token for WebSocket authentication.

**Authentication:** Requires valid JWT access token (HttpOnly cookie)

**Request:** No body required

**Response (200):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 60,
  "token_type": "bearer"
}
```

**HTTP Status Codes:**
- `200` - WebSocket token generated
- `401` - Invalid or missing access token

**Purpose:** Provides short-lived (60-second) tokens for WebSocket connections to bypass cookie limitations in WebSocket handshakes.

## Health & Status Endpoints

### GET /health
Basic health check for load balancers and monitoring systems.

**Request:** No body required

**Response (200):**
```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected"
}
```

**Response (503) - Service Unavailable:**
```json
{
  "status": "error",
  "detail": "Database connection failed"
}
```

**HTTP Status Codes:**
- `200` - All systems healthy
- `503` - Critical system failure (database unreachable)

**Health Checks:**
- Database connectivity test via `SELECT 1`
- Redis queue backend status check

### GET /status
Comprehensive system status including version and phrase validation.

**Request:** No body required

**Response (200):**
```json
{
  "version": "1.2.3",
  "environment": "production",
  "phrase_validation": {
    "mode": "remote",
    "healthy": true
  }
}
```

**HTTP Status Codes:**
- `200` - Status retrieved successfully

**Status Information:**
- `version` - Current application version from version.py
- `environment` - Deployment environment (development/staging/production)
- `phrase_validation.mode` - Validation mode ("remote" for API, "local" for dictionary file)
- `phrase_validation.healthy` - Whether phrase validation system is operational

**Phrase Validation Health:**
- **Remote mode**: Tests connectivity to phrase validation API service
- **Local mode**: Verifies dictionary file is loaded and accessible

## Common Error Response Format

All endpoints use a consistent error response structure:

```json
{
  "detail": "error_code_or_message"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `204` - Success with no content
- `400` - Bad request (client error)
- `401` - Unauthorized (authentication required/failed)
- `403` - Forbidden (insufficient permissions)
- `404` - Not found
- `422` - Unprocessable entity (validation error)
- `429` - Too many requests (rate limited)
- `500` - Internal server error
- `503` - Service unavailable

**Authentication Required:**
Most game-specific endpoints require a valid JWT access token provided via:
- `Authorization: Bearer <token>` header, or
- `access_token` HttpOnly cookie (recommended for web clients)

**Rate Limiting:**
Some endpoints may implement rate limiting with standard HTTP 429 responses and `Retry-After` headers.
