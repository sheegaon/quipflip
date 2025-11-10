# Heroku Migration Lessons Learned

## Context
In October 2025 a Heroku deployment failed because the release phase could not
locate the Alembic revision identifier `guest_lockout_001`. Production
instances had been manually stamped with that identifier even though the
repository lacked a corresponding migration file. As a result, `alembic upgrade`
aborted during deploy.

## Lessons Learned
- **Track every historic revision identifier.** Even if a revision was created
  only in production, we must backfill a placeholder migration in version
  control so Alembic can resolve the revision graph.
- **Keep the migration chain linear.** Reconnecting the downstream guest vote
  lockout migration to point at the placeholder guarantees that upgrades follow
  a single, ordered path.
- **Test for gaps proactively.** The migration chain sanity test now accepts
  non-hex revision identifiers, so it will flag missing files like
  `guest_lockout_001` before they reach production.
- **Match UUID column types across database dialects.** When creating foreign
  keys to UUID columns, ensure the column types match the target database
  dialect. PostgreSQL uses native UUID types, while SQLite uses String(36).
  Use dialect detection to select the correct type.
- **Avoid duplicate migration files.** Multiple files with the same revision ID
  will cause "Multiple head revisions" errors that prevent deployment. Always
  ensure migration file renames are complete (delete old files) and verify with
  `alembic heads` that only one head exists.
- **Follow Alembic naming conventions.** Migration files should follow the
  pattern `{revision}_{description}.py` (e.g., `b2c3d4e5f8a9_add_user_table.py`).
  Non-standard names like `add_user_activity_001_description.py` can cause
  revision lookup failures and should be renamed to the proper format.
- **Update database revision tracking after file renames.** When renaming
  migration files, remember to update the `alembic_version` table in the
  database to match the new revision ID, otherwise Alembic will report
  "Can't locate revision identified by 'old_name'" errors.
- **Enhance migration tests for merge scenarios.** The migration chain test
  should properly parse tuple `down_revision` values for merge migrations
  (e.g., `('rev1', 'rev2')`) to avoid false positive multiple heads detection.

## Practical Takeaways
- Add a no-op migration that mirrors any production-only revision identifier
  before deploying further schema changes.
- Re-run `pytest tests/test_migration_chain.py` after adjusting migrations to
  verify that the repository still forms a single head.
- Review historical deployment logs to uncover similar manually stamped
  revisions and backfill them before they block future releases.
- **Always run `alembic heads` before deployment** to verify you have exactly
  one migration head. Multiple heads indicate a branched migration chain that
  will cause deployment failures.
- **When renaming migration files**, follow this process:
  1. Rename the file to follow Alembic conventions
  2. Update the database: `UPDATE alembic_version SET version_num = 'new_revision_id'`
  3. Verify with `alembic heads` that you have one clean head
  4. Delete any duplicate files completely
- When creating migrations with UUID foreign keys, use the `get_uuid_type()`
  helper function from `backend.migrations.util`:
  ```python
  from backend.migrations.util import get_uuid_type

  def upgrade() -> None:
      uuid = get_uuid_type()
      op.create_table(
          'my_table',
          sa.Column('id', uuid, nullable=False),
          sa.Column('foreign_id', uuid, nullable=True),
          ...
      )
  ```
  This helper automatically selects the correct type based on the database
  dialect (PostgreSQL: native UUID, SQLite: String(36)), ensuring
  compatibility across both local development and production environments.
  Using this shared helper function improves maintainability and consistency
  across all migrations.
