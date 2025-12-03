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

# Global Player Refactor – Phase 2.1 Plan (Global Player Model)

## Objective
Define the concrete refactor steps to make `backend/models/player.py` fully global and to move game-specific state into per-game tables without implicit defaults.

## Scope
- Player ORM model, per-game data models, and Alembic migrations for structural changes.
- Removal of implicit `GameType.QF` fallbacks tied to the player model.
- Compatibility shims and backfill steps required for downstream services that currently depend on delegated properties.

## Target State
- `Player` stores only cross-game identity and auth state (id, username, email, password_hash, admin/guest flags, ban/lockout metadata, feature flags, created/updated timestamps).
- Per-game tables (`qf_player_data`, `ir_player_data`, `mm_player_data`, `tl_player_data`) own all balances, tutorial flags, lockouts, quest/progression references, and other game-specific attributes.
- One-to-one relationships exist from `Player` to per-game tables but no delegated properties or implicit auto-creation on attribute access.
- Service layer accesses per-game attributes explicitly via per-game data accessors or the forthcoming `player_service` orchestration.

## Changes to `backend/models/player.py`
1. **Remove delegated properties/relationships**
   - Delete wallet/vault accessors, tutorial properties, per-game lockout helpers, and quest/progression delegates.
   - Keep only explicit `relationship` definitions to per-game tables (lazy='selectin') for targeted loading; remove `association_proxy`/property shims that hide per-game ownership.
2. **Normalize identity fields**
   - Ensure columns remain: `id`, `username`, `email`, `password_hash`, `is_admin`, `is_guest`, `is_banned`, `ban_reason`, `ban_expires_at`, `lockout_expires_at`, `phone_number`, `feature_flags`, `created_at`, `updated_at`.
   - Drop any per-game status columns if discovered (none expected but verify migrations).
3. **Relationship hygiene**
   - Configure relationships to per-game data classes with `uselist=False`, `cascade="all, delete-orphan"`, and `post_update=False`; avoid backrefs that recreate delegated convenience properties.
   - Add explicit helper methods (non-property) for optional eager creation to be used by `player_service` only, not via attribute access.
4. **Defaults and game assumptions**
   - Remove any default `game_type` arguments in model helpers or constructors; rely on callers to pass explicit game context when needed.

## Per-Game Data Model Updates
1. **Ownership of state**
   - Ensure each per-game model includes: balances/wallet/vault, tutorial/quest status, lockout flags, onboarding markers, and any per-game cooldown fields currently delegated from `Player`.
   - Add nullable columns where data migrates from `Player` and is not yet present in the per-game table; prefer explicit defaults over silent inference.
2. **Consistency utilities**
   - Create lightweight mixins/utilities for repeated patterns (balance operations, tutorial/completion timestamps) to reduce duplication across QF/IR/MM/TL models.
3. **Indexes and constraints**
   - Validate PK/FK alignment (player_id as PK, FK to `players` with CASCADE). Add unique constraints or indexes for frequently queried fields if removed from `Player` (e.g., tutorial completion timestamps per game as needed).

## Alembic Migration Tasks
1. **Schema changes**
   - Drop migrated per-game columns from `players` (if any) and add missing columns to per-game tables to receive data.
   - Add or adjust FKs/indexes reflecting new ownership; confirm no `game_type` defaults encoded in constraints.
2. **Data migration/backfill**
   - Backfill per-game tables with data currently delegated from `Player`; run in an idempotent script with chunking and logging.
   - Guard with feature flag/transactional batches; verify row counts per table against affected players.
3. **Rollback plan**
   - Provide reversible migrations that re-add dropped columns and rehydrate data from per-game tables if needed.

## Service/Router Guardrails
- Update service entry points (e.g., `AuthService`, `get_current_player`, WebSocket helpers) to fetch per-game data explicitly rather than relying on delegated Player properties.
- Remove `GameType.QF` defaults when instantiating model-aware services; require explicit game selection or use global-only flows.
- Add temporary compatibility accessors (e.g., `Player.get_game_data(game_type)`) that raise clear errors when called without a game context to expose missing refactors during transition.

## Risk & Validation Checklist
- Validate no ORM queries fail due to removed delegated properties; add lint/unit coverage for top routes/services touching player data.
- Confirm migrations preserve referential integrity and that per-game data row counts match player population for each active game.
- Monitor for performance regressions from additional joins; add selectinload patterns where necessary and ensure indexes exist on new per-game columns.

## Deliverables for Phase 2.1
- Updated `backend/models/player.py` and per-game data models reflecting the ownership changes above.
- Alembic migration scripts for schema and data movement, including rollback steps.
- Compatibility helpers and service call-site adjustments to remove `GameType.QF` defaults tied to the player model.
- A validation checklist to execute post-migration before proceeding to service-layer refactors (Phase 2.2/3).

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

# Global Player Refactor – Phase 2 Completion Notes

## What changed in Phase 2
- **Game-specific data fully isolated:** The unified `Player` model now requires explicit per-game access; no delegated balance/tutorial properties remain.
- **Per-game state migration:** Added Alembic migration `0f5c7c89f4bb_phase2_player_data_cleanup.py` to backfill Quipflip player data rows from any legacy columns on `players` and drop those global columns to keep the table game-agnostic.
- **Documentation alignment:** Updated `docs/DATA_MODELS.md` to reflect the explicit per-game data access pattern and removal of implicit Quipflip defaults.

## Migration expectations
- The migration uses dialect-aware column checks (per `HEROKU_MIGRATION_LESSONS.md`) before dropping columns to stay compatible with environments that already removed the fields.
- During `upgrade`, missing `qf_player_data` rows are created from legacy player columns when present. When the legacy columns are absent, safe defaults are used so the insert is idempotent.
- During `downgrade`, the migration restores the dropped columns (with sensible defaults) and rehydrates them from `qf_player_data` when available.

## Operational guidance
- Run `alembic upgrade head` before deploying Phase 3. If the migration chain reports multiple heads, resolve them or run `tests/test_migration_chain.py` locally to ensure a single head following Heroku migration guidance.
- After applying the migration, verify that `players` no longer contains wallet/tutorial/lockout columns and that `qf_player_data` has a row for every player.
- Services must access per-game data explicitly (`player.get_game_data(game_type)` or service-level fetchers); do not assume `GameType.QF` defaults anywhere.
