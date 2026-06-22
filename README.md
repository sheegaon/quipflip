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

Install dependencies from the committed manifests, then run the deterministic
repository gate:

```bash
npm ci
npm run verify
```

The default gate runs the isolated backend suite, frontend origin contract tests,
lint/typecheck/build for the shared library and all four games, and secret scanning.
It does not require a server, credentials, or network access.

The backend portion currently reports the deterministic product-regression
families recorded in the [test inventory](docs/development/test-tier-inventory.md);
the command is trustworthy and reproducible but is not yet green. Do not treat a
nonzero result as an environment limitation.

Production-shaped SQLite and transport checks are explicit separate gates:

```bash
npm run test:sqlite-integration
npm run smoke  # requires the API on http://localhost:8000
```

Security checks run locally and in CI:

```bash
npm run security:secrets
npm run security:npm-audit
.venv/bin/pip-audit -r requirements.txt
```

Temporary audit exceptions must include an owner-readable reason and expiry in
`security/`. Expired or newly discovered high/critical npm vulnerabilities fail
the gate. Test tier ownership and runtime budgets are documented in
[the test inventory](docs/development/test-tier-inventory.md).

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
