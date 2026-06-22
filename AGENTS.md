# Crowdcraft Labs Agent Guide

Crowdcraft Labs is a multi-game platform — **QuipFlip (`/qf`)**, **MemeMint
(`/mm`)**, **Initial Reaction (`/ir`)**, and **ThinkLink (`/tl`)** — served by one
async **FastAPI** backend and four Vite/React/Tailwind frontends that share the
`frontend/crowdcraft` library. The backend owns persistence, queues, the flipcoin
economy, scoring, finalization, AI backups, and the realtime channels; the
frontends are thin clients. `tests/` covers lifecycle, scoring, and integration.

This repository is mid-transition toward the reliability and operating model of the
sibling `pixel-plagiarist` repo. Read the [transition plan](docs/transition-plan.md)
for the destination and the [codebase organization guide](docs/development/codebase-organization.md)
for current rules.

## Authority and instruction hierarchy

1. Direct task instructions and the nearest path-specific `AGENTS.md`.
2. This file and [the autonomous workflow](docs/development/autonomous-agent-workflow.md).
3. Running code and tests for implemented behavior.
4. The game rules docs under `docs/<game>/` for intended behavior.
5. Active development guides, then historical plans.

Keep universal rules here. Put subsystem rules in path-specific `AGENTS.md` files.
Maintain one canonical source for each rule.

## Setup and canonical verification

Requires Python 3.12+ and Node.js 20+.

```bash
pip install -r requirements.txt
pytest                       # backend lifecycle, scoring, integration (SQLite)
npm run build:qf && npm run build:mm && npm run build:ir && npm run build:tl
```

Use `uvicorn backend.main:app --reload` for local backend dev and `npm run dev` in a
`frontend/<game>` for the client. Run focused tests while editing; run the full
suite plus the four frontend builds before reporting completion. (A single `verify`
entry point is being introduced — see the transition plan, Workstream A.)

## Non-negotiable invariants

- **The server is authoritative** for eligibility, pricing, queue assignment, vote
  validity, scoring, finalization, and every lifecycle transition. Frontend timers
  and counts are display-only.
- **Validate every inbound payload** with Pydantic, and **re-validate the lifecycle
  precondition inside the database transaction** (is this round still claimable / still
  the player's active round / still open?). A request schema does not prove a state
  precondition.
- **One controlled mutation path per transition.** A `round` / `phraseset` /
  `party_round` advances through exactly one service command that conditionally
  updates the expected status/version, re-validates state, writes ledger changes,
  and commits atomically. Database constraints and idempotency keys, not a process
  lock, make invalid states uncommittable.
- **Deadlines, not client clocks, drive progression**, and deadline commands are
  idempotent and stale-safe** — re-running after the state advanced must not
  double-refund, double-pay, or re-queue.
- **Money is a ledger.** Every flipcoin movement is a uniquely keyed transaction
  row written atomically with cached wallet/vault changes. Refunds and payouts are
  idempotent; finalization is the only place prize pools are distributed.
- **SQLite is durable truth.** The target deployment uses exactly one Uvicorn
  worker, foreign keys, WAL, a bounded busy timeout, and short writes. In-memory
  queues/locks are rebuildable coordination only. Never hold a synchronous lock
  across `await` or rely on `FOR UPDATE` for SQLite correctness.
- **Never serialize internal models.** Return explicit response schemas. Before
  finalization never disclose authorship, the originating prompt to a copy player,
  or which phrase/entry is the original to a voter.
- **Reconnect restores, never resets** party membership, round assignment, votes,
  allowances, or deadlines.
- **No credentials** in the source tree, fixtures, logs, screenshots, or commits.
  Commit `.env.example` with names and safe placeholders only.
- **Do not execute untrusted scripts** without inspecting them.

## Standard workflow

1. Read the task contract, applicable `AGENTS.md`, the relevant game-rules doc, and
   `git status`.
2. Investigate before editing when lifecycle ownership, locking, disclosure, money
   movement, or existing in-flight changes are unclear.
3. Define one behavioral objective, the invariants it must preserve, non-goals, and
   verification. Keep the diff small.
4. Make the smallest complete change. Do not mix behavior changes with broad
   formatting, dependency upgrades, or mechanical extraction.
5. Add or update the lowest-layer test that proves the claim (a pure scoring/
   eligibility unit test beats an integration test where it can do the job). Delete
   superseded code and temporary debug scripts.
6. Run focused tests, the full `pytest`, affected frontend builds, and any smoke
   check for changed lifecycle/transport behavior.
7. Inspect `git diff --check`, `git diff --stat`, and the full diff. Do not rely on
   tests alone.
8. Report changed behavior, invariants reviewed, exact commands/results, browser
   evidence for UI changes, limitations, and deliberately untouched files.

Stop and investigate rather than guessing if requirements conflict, a secret may be
exposed, a migration can destroy or orphan data, a response may leak
pre-finalization information, or money could be double-moved. Do not weaken a gate
to make it pass.

## High-risk changes

Round/phraseset/party lifecycle, locking/queue assignment, scoring and prize-pool
distribution, refunds/payouts, authentication, WebSocket auth/reconnect, response
schemas (disclosure), database migrations, and dependency/CI changes require an
independent review focused on the relevant risk. Substantial UI changes require
actual browser verification. Follow [the review modes](docs/development/autonomous-agent-workflow.md#independent-review).

## Required final report

Use the headings in `.github/pull_request_template.md`. Never claim a check ran
unless it did. Mark failures and environment limitations explicitly with the exact
command.
