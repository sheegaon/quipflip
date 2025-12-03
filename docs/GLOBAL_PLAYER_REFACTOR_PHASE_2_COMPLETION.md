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
