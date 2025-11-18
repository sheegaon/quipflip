# API Documentation Index

The backend now mirrors the code split between shared infrastructure and game-specific routers.

- [Quipflip (QF) API](QF_API.md) – endpoints mounted under `/qf/*` and implemented in `backend/routers/qf`.
- [Initial Reaction (IR) API](IR_API.md) – endpoints mounted under `/ir/*` and implemented in `backend/routers/ir`.

## Shared Endpoints

Authentication, health checks, and WebSocket token exchange are defined once in `backend/routers` and reused by both games:

- `GET /health` and `GET /` for basic service discovery.
- `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` for cookie-backed JWTs.
- `POST /auth/ws-token` for short-lived WebSocket tokens.

Refer to each game guide for gameplay-specific routes and payloads. Both games share the same authentication contract and HTTP error envelope.
