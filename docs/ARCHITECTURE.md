# Technical Architecture and Overview

## System Overview
- Crowdcraft platform runs three games—QuipFlip (phrases), MemeMint (memes/captions), and Initial Reaction (backronyms)—behind a single FastAPI backend.
- Backend exposes stateless REST endpoints plus a few WebSocket channels; it owns persistence, queueing, wallets, quests, AI backups, and finalization logic. Frontends are thin clients.
- React + TypeScript frontends are Vite apps that reuse a shared `frontend/crowdcraft` component/util/API layer via `@crowdcraft/*` path aliases.
- Phrase validation and AI generation can run locally or through external services but plug into the same service layer and metrics.

## Project Structure
```
repo/
├── backend/                # FastAPI app, routers, services, models, utils, middleware
│   ├── routers/            # auth/health + game routers (qf/mm/ir) and WebSocket endpoints
│   ├── services/           # shared infrastructure + game-specific domains (rounds, party, AI, notifications)
│   ├── models/             # SQLAlchemy models (shared bases + game packages)
│   ├── schemas/            # Pydantic request/response models
│   ├── middleware/         # deduplication + online user tracking
│   ├── tasks/              # periodic maintenance helpers
│   └── migrations/         # Alembic migrations
├── frontend/
│   ├── crowdcraft/         # shared component/util/API library exported as @crowdcraft/*
│   ├── qf/                 # QuipFlip SPA
│   ├── mm/                 # MemeMint SPA
│   └── ir/                 # Initial Reaction SPA
├── docs/                   # Architecture, API, data models, websocket, AI docs
├── scripts/                # Ops/data helpers (dictionary download, cleanup)
├── tests/                  # Pytest suites (integration focus)
├── package.json            # npm workspaces for all frontend packages
├── requirements.txt        # Backend dependencies
└── docker-compose.yml      # Local Postgres/Redis helpers
```

## Backend Architecture

### Entrypoint & runtime lifecycle
- `backend/main.py` sets UTC before imports, configures rotating logs (general, SQL, API access), mounts CORS, and applies middleware for request deduplication and online-user tracking.
- Lifespan startup initializes the phrase validator (local or remote API), syncs prompt seeds, backfills quests, imports MemeMint images/captions, and starts background tasks (AI backup cycle, stale-content sweep, cleanup cycle, party maintenance). Shutdown closes the validator client and cancels tasks cleanly.

### Routers & dependencies
- Game routers live under `backend/routers/{qf,mm,ir}` and are mounted at `/qf`, `/mm`, `/ir`. Shared router bases (admin/player/quest) handle authentication and common dependency wiring.
- Auth router issues JWT access/refresh tokens, maintains HttpOnly cookies, and exposes `/auth/ws-token` for short-lived WebSocket tokens. Health router serves readiness probes.
- QF-only real-time endpoints: notifications (`/qf/notifications/ws`), online users (`/qf/users/online/ws`), and party updates (`/qf/party/{sessionId}/ws`).

### Service layer
- Routers validate/authenticate then delegate to services; services encapsulate database work, locking, and business rules.
- Core services: queue and round orchestration, voting/finalization, transaction logging, quests, statistics, notification delivery, and phrase validation (local validator or remote client).
- QF-specific services cover party mode (`PartySessionService`, `PartyCoordinationService`, `PartyScoringService`, `PartyWebSocketManager`) and rich notification fan-out.
- AI orchestration in `services/ai/*` generates backup copies/votes/hints for QF and backronyms/votes for IR using OpenAI or Gemini. Results and costs are recorded in `ai_metrics` and cached phrase tables to avoid duplicate work.

### Data & infrastructure
- Async SQLAlchemy with Postgres in production and SQLite locally (`backend/database.py`); migrations in `backend/migrations/`.
- Models are split into shared bases (`*_base.py` for auth/tokens/transactions) and per-game packages (`models/qf`, `models/mm`, `models/ir`). Pydantic schemas mirror API shapes in `backend/schemas`.
- Locking and queue helpers prefer Redis when configured (`utils/lock_client.py`, `utils/queue_client.py`) and fall back to in-memory/thread locks. Rate limiting, cookie helpers, and JSON encoding live in `backend/utils`.
- Logging writes to `logs/` via rotating handlers; API request logging middleware emits structured entries.

### Background jobs
- `ai_backup_cycle` periodically fills stalled prompts/phrasesets with AI copies and votes.
- `ai_stale_handler_cycle` sweeps older content to keep games fresh.
- `cleanup_cycle` removes stale tokens and related auth artifacts.
- `party_maintenance_cycle` prunes stale party sessions/participants.
- `ir_backup_cycle` is available for Initial Reaction but currently disabled by default in the lifespan loop.

## Frontend Architecture

### Shared library: `frontend/crowdcraft`
- Vite-built library exporting UI components, contexts, utilities, and API/base client helpers via `@crowdcraft/*`.
- Consumed directly via path aliases in each game `tsconfig`; `frontend/crowdcraft` is included in the TypeScript `include` list so types remain in sync during local dev.

### Game apps
- `frontend/{qf,mm,ir}` are Vite + React + TypeScript SPAs with Tailwind for styling and per-game branding/routes.
- Each app imports shared pieces from `@crowdcraft` plus game-specific pages, assets, and API extensions. Axios clients are configured with `withCredentials` and derive the base URL from Vite env (`VITE_API_URL`) so HttpOnly cookies flow to the backend proxy.
- Vercel hosts the production frontends; Vercel proxies REST under `/api/*` to the Heroku backend to keep same-origin cookie semantics.

## Authentication & Session Model
- JWT access tokens (~2h) and refresh tokens (~30d) are stored in HttpOnly cookies (`access_token_cookie_name` / `refresh_token_cookie_name` for QF, IR-specific names for IR). Authorization headers remain supported for API clients.
- Token refresh is automatic on 401 via frontend interceptors; logout clears cookies. SameSite is lax in dev and secure in production.
- WebSocket access uses `/qf/auth/ws-token` to mint 60-second tokens passed via query param; sockets are closed and do not retry on auth failures.

## Real-Time Channels (QF)
- Notifications: `/qf/notifications/ws` pushes pings and notification payloads via `WebSocketNotificationService`.
- Online users: `/qf/users/online/ws` broadcasts presence snapshots; REST polling fallback exists when the socket drops.
- Party mode: `/qf/party/{sessionId}/ws` emits lobby/progress updates while REST endpoints drive actions (create/join/start/submit).
See `docs/WEBSOCKET.md` for connection details and error handling.

## QuipFlip Game Flow (high level)
- **Quip → Impostor → Vote** rounds share a common queue managed by `QueueService`: prompt players submit quips, two impostor copies are collected, then phrasesets enter the voting queue.
- Round limits: single active round per player, outstanding prompt limits, copy discount when the prompt queue is deep, timers with grace periods, and distributed locks to prevent double-claiming.
- Voting closes at configurable thresholds (min 3 votes to start closing, 5-vote short window, max 20). Finalization distributes prizes, writes transactions, and caches result views.
- MemeMint and Initial Reaction reuse the same service patterns with game-specific models and settings (caption/vote for MM, backronym sets for IR).

## Phrase Validation & AI
- Phrase validation can run locally (`services/phrase_validator.py` + NASPA dictionary + similarity thresholds) or through a remote Phrase Validation API client; both enforce word lists, length limits, and semantic-distance checks.
- AI service (`docs/AI_SERVICE.md`) integrates with the same validators, caches generated phrases/backronyms, and records latency/cost/accuracy metrics. Backup cycles run as background tasks; hints reuse the same cached phrases.

## Deployment Notes
- Production setup: Vercel frontends (e.g., `quipflip.xyz`) proxy REST calls to the Heroku backend (`quipflip-c196034288cd.herokuapp.com`) at `/api/*` for same-origin cookies; WebSockets connect directly to the backend using short-lived tokens.
- Local dev uses SQLite by default, optional Redis for locks/queues, and the same FastAPI app with `uvicorn backend.main:app --reload`.
- Config is environment-driven via `backend.config.Settings`; set env vars as needed (see `docs/API.md` for endpoint specifics).
