# WebSocket Integration

This document captures the current WebSocket architecture across the Quipflip backend and frontend.

## Authentication Handshake
- Clients fetch a short-lived token from `GET /qf/auth/ws-token` before connecting.
- The frontend helper builds WebSocket URLs by converting the REST base URL to `ws(s)://` and appending the `token` query param.
- All Quipflip WebSocket endpoints expect that token and reject missing/invalid tokens with a `1008` close code.
- Tokens are requested only while authenticated. Pending token requests are canceled and sockets are closed as soon as the user logs out to avoid extra `/qf/auth/ws-token` calls.

## Frontend Connection Management
- `useWebSocket(path, options)` pools connections per `path`, multiplexes listeners, and performs exponential-backoff reconnects when listeners opt in.
- Each connection request includes a token fetch; any outstanding fetch is aborted when listeners disable a path (e.g., on logout).
- Connections are created for a path only when at least one listener is `enabled`. When no enabled listeners remain, the hook clears reconnection timers and closes the socket.
- The `NotificationProvider` lives above route components so WebSockets stay mounted during navigation and are torn down only when authentication is lost.

## Channels
### Notifications
- **Endpoint:** `GET /qf/notifications/ws?token=...`
- **Messages:**
  - `notification` — `{ notification_type, actor_username, action, recipient_role, phrase_text, timestamp }`
  - `ping` — `{ from_username, timestamp, join_url? }` (party invitations or direct pings)
- **Frontend:**
  - `NotificationProvider` subscribes when authenticated, adds toast notifications, and records ping toasts.
  - Errors are logged quietly; no REST polling fallback is used for this channel.

### Online Users
- **Endpoint:** `GET /qf/users/online/ws?token=...`
- **Messages:** `online_users_update` payloads with `{ users, total_count, timestamp }`.
- **Frontend:**
  - The provider connects when authenticated to keep connection state and user lists.
  - On close with code `1008`, the provider stops reconnecting and surfaces an auth error.
  - On connection issues, it falls back to REST polling (`GET /qf/users/online`) every 10 seconds until the socket is healthy again.
  - Ping actions use the REST helper `pingOnlineUser(username)` to send a lightweight ping via the backend connection manager.

### Party Mode
- **Endpoint:** `GET /qf/party/{sessionId}/ws?token=...`
- **Messages:** read-only notifications such as `player_joined`, `player_left`, `player_ready`, `round_started`, `round_completed`, `submission`, `session_status`, and `error`.
- **Frontend:**
  - `usePartyWebSocket` wraps `useWebSocket` for presence and progress notifications only; the actual party flow (starting rounds, submitting, switching phases) is driven by REST endpoints and status polling (e.g., `GET /party/{id}/status` followed by `POST /party/{id}/rounds/prompt`).
  - Connection state (`connected`, `connecting`, `error`) is exposed to party screens for UX feedback.
  - Auth-related close codes (`1008`, `1011`) stop reconnect attempts and surface a clear error; other failures rely on backoff reconnects from the shared hook.
  - Session updates are broadcast every ~5 seconds while connections are active, keeping all party members synchronized on game progress.

## Backend WebSocket Endpoints

All three QF channels use the same authentication pattern and rely on short-lived tokens:

- **`/qf/auth/ws-token`** — short-lived token issuance (60 seconds) used by all channels
  - Called via REST before establishing WebSocket connections
  - Token passed as query parameter: `?token=...`
  - Provides secure cross-domain WebSocket auth when HttpOnly cookies cannot be used

- **`/qf/notifications/ws`** — per-player notification delivery managed by `WebSocketNotificationService`
  - Pushes copy submissions, vote notifications, and ping messages
  - One connection per authenticated player
  - No fallback; errors are logged but silent (no REST fallback)

- **`/qf/users/online/ws`** — broadcasts online-user snapshots managed by `OnlineUsersConnectionManager`
  - Updates every 5 seconds while any client is connected
  - Includes user presence, last action, and balance data
  - Falls back to REST polling (`GET /qf/users/online`) on connection loss with automatic reconnection

- **`/qf/party/{sessionId}/ws`** — party session updates managed by `PartyWebSocketManager`
  - Read-only updates for lobby presence and game progress
  - Updates every ~5 seconds or on significant state changes
  - Requires both valid token AND membership in the party session

## Connection Lifecycle

1. **Authentication**: Client calls `GET /qf/auth/ws-token` to get a 60-second token
2. **Connection**: Client initiates WebSocket with token in query param: `wss://.../{channel}?token=<token>`
3. **Validation**: Backend validates token signature and player identity
4. **Messaging**: Server pushes updates; client maintains connection with periodic heartbeats
5. **Disconnection**: Client closes socket on logout; server auto-closes on token expiration or validation failure

All endpoints reject missing/invalid tokens with WebSocket close code `1008` (POLICY_VIOLATION).
