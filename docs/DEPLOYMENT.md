# Deployment Guide

This guide documents how we ship the multi-game FastAPI backend to Heroku and the three Vercel frontends (QuipFlip, MemeMint, Initial Reaction). All frontends live in this repo and share the `frontend/crowdcraft` library via npm workspaces.

## Deployment Targets
- **Backend:** Single FastAPI service on Heroku (`https://quipflip-c196034288cd.herokuapp.com`) serving `/qf`, `/mm`, and `/ir`.
- **Frontends:** Three Vercel projects with roots `frontend/qf`, `frontend/mm`, and `frontend/ir`. Each project ships its own `vercel.json` rewrite.
- **API proxy:** Vercel rewrites `/api/*` to the Heroku backend for same-origin REST (HttpOnly cookies stay intact). WebSockets connect directly to Heroku using a short-lived token exchange.

## Backend (Heroku)

### Prerequisites
- Heroku app set to `container` stack (uses `heroku.yml` + `Dockerfile`).
- Add-ons: Postgres (required), Redis (optional but recommended for locks/queues).

### Release pipeline
- `heroku.yml` runs release commands: `alembic upgrade head` then `python3 scripts/auto_seed_prompts.py`.
- Runtime command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.

### Environment variables
Set via `heroku config:set` (names map directly to `backend.config.Settings`):

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT=production` | Enables secure cookies/CORS defaults |
| `SECRET_KEY` | Required; change from default |
| `DATABASE_URL` | Heroku Postgres URL |
| `REDIS_URL` | Optional; enables Redis locks/queues |
| `QF_FRONTEND_URL` | Primary QuipFlip host (for CORS) |
| `MM_FRONTEND_URL` | Primary MemeMint host (for CORS) |
| `ALLOWED_ORIGINS` | Comma-separated extra origins (e.g., Vercel preview URLs) |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` | AI providers (optional) |
| `AI_PROVIDER` | `openai` or `gemini` |
| `USE_PHRASE_VALIDATOR_API` | `true` to use remote validator |
| `PHRASE_VALIDATOR_URL` | Remote validator base URL when enabled |

Notes:
- Cookies are HttpOnly + Secure (in production) with SameSite=Lax; REST stays same-origin via the Vercel proxy.
- CORS defaults include `QF_FRONTEND_URL`, `MM_FRONTEND_URL`, localhost dev ports, and any values in `ALLOWED_ORIGINS`.
- If `USE_PHRASE_VALIDATOR_API=false`, the local validator uses the bundled NASPA dictionary.

## Frontends (Vercel)

Common settings for each project:
- **Project root:** `frontend/qf`, `frontend/mm`, or `frontend/ir`.
- **Install:** `npm install` (repo uses npm workspaces; this pulls shared `frontend/crowdcraft`).
- **Build:** `npm run build`
- **Output directory:** `dist`
- **Node:** 18+ (match local dev; 20 recommended).
- **Rewrite:** Use the included `vercel.json` (rewrites `/api/:path*` → Heroku backend).
- **Env vars:**
  - QF/MM: `VITE_API_URL=/api` (client appends `/qf` or `/mm` automatically).
  - IR: `VITE_API_URL=/api` (client appends `/ir` if missing).

### WebSockets
- WebSockets bypass Vercel; the frontend first calls `/api/qf/auth/ws-token` (via the proxy) then connects to `wss://quipflip-c196034288cd.herokuapp.com/qf/...` with the returned token (60s TTL).
- Channels: notifications, online users, and party mode. See `docs/WEBSOCKET.md` for paths and client behavior.

## Deployment Checklist

### Backend
- [ ] `ENVIRONMENT=production` and strong `SECRET_KEY` set
- [ ] Postgres add-on provisioned (`DATABASE_URL` present)
- [ ] Redis add-on configured (`REDIS_URL`) or confirmed optional fallback
- [ ] CORS: `QF_FRONTEND_URL`, `MM_FRONTEND_URL`, and `ALLOWED_ORIGINS` cover prod + previews
- [ ] AI keys set if using backups/hints (`OPENAI_API_KEY`/`GEMINI_API_KEY`, `AI_PROVIDER`)
- [ ] Phrase validator configured (`USE_PHRASE_VALIDATOR_API`, `PHRASE_VALIDATOR_URL`) or local mode chosen
- [ ] Deploy (e.g., `git push heroku main`) and confirm release phase migrations succeed

### Frontends
- [ ] Vercel project roots set to `frontend/qf`, `frontend/mm`, `frontend/ir`
- [ ] `VITE_API_URL=/api` configured for each project
- [ ] `vercel.json` rewrite intact
- [ ] Build succeeds (`npm run build`)
- [ ] Smoke tests: REST calls go through `/api/*`; QF WebSockets connect directly to Heroku

## Smoke Tests
- Backend health: `curl https://quipflip-c196034288cd.herokuapp.com/health`
- WebSocket token + connect (QF):
  ```bash
  curl -b cookies.txt -c cookies.txt https://quipflip-c196034288cd.herokuapp.com/qf/auth/ws-token
  # then connect to wss://quipflip-c196034288cd.herokuapp.com/qf/users/online/ws?token=...
  ```
- Frontend builds locally (optional confidence before deploy):
  ```bash
  npm run build:qf   # from repo root
  npm run build --workspace frontend/mm
  npm run build --workspace frontend/ir
  ```

## Testing

### Manual API + cookie verification (QF)
```bash
# Login (replace credentials) and persist cookies locally
curl -X POST https://quipflip-c196034288cd.herokuapp.com/qf/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"YOUR_EMAIL","password":"YOUR_PASSWORD"}' \
  -c cookies.txt -v

# Verify cookies authenticate subsequent requests
curl https://quipflip-c196034288cd.herokuapp.com/qf/player/me \
  -b cookies.txt -v
```

### Manual WebSocket check (QF online users)
```bash
# Mint short-lived token (requires cookies from prior login)
token=$(curl -s -b cookies.txt https://quipflip-c196034288cd.herokuapp.com/qf/auth/ws-token | jq -r .token)

# Connect directly to Heroku WS endpoint
node -e "const WebSocket=require('ws'); const ws=new WebSocket('wss://quipflip-c196034288cd.herokuapp.com/qf/users/online/ws?token='+process.env.TOKEN); ws.on('open',()=>console.log('connected')); ws.on('message',m=>console.log('msg',m.toString())); ws.on('close',(c,r)=>console.log('closed',c,r));" TOKEN=$token
```

### Frontend sanity checks (after deploy)
- Hit `https://quipflip.xyz` (QF), MemeMint, and IR prod URLs.
- Open DevTools → Network: confirm API calls go to `/api/...` (same-origin) and carry `Cookie` headers.
- For QF, open the Online Users screen and confirm live updates; force a token expiration by waiting >60s then ensure reconnection fetches a new token.

### Automated
```bash
# Backend
pytest

# Frontends (from repo root)
npm run build:qf
npm run build --workspace frontend/mm
npm run build --workspace frontend/ir
```

## Troubleshooting
- **Cookies not set:** Requests must go through `/api/*` rewrite; confirm `ENVIRONMENT=production` and HTTPS on the deployed domain listed in `QF_FRONTEND_URL` / `MM_FRONTEND_URL`.
- **WebSocket auth failures (code 1008 or instant close):** Token older than 60s, cookies missing during token request, or using `ws://` instead of `wss://`. Refresh page to mint a new token.
- **CORS errors / preflight failures:** Add preview domains to `ALLOWED_ORIGINS` and redeploy backend; make sure `VITE_API_URL` is `/api` (not an absolute cross-site URL).
- **API 401s after login:** Check that `SECRET_KEY` changed from default and clocks are in sync; ensure Secure cookies are allowed in the browser (no mixed-content HTTP).
- **Builder fails on Vercel:** Ensure the project root points to the correct frontend folder and Node version is 18/20; clear `.next`/`node_modules` caches if using custom settings.

## Monitoring
- **Health:** `curl https://quipflip-c196034288cd.herokuapp.com/health`
- **Logs:** `heroku logs --tail --app quipflip-c196034288cd`
- **DB/Redis status:** Check add-on dashboards for connection limits and slow queries.
- **Frontend deploys:** Vercel dashboards for `frontend/qf`, `frontend/mm`, `frontend/ir`—review build logs and check rewrites.
- **WebSocket signal:** Backend logs emit connect/disconnect counts; watch for repeated 1008/440x codes indicating auth issues.
