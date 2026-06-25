# QuipFlip Production Play Test

Date: 2026-06-24
Environment: https://quipflip.crowdcraftlabs.com/
Tester: Codex

## Flow tested

1. Opened the production site in a clean browser tab.
2. Confirmed guest-first entry created a guest session and landed on `/dashboard`.
3. Dismissed the welcome overlay.
4. Tried to start a Quip round from the dashboard.
5. Started and submitted an Impostor round.

## Issues found

### 1. Fresh guest dashboard can hit a request storm before gameplay starts

- Browser console showed dozens of repeated `Statistics refresh failed` errors immediately after guest entry.
- The first Quip round attempt returned the UI error `Too many requests. Please wait a moment before trying again.` and did not navigate away from the dashboard.
- The symptom is consistent with the shared results actions being recreated every render, which causes guest-upgrade history checks to repeatedly refetch statistics while the dashboard is rendering.

### 2. Copy-round side effects degrade under the same load

- The Impostor round itself could be opened and submitted, but the page displayed a reconnect banner and the AI hints request failed with a temporary server-busy message.
- Those failures appeared after the same burst of repeated statistics errors, so they are likely secondary effects of the request storm and guest rate limiting rather than isolated gameplay bugs.

### 3. Guest account save and returning-account restore are broken in production

- `POST /auth/magic-links` returned `503 {"detail":"magic_link_email_failed"}` from the production host.
- Installed production runtime configuration had no SMTP settings loaded, so the frontend's magic-link-based account flow could never succeed.
- QuipFlip already ships direct email/password login and guest-upgrade APIs, so the production frontend should not depend on SMTP for the primary guest-first account path.

## Deployment blocker observed during redeploy attempt

- `scripts/restart-production-server.sh` could not complete because the frontend verification step ran without installed workspace dependencies.
- The release gate failed on missing `typescript` and `vite` package resolution from `scripts/test_frontend_origins.mjs` and `scripts/run_frontend_checks.mjs`.
