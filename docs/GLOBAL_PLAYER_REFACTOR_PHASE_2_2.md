# Global Player Refactor – Phase 2.2 Implementation Notes (Auth Guardrails)

## Objective
Reduce remaining implicit `GameType.QF` coupling in authentication/token handling so global player tokens can be decoded without assuming a default game.

## Changes Implemented
- **AuthService constructor** now accepts an optional `game_type`, instantiating per-game player services only when needed and exposing a `game_type_required` error when creation flows forget to pass context.
- **Token decoding call sites** (shared dependencies, notifications WebSocket auth, IR dependencies, online users WebSocket auth, and middleware activity tracking) now use a game-agnostic `AuthService` for JWT decode, eliminating fallback loops over QF/IR secrets.
- **Middleware inference** determines game type from request path prefixes for user-activity writes instead of defaulting to QF, skipping writes when the path is ambiguous.

## Impact and Follow-Ups
- Global tokens can be decoded uniformly without per-game configuration; registration/guest flows still require explicit `game_type` until the cross-game player_service orchestration lands in later phases.
- User activity tracking and online users WebSockets now map the decoded player to a game by inspecting request paths or existing per-game player records; tokens lacking per-game context will no longer silently default to QF.
- Next steps (Phase 3) can rely on the relaxed constructor to plug in the new cross-game player service while keeping backward-compatible per-game creation paths guarded by `game_type_required`.
