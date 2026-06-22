# Frontend Instructions

Four Vite + React + TypeScript + Tailwind SPAs (`qf`, `mm`, `ir`, `tl`) share the
`frontend/crowdcraft` library (components, contexts, hooks, API clients, utils)
through `@crowdcraft/*` path aliases and npm workspaces. Preserve each game's
existing look, feel, branding, and assets — the transition does **not** restyle the
games.

- **The client renders server state and submits commands.** It must not contain
  authoritative scoring, eligibility, pricing, queue-assignment, finalization, or
  deadline logic. Countdown timers are display-only and derived from server
  deadlines; the backend enforces the real cutoff plus grace.
- **API base URL is same-origin in the target deployment.** An absent production
  override resolves explicitly to `window.location.origin`; do not use an empty
  `VITE_API_URL` with an `||` localhost fallback. The shared client appends the game
  prefix (`/qf`, `/mm`, …). Do not hardcode backend hosts. See
  `frontend/crowdcraft/src/api/client.ts` and `BaseApiClient.ts`.
- **WebSocket URLs derive from `window.location`** (`wss://<same-host>/...`), not a
  hardcoded backend URL. Update `frontend/crowdcraft/src/hooks/useWebSocket.ts`
  when touching realtime. WS auth uses the short-lived `/<game>/auth/ws-token`;
  close and do not retry on `1008`.
- **Keep shared logic in `frontend/crowdcraft`.** Game apps add pages, assets, and
  thin API extensions; common components/contexts/hooks belong in the shared lib so
  all four games stay consistent.
- **Build is part of verification.** Run the affected `npm run build:<game>` (or
  `npm run build` in the app) before reporting UI changes; substantial UI changes
  also require an actual browser check.
- Use HttpOnly cookies via `withCredentials`; never store tokens in
  `localStorage`. Same-origin per subdomain keeps cookies isolated per game.

When changing realtime or auth flows, confirm reconnect **restores** state
(membership, active round, deadlines) and never resets the player's progress.
