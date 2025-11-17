# WebSocket Notifications Review

## Scope
- Verified `WEBSOCKET_NOTIFICATIONS_IMPLEMENTATION.md` against the shipped backend/frontend code
- Ensured new REST + WebSocket surfaces are reflected in canonical docs (`API.md`, `DATA_MODELS.md`)
- Audited backend flows (round + vote submissions, notification persistence, WebSocket delivery)

## Critical Issues Fixed
1. **Connection manager was never wired into `NotificationService`**
   - Round/Vote services instantiate `NotificationService` directly, but the class expected `set_connection_manager()` to be invoked beforehand.
   - As a result, `_connection_manager` remained `None` and no WebSocket payloads were ever sent even when clients were connected.
   - Fix: `NotificationService` now defaults to the global singleton returned by `get_notification_manager()` while still allowing explicit injection for tests. (File: `backend/services/notification_service.py`).

2. **Notifications were not committed to the database**
   - `notify_copy_submission()` / `notify_vote_submission()` called `_create_notification()` (which only flushed) *after* the calling services had already committed their own work.
   - Without an additional commit, notification rows never persisted, defeating audit trails and rate limiting.
   - Fix: each notifier now tracks whether it created rows and performs `await self.db.commit()` once at the end of the method. This ensures durable storage before WebSocket delivery. (File: `backend/services/notification_service.py`).

## Verification Notes
- `GET /auth/ws-token` + `WebSocket /qf/notifications/ws` handshake documented and matches the frontend `NotificationContext` implementation.
- Rate limiting (10 per player/minute), human-only filtering, and self-action filtering align with the service code.
- Frontend providers/components (`NotificationProvider`, `NotificationDisplay`, `NotificationToast`) mount globally via `AppProviders`/`App.tsx`, ensuring toasts appear on every page when the WebSocket emits a payload.
- Alembic migration `001_add_notifications_table.py` introduces the table + indexes described in the implementation doc; `docs/DATA_MODELS.md` now mirrors that schema.

## Additional Recommendations
1. **Add persistence API**: Provide `/notifications` REST endpoints for listing + dismissing stored notifications so players can see missed events when offline.
2. **Reconnect/backoff strategy**: Implement exponential backoff reconnects in `NotificationContext` to handle transient Heroku restarts without manual refreshes.
3. **Observability**: Emit structured metrics (counts per type, rate-limit drops) from `NotificationService` so we can alert on stuck delivery pipelines or unusual spikes.
