# Crowdcraft Labs games

This repository contains four asynchronous multiplayer games served by one FastAPI
backend:

- QuipFlip (`/qf`)
- MemeMint (`/mm`)
- Initial Reaction (`/ir`)
- ThinkLink (`/tl`)

Each game has a Vite/React frontend under `frontend/`; shared client code lives in
`frontend/crowdcraft`. The backend owns persistence, lifecycle transitions,
eligibility, scoring, the in-game economies, AI backup players, and realtime
channels.

The repository is being hardened for the Mac-local SQLite/FastAPI deployment
behind Cloudflare. Start with the [documentation index](docs/README.md) and the
active [reliability and deployment plan](docs/transition-plan.md).

## Requirements

- Python 3.12+
- Node.js 20+
- SQLite configured with the same integrity and concurrency pragmas as production

## Local setup

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
npm ci
alembic upgrade head
```

Start the API:

```bash
.venv/bin/uvicorn backend.main:app --reload
```

Start one frontend from its workspace, for example:

```bash
npm run dev --workspace frontend/qf -- --host
```

The API is at `http://127.0.0.1:8000`; its current health endpoint is `/health`.
The transition plan requires separate `/livez` and `/readyz` endpoints before the
Mac deployment is considered production-ready.

## Verification

The canonical single-command gate is planned but not implemented yet. Current
required evidence is:

```bash
.venv/bin/python -m pytest
npm run build:qf
npm run build:mm
npm run build:ir
npm run build:tl
```

The baseline is not green; see the transition plan for the dated results and the
work to split deterministic, lifecycle, localhost, stress, and smoke tiers. Do not
describe the repository as passing until the exact commands pass.

## Authoritative documentation

- [Documentation index](docs/README.md)
- [Engineering and agent rules](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [QuipFlip rules](docs/quipflip/QF_GAME_RULES.md)
- [MemeMint rules](docs/mememint/MM_GAME_RULES.md)
- [Initial Reaction rules](docs/initialreaction/IR_GAME_RULES.md)
- [ThinkLink rules](docs/thinklink/TL_GAME_RULES.md)

The game-rules documents, not this README, are the canonical source for economy and
gameplay behavior.
