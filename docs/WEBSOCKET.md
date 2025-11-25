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
- **Endpoint:** `GET /qf/party/{sessionId}/ws?context={lobby|game|other}&token=...`
- **Messages:** session lifecycle events including `phase_transition`, `player_joined`, `player_left`, `player_ready`, `progress_update`, `session_started`, `session_completed`, `session_update`, and `host_ping`.
- **Frontend:**
  - `usePartyWebSocket` wraps `useWebSocket`, enabling the connection when authenticated and `sessionId` is set.
  - Connection state (`connected`, `connecting`, `error`) is exposed to party screens for UX feedback.
  - Auth-related close codes (`4000`–`4003`, `4401`, `4403`) stop reconnect attempts and surface a clear error; other failures rely on backoff reconnects from the shared hook.

## Backend WebSocket Endpoints
- `/qf/auth/ws-token` — short-lived token issuance (60s) used by all channels.
- `/qf/notifications/ws` — per-player notification delivery managed by `WebSocketNotificationService`.
- `/qf/users/online/ws` — broadcasts online-user snapshots and ping messages via `OnlineUsersConnectionManager`.
- `/qf/party/{sessionId}/ws` — party session updates managed by `PartyWebSocketManager`.

All endpoints rely on the token exchange (query param or cookie) for authentication and keep connections open for real-time updates while the user remains logged in.
