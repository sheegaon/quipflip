# WebSocket Integration

> **Document type:** Implementation reference
> **Status:** Current QF channels plus target origin behavior
> **Last reviewed:** 2026-06-22

## Authentication

Authenticated clients request a short-lived WebSocket token through the REST auth
surface, then pass it as `?token=...`. HttpOnly access/refresh cookies never move to
JavaScript storage. Missing or invalid tokens close with policy code `1008`.

Tokens must be actor-scoped, short-lived, and revocable. Party sockets additionally
authorize current session membership. Logs never record query tokens.

## Current channels

| Channel | Endpoint | Purpose |
| --- | --- | --- |
| Notifications | `/qf/notifications/ws` | Player notifications and pings |
| Presence | `/qf/users/online/ws` | Online-user snapshots; REST polling fallback |
| Party | `/qf/party/{sessionId}/ws` | Read-only lobby/progress updates |

Party lifecycle actions still use REST. A WebSocket connection or client poll does
not own phase progression.

## Client lifecycle

`frontend/crowdcraft/src/hooks/useWebSocket.ts` shares one connection per path,
mints a token before connect, applies exponential backoff, and closes when no enabled
listeners remain. Providers decide which close codes stop reconnection.

On reconnect, the client fetches an authoritative projection. Reconnect must restore
the same membership, assignment, counters, votes, and deadlines; it never creates a
replacement round or resets state.

## Current and target origins

Today the shared hook falls back to the Heroku WebSocket host when no explicit
backend value is present. The Mac/Cloudflare target removes that fallback:

```text
https://quipflip.crowdcraftlabs.com → wss://quipflip.crowdcraftlabs.com
```

The same rule applies to each host. An absent production API/WS override selects
`window.location.origin`; do not set an empty value while the code uses `||`.

## Security and tests

Every channel needs tests for:

- missing, expired, malformed, and revoked token rejection;
- actor/session authorization and cross-game token isolation;
- bounded message size and rate limits;
- redacted logging;
- reconnect after token refresh and server restart;
- no retry loop on terminal auth failure; and
- private reconnect projections with forbidden fields absent.

The built-server smoke must connect real WebSocket clients through the same-origin
host and complete a QF Party reconnect flow.
