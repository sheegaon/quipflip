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

## Practical Takeaways
- Add a no-op migration that mirrors any production-only revision identifier
  before deploying further schema changes.
- Re-run `pytest tests/test_migration_chain.py` after adjusting migrations to
  verify that the repository still forms a single head.
- Review historical deployment logs to uncover similar manually stamped
  revisions and backfill them before they block future releases.
- When creating migrations with UUID foreign keys, use the dialect detection
  pattern from the initial schema migration:
  ```python
  bind = op.get_bind()
  dialect_name = bind.dialect.name
  if dialect_name == 'postgresql':
      uuid = sa.UUID()
  else:
      uuid = sa.String(length=36)
  ```
  Then use the `uuid` variable for all UUID columns to ensure compatibility.
