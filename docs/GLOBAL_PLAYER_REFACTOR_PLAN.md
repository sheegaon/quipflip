# Global Player Refactor Plan

## Goals
- Make the Player model truly global and game-agnostic while keeping game-specific state in per-game tables.
- Provide a single cross-game authentication flow that issues tokens without requiring a game type.
- Introduce a reusable `backend/services/player_service.py` that logs players into any game and orchestrates per-game player data creation.
- Remove implicit `GameType.QF` fallbacks and ensure code paths always handle explicit or inferred game context safely.
- Keep backward compatibility where possible through staged migrations and feature flagging.

## Phase 1: Discovery and Alignment
1. **Audit current Player model usage**
   - Map all imports of `models/player.py`, delegated fields, and `game_type` assumptions across services, routers, and tasks.
   - Inventory per-game player data tables (`backend/models/qf/player_data.py`, `backend/models/ir/player_data.py`, `backend/models/mm/player_data.py`) and their creation points.
   - Trace authentication flows in `backend/routers/auth.py`, `backend/services/auth_service.py`, and any game-specific auth helpers to understand token issuance and refresh handling.
2. **Confirm database expectations**
   - Review Alembic migrations for player and refresh token tables to identify constraints that encode game specificity.
   - Enumerate existing indexes/constraints that might assume a default game type (e.g., unique refresh tokens per game table).
3. **Align on contract changes**
   - Define the new global Player schema surface (fields retained vs. removed) and the per-game payloads expected by downstream clients.
   - Document token payload changes (claims, audience) for cross-game validity.

## Phase 2: Data Model Refactoring
1. **Globalize `models/player.py`**
   - Remove game-specific fields/properties (e.g., wallets, vaults, tutorial state) from the base model; keep only shared identity and auth fields.
   - Ensure relationships to per-game player data tables are explicit (one-to-one) without delegating attributes by default.
2. **Update per-game player data tables**
   - Adjust `QFPlayerData`, `IRPlayerData`, and `MMPlayerData` to own all game-specific state (balances, tutorials, lockouts, quest progress, results views, etc.).
   - Add helper methods or mixins for shared patterns (balances, tutorial flags) to reduce duplication.
3. **Refresh token + daily bonus models**
   - Unify refresh token storage under global tables if feasible, or clearly namespace per-game tables while keeping Player global.
   - Confirm `TransactionBase`, `ResultView`, quests, and notifications reference only the global player ID without game defaults.
4. **Schema migrations**
   - Write Alembic migrations to drop deprecated columns from `players`, add missing FKs/indexes for new relationships, and backfill per-game tables where data moves out of `players`.
   - Provide data migration scripts to move balances/tutorial fields into per-game tables with integrity checks.

## Phase 3: Service Layer Restructure
1. **Create `backend/services/player_service.py`**
   - Implement global player retrieval/creation helpers and a `login_player(game_type=None, ...)` entry that authenticates users and ensures per-game data exists on demand.
   - Encapsulate guest upgrade, password validation, and lockout logic in this service to be reusable by all games.
2. **Refactor `AuthService` for global auth**
   - Update `backend/services/auth_service.py` to authenticate against the global Player only, issuing tokens that are game-agnostic by default.
   - Remove implicit `GameType.QF` assumptions; require explicit game type for per-game entitlements and pass it through to `player_service` when needed.
3. **Router changes**
   - Rework `backend/routers/auth.py` endpoints to call the global service. Inputs should no longer require `game_type` (unless selecting a target game), and responses should include global player data plus any requested game-specific snapshots.
   - Ensure refresh/logout endpoints operate on global tokens and revoke across games where applicable.
4. **Per-game service updates**
   - Update QF/IR/MM services (round join, quest claim, bonuses) to load per-game player data explicitly via the new service rather than accessing delegated Player properties.
   - Remove any defaulting to `GameType.QF` in economics, notifications, and quest services.

## Phase 4: API and Client Integration
1. **API contract updates**
   - Version or annotate auth endpoints to reflect global tokens; update response schemas to separate global player fields from per-game data.
   - Provide transitional fields or shims for clients expecting delegated properties (e.g., optional `wallet` mirrors) guarded by a feature flag.
2. **Frontend adjustments**
   - Update frontend auth contexts to consume the new global auth payload and request per-game player data explicitly when entering a game.
   - Remove client-side assumptions about defaulting to Quipflip when `game_type` is absent.
3. **Documentation**
   - Update DATA_MODELS docs to describe the fully game-agnostic Player model and the new service/endpoint behavior.

## Phase 5: Testing and Rollout
1. **Test coverage**
   - Add unit tests for `player_service` global login flows, per-game data provisioning, and lockout edge cases.
   - Expand integration tests for `backend/routers/auth.py` to validate global token issuance and per-game data retrieval.
   - Regression-test per-game flows (round creation, payouts, quests) to ensure per-game data access works without delegated Player fields.
2. **Migration rehearsal**
   - Run migrations on a staging snapshot to verify data movement, backfills, and token compatibility.
   - Validate that legacy tokens either remain functional during the transition or are explicitly invalidated with clear UX.
3. **Gradual rollout**
   - Deploy behind a feature flag for global auth; enable per-environment and monitor error rates.
   - Provide rollback plan: retain old delegated properties temporarily or keep dual-write until confidence is high.

## Phase 6: Cleanup and Hardening
1. **Remove deprecated paths**
   - Delete legacy delegation properties from `Player` and any compatibility shims once clients are migrated.
   - Remove `GameType.QF` defaults across codebase and enforce explicit game selection where required.
2. **Performance and monitoring**
   - Add logging/metrics around cross-game login to detect anomalies across games.
   - Validate indexes for new access patterns (global tokens, per-game data joins) and optimize as needed.
3. **Security review**
   - Ensure token scopes, refresh revocation, and per-game entitlements are correctly enforced post-refactor.
   - Reconfirm admin flows and lockout logic operate globally.
