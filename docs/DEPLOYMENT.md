# Legacy Heroku and Vercel Deployment

> **Document type:** Operational reference
> **Status:** Current legacy topology; scheduled for replacement
> **Last checked:** 2026-06-22

This document describes the provider split that remains until the
[Mac/Cloudflare cutover](development/persistent-startup-services.md). On the last
check, `quipflip.xyz` served the Vercel frontend while the Heroku backend health URL
returned maintenance-mode HTTP 503. Treat recovery steps below as legacy operations,
not evidence that production is healthy.

## Topology

- Backend: `quipflip-c196034288cd.herokuapp.com`, FastAPI plus Heroku Postgres.
- Frontends: Vercel projects rooted at `frontend/qf`, `frontend/mm`,
  `frontend/ir`, and `frontend/tl`.
- REST: each `vercel.json` rewrites `/api/*` to Heroku to preserve same-origin
  cookies.
- QF WebSockets: connect directly to Heroku after a short-lived token exchange.

The repository contains four frontend workspaces even though older deployment
notes and CI refer to three.

## Backend release

`heroku.yml` runs `alembic upgrade head` and prompt seeding in the release phase,
then starts:

```text
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Required provider configuration includes production environment, a non-default
signing secret, `DATABASE_URL`, exact frontend origins, and optional AI provider
keys. Redis is optional in the legacy topology, but current lifecycle integrity
must not be assumed when Redis/in-memory queues diverge from the database.

Do not paste provider values into documentation, shell history, logs, or tickets.

## Frontend release

Each Vercel project uses Node 20, installs from the repository lockfile, builds its
workspace, and publishes `dist`. Legacy builds set `VITE_API_URL=/api`; the shared
WebSocket hook may use `VITE_BACKEND_WS_URL` for the Heroku socket host.

Before any release, all four commands must pass:

```bash
npm run build:qf
npm run build:mm
npm run build:ir
npm run build:tl
```

At the 2026-06-22 baseline QF and MM passed, IR failed TypeScript compilation, and
the chained command did not reach TL. Do not deploy a partial frontend set as a
green release.

## Verification

```bash
curl -fsS https://quipflip-c196034288cd.herokuapp.com/health
curl -fsS https://quipflip.xyz/
```

A complete check also verifies exact REST origin, cookie login/refresh/logout, one
game flow per deployed frontend, QF WebSocket token/connect/reconnect, and browser
console errors. Never put a real password or token into a command retained in shell
history.

## Recovery and retirement

- Use Heroku/Vercel dashboards and provider logs for the legacy system; redact
  request data and tokens before sharing output.
- Confirm release-phase migrations completed before diagnosing application startup.
- A frontend HTTP 200 is not service health when proxied API calls fail.
- Keep this topology available as cutover rollback until the new SQLite deployment
  completes its soak window.
- After retirement, mark this document Historical and remove provider-specific
  rewrites/configuration in a separate reviewed change.
