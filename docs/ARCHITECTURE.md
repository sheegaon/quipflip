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

### Authentication & Player Model
- **Unified Player Account**: Single `players` table stores authentication and cross-game identity for all three games (QF, IR, MM).
- **Game-Specific Data Delegation**: Each game has a `{Game}PlayerData` table (qf_player_data, ir_player_data, mm_player_data) that stores game-specific state like wallet, vault, and tutorial progress.
- The `Player` model provides transparent access to game-specific fields via property accessors, allowing frontend code to use `player.wallet` regardless of which game's PlayerData stores the actual value.
- See [DATA_MODELS.md](DATA_MODELS.md#architecture-overview) for detailed architecture.

### Entrypoint & runtime lifecycle
- `backend/main.py` sets UTC before imports, configures rotating logs (general, SQL, API access), mounts CORS, and applies middleware for request deduplication and online-user tracking.
- Lifespan startup initializes the phrase validator (local or remote API), syncs prompt seeds, backfills quests, imports MemeMint images/captions, and starts background tasks (AI backup cycle, stale-content sweep, cleanup cycle, party maintenance). Shutdown closes the validator client and cancels tasks cleanly.

### Routers & dependencies
- Game routers live under `backend/routers/{qf,mm,ir}` and are mounted at `/qf`, `/mm`, `/ir`. Shared router bases (admin/player/quest) handle authentication and common dependency wiring.
- Auth router issues JWT access/refresh tokens (stored in game-specific HttpOnly cookies), maintains refresh token tables, and exposes `/auth/ws-token` for short-lived WebSocket tokens. Health router serves readiness probes.
- QF-only real-time endpoints: notifications (`/qf/notifications/ws`), online users (`/qf/users/online/ws`), and party updates (`/qf/party/{sessionId}/ws`).
- MM includes social features: circles endpoint (`/mm/circles`) for player-created groups with membership management.

### Service layer
- Routers validate/authenticate then delegate to services; services encapsulate database work, locking, and business rules.
- Core services: queue and round orchestration, voting/finalization, transaction logging, quests, statistics, notification delivery, and phrase validation (local validator or remote client).
- **QF Services**:
  - Party mode (`PartySessionService`, `PartyCoordinationService`, `PartyScoringService`, `PartyWebSocketManager`) enables multiplayer synchronized gameplay with AI player support.
  - Rich notification fan-out (`WebSocketNotificationService`) delivers copy/vote alerts and pings to prompt creators.
  - Statistics and leaderboard services compute weekly/all-time rankings split by role (prompt, copy, voter).
- **MM Services**: Circles/social group management (`CircleService`) with membership requests and approval workflows.
- **AI Orchestration** in `services/ai/*`: Generates backup copies/votes/hints for QF and backronyms/votes for IR using OpenAI or Gemini. Results, latency, and costs are recorded in `ai_metrics` table and cached in phrase/quip tables to avoid duplicate API calls. Stale content handler (`StaleAIService`) ensures permanently abandoned content receives AI help after configurable threshold.

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

## Game Flows

### QuipFlip (QF)
- **Solo Mode - Quip → Impostor → Vote** rounds share a common queue managed by `QueueService`: prompt players submit quips, two impostor copies are collected, then phrasesets enter the voting queue.
- Round limits: single active round per player, outstanding prompt limits, copy discount when the prompt queue is deep, timers with grace periods, and distributed locks to prevent double-claiming.
- Voting closes at configurable thresholds (min 3 votes to start closing, 5-vote short window, max 20). Finalization distributes prizes, writes transactions, and caches result views.
- **Party Mode** - Multiplayer synchronized rounds where players play together in real-time, with optional AI players to fill seats. Party sessions manage member readiness, round progression, and shared scoring.
- AI assists both solo and party modes by generating backup copies when prompts stall and voting when phrasesets need participation.

### MemeMint (MM)
- **Vote → Caption** flow: players vote on image captions (entry fee), then submit their own captions for the same images.
- Caption quality is tracked via performance stats (shows, picks, quality_score) and used for weighted selection in future rounds.
- **Social Groups (Circles)**: Players can create circles to organize, collaborate, and manage shared meme activities with membership requests and approval workflows.

### Initial Reaction (IR)
- **Backronym Sets**: Players create backronym entries (one letter = one word) for random 3–5 letter words, then vote on submissions.
- Set lifecycle: collecting entries (0–5), voting phase, finalization with prize distribution.
- AI generates backronyms and votes when sets stall, ensuring games progress even with low human participation.

## Phrase Validation & AI
- Phrase validation can run locally (`services/phrase_validator.py` + NASPA dictionary + similarity thresholds) or through a remote Phrase Validation API client; both enforce word lists, length limits, and semantic-distance checks.
- AI service (`docs/AI_SERVICE.md`) integrates with the same validators, caches generated phrases/backronyms, and records latency/cost/accuracy metrics. Backup cycles run as background tasks; hints reuse the same cached phrases.

## Deployment Notes
- Production setup: Vercel frontends (e.g., `quipflip.xyz`) proxy REST calls to the Heroku backend (`quipflip-c196034288cd.herokuapp.com`) at `/api/*` for same-origin cookies; WebSockets connect directly to the backend using short-lived tokens.
- Local dev uses SQLite by default, optional Redis for locks/queues, and the same FastAPI app with `uvicorn backend.main:app --reload`.
- Config is environment-driven via `backend.config.Settings`; set env vars as needed (see `docs/API.md` for endpoint specifics).
