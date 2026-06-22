# Same-Origin Cloudflare Deployment

## Status

Accepted target; implemented by the deployment workstream.

## Context

The current deployment splits Vercel frontends from a Heroku backend, proxies REST,
and special-cases WebSockets. Pixel Plagiarist demonstrates the desired Mac,
launchd, and Cloudflare operating model.

## Decision

Serve all four games from one Mac-local FastAPI process and SQLite database behind
one Cloudflare named tunnel. Exact host validation selects the game and SPA. Each
host permits only that game's API prefix plus shared health/auth routes; shared auth
derives game scope from the validated host. API routes take priority over
host-specific SPA fallback. The four approved hosts map to `127.0.0.1:8000`.

API and WebSocket origins derive from `window.location`. Cookies remain host-only.
launchd runs a Keychain-integrated server wrapper and the tunnel without storing
secrets in plist files, command lines, repository files, or logs.

## Consequences

REST and WebSockets are same-origin without Vercel rewrites or a hardcoded Heroku
host. An absent production API override selects the current origin; an empty value
is not relied on because the current client uses `||` fallbacks. Uptime is tied to
the Mac, local database, and network, so backup, monitoring, rollback, and a soak
period are required.

## Rejected alternatives

Retaining the Heroku/Vercel split; separate static servers per game; host dispatch
without an exact allowlist.

## Conditions for revisiting

Split a game to independent hosting only when availability or scale requires it and
the auth/WS origin model remains explicit.
