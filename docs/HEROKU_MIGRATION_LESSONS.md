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

- **Audit raw SQL queries when renaming tables.** When executing table renames via migration,
  systematically search for all raw SQL references (in CTEs, DELETE, UPDATE, SELECT statements).
  Use grep/ripgrep with patterns like `FROM table_name`, `JOIN table_name`, and `DELETE FROM table_name`.
  A single missed reference can break production endpoints (e.g., the November 2025 dashboard 500 error).
- **Keep migrations and models in sync.** Migration schema definitions must match model definitions exactly.
  Check for missing columns, missing foreign key constraints, nullable field mismatches, and indexes.
  A mismatch will cause runtime errors when the migration is applied.
- **Use JTI claim for token identity.** When implementing JWT refresh tokens, include a unique JTI (JWT ID)
  claim in the payload, hash the JTI for storage, and validate by extracting and hashing the JTI from the token.
  This avoids the circular problem of hashing a JWT that contains the JTI itself.
- **Always use FastAPI parameter annotations for headers/cookies.** Use `Header()` and `Cookie()` annotations
  in dependency functions (e.g., `authorization: str | None = Header(None, alias="Authorization")`).
  Plain optional parameters default to query parameters, breaking HTTP header/cookie-based authentication.
- **Avoid exception handling for DDL statements in async migrations.** When using SQLAlchemy with asyncpg,
  failed DDL statements (like `ALTER TABLE`) leave the transaction in a failed state. Using try-except around
  DDL can corrupt the transaction, causing all subsequent database operations to fail with "current transaction
  is aborted, commands ignored until end of transaction block" errors. Instead, check preconditions BEFORE
  executing DDL using dialect-aware schema inspection.
- **Use dialect-aware schema inspection in migrations.** PostgreSQL and SQLite have different ways to check
  if a table or column exists. PostgreSQL uses `information_schema.columns`, while SQLite uses `PRAGMA table_info()`.
  When writing migrations that should work on both databases, detect the database dialect and use the appropriate
  query method:
  ```python
  def column_exists(connection, table_name, column_name):
      dialect = connection.dialect.name

      if dialect == 'postgresql':
          result = connection.execute(
              sa.text("""
                  SELECT EXISTS (
                      SELECT FROM information_schema.columns
                      WHERE table_name = :table_name AND column_name = :column_name
                  )
              """),
              {"table_name": table_name, "column_name": column_name}
          )
          return result.scalar()
      elif dialect == 'sqlite':
          result = connection.execute(
              sa.text(f"PRAGMA table_info({table_name})")
          )
          columns = [row[1] for row in result.fetchall()]
          return column_name in columns
      return False
  ```
  Use this precondition check in upgrade/downgrade to avoid attempting DDL on non-existent or existing columns.
- **Validate API contracts between frontend and backend.** Frontend TypeScript interfaces must exactly match
  backend Pydantic request models in both field names and field presence. A missing field in the frontend
  request will cause backend validation errors (422 Unprocessable Entity). Use your type system to catch
  these mismatches at compile time: ensure all request/response types are fully typed and match the backend
  API specification. This is especially important for authentication endpoints where contract mismatches can
  prevent users from signing up or logging in.
- **Use `.bindparams()` for parameterized queries in migrations.** Modern SQLAlchemy (1.4+) in Alembic requires
  using `.bindparams()` on text objects instead of passing parameters as a second argument to `op.execute()`.
  The old syntax:
  ```python
  op.execute(sa.text("INSERT INTO ... VALUES (:id, :name)"), {"id": val1, "name": val2})  # WRONG
  ```
  Should be:
  ```python
  op.execute(sa.text("INSERT INTO ... VALUES (:id, :name)").bindparams(id=val1, name=val2))  # CORRECT
  ```
  This applies to all parameterized queries (INSERT, UPDATE, SELECT) in migration code. Failure to use
  `.bindparams()` results in `TypeError: execute() takes 2 positional arguments but 3 were given` when
  running migrations on Heroku or any PostgreSQL deployment.
