# Global Player Refactor – Phase 1 Findings

## Scope
This document captures the Phase 1 discovery work for globalizing the Player model and authentication flows. It summarizes the current code-level realities, database expectations, and the contract changes required before proceeding to schema/service refactors.

## Audit Findings
- **Player model still delegates game-specific state** via relationships and property shims to Quipflip and ThinkLink tables, meaning `Player` implicitly owns QF/TL-specific behaviors (wallets, tutorials, lockouts) instead of being strictly global. 【F:backend/models/player.py†L38-L249】
- **Auth router assumes Quipflip as the default game** for login, username login, refresh, and logout by hard-coding `GameType.QF` when constructing `AuthService`, which blocks a truly global login surface. 【F:backend/routers/auth.py†L33-L168】
- **WebSocket token helper iterates over games but still relies on per-game AuthService** instances, reinforcing the need for a global player service/token path. 【F:backend/routers/auth.py†L172-L218】
- **AuthService is parameterized by `game_type` and loads game-specific player services** for creation/quest initialization; global auth is not yet centralized and defaults to QF when unspecified. 【F:backend/services/auth_service.py†L44-L165】
- **Per-game player data tables remain separate and contain wallets/tutorial/lockout fields**, with single-row-per-player constraints via PK/FK to `players`. These tables currently back the delegated properties on `Player`. 【F:backend/models/qf/player_data.py†L16-L60】【F:backend/models/ir/player_data.py†L16-L45】【F:backend/models/mm/player_data.py†L16-L47】
- **Refresh tokens are already stored in a unified `refresh_tokens` table** keyed to `players`, implying DB support for global sessions even though services still request a game type. 【F:backend/models/refresh_token.py†L15-L49】

## Database Expectations (Current State)
- **Players table**: global identity/authentication columns (username, email, password_hash, admin/guest flags, lockouts) with unique constraints on username/email. Delegated game state is not stored here but accessed via relationships. 【F:backend/models/player.py†L23-L184】
- **Game-specific player data**: `qf_player_data`, `ir_player_data`, `mm_player_data`, and `tl_player_data` each require a `player_id` FK/PK, enforce CASCADE deletes, and own per-game wallet, vault, tutorial, and lockout fields. 【F:backend/models/qf/player_data.py†L23-L57】【F:backend/models/ir/player_data.py†L23-L41】【F:backend/models/mm/player_data.py†L23-L45】【F:backend/models/tl/player_data.py†L23-L43】
- **Auth/session storage**: `refresh_tokens` table is global (player_id FK with CASCADE, indexed token hash) and supports SSO semantics without per-game scoping. 【F:backend/models/refresh_token.py†L15-L49】
- **Implicit defaults**: Service constructors and dependencies default to `GameType.QF`, meaning many code paths will bind to Quipflip-specific behaviors unless explicitly overridden. 【F:backend/routers/auth.py†L33-L168】【F:backend/services/auth_service.py†L44-L165】

## Contract Changes Needed for Globalization
1. **Authentication & tokens**
   - Expose global login/refresh/logout endpoints that do not require `game_type` and issue tokens scoped to the player, not a specific game. Tokens should remain valid across games with audience/claims aligned accordingly. 【F:backend/routers/auth.py†L33-L168】【F:backend/services/auth_service.py†L44-L165】
   - Centralize token decoding/creation to a game-agnostic service (`player_service.py`) and remove the default `GameType.QF` assumption when resolving the player from cookies/headers.
2. **Player model boundaries**
   - Strip delegated QF/TL properties from `Player` and relocate wallets/tutorial/lockout fields to per-game data classes, keeping `Player` limited to identity, credentials, and account-level flags. 【F:backend/models/player.py†L38-L249】【F:backend/models/qf/player_data.py†L16-L60】【F:backend/models/tl/player_data.py†L16-L43】
   - Maintain one-to-one relationships from `Player` to per-game data without auto-creation shims to avoid silent QF coupling.
3. **Service layer**
   - Introduce `backend/services/player_service.py` that handles global login/lookup and conditionally provisions per-game data, replacing the current per-game AuthService branching. 【F:backend/services/auth_service.py†L44-L165】
   - Update dependencies (e.g., `get_current_player`) and websocket token issuance to rely on the global service and a single token format. 【F:backend/routers/auth.py†L172-L218】
4. **Database/contracts**
   - Plan migrations to remove any residual game-specific columns from `players` (none today) and ensure per-game tables include all necessary fields for refactored ownership. 【F:backend/models/player.py†L23-L184】【F:backend/models/qf/player_data.py†L23-L57】【F:backend/models/tl/player_data.py†L23-L43】
   - Clarify API responses to return global player fields plus optional per-game snapshots so clients no longer expect delegated properties.
