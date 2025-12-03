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
