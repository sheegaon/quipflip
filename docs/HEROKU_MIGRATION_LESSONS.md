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

## Schema Changes & Table Renaming (November 2025)

### The Problem
When Phase 1 migration renamed Quipflip tables with the `qf_` prefix to prepare for Initial Reaction,
raw SQL queries in service layers (`round_service.py`, `cleanup_service.py`) were not updated.
This caused a 500 error in production on the `/api/player/dashboard` endpoint with the error
"no such table: rounds". SQLAlchemy ORM models correctly used the new table names, but raw SQL
queries still referenced old names.

### Lessons Learned
- **Update raw SQL when renaming tables.** Not just ORM models. When executing table renames via
  migration, systematically audit all raw SQL queries (Common Table Expressions, DELETE, UPDATE,
  SELECT statements) to ensure they reference the new table names. A single missed reference can
  break production endpoints.
- **Search comprehensively for SQL references.** After table renames, use grep/ripgrep to find
  all occurrences of old table names in raw SQL strings. Look for patterns like:
  - `FROM table_name` and `JOIN table_name`
  - `UPDATE table_name` and `DELETE FROM table_name`
  - References within CTEs (Common Table Expressions)
  This should be a required step before committing migration-related changes.
- **Keep migrations and models in sync.** Migration schema definitions must match model
  definitions exactly. Check for:
  - Missing columns (e.g., `revoked_at` on refresh tokens)
  - Missing foreign key constraints
  - Nullable field mismatches
  - Index definitions
  A mismatch between migration and model will cause runtime errors when the migration is applied.
- **Test production-critical queries after schema changes.** Run integration tests that exercise
  the affected endpoints (e.g., dashboard endpoint) to verify raw SQL queries work with the new
  table names before deployment.

## JWT Token Validation Using JTI Claim (November 2025)

### The Problem
Initial refresh token implementation generated a random token and hashed it for storage, but the
client received a JWT. When validating, the code tried to hash the JWT and compare it to the
stored hash—but the JWT is not the token that was hashed, so validation always failed.

### The Solution
Use the JWT's JTI (JWT ID) claim as the unique identifier instead:
1. Generate a unique token ID (UUID)
2. Include it as the `jti` claim in the JWT payload
3. Hash the token ID (JTI) and store that hash in the database
4. When validating, extract the JTI from the JWT payload, hash it, and compare to the stored hash

This ensures consistency: the client receives a JWT containing the JTI, and the server validates
by extracting the JTI from that same JWT.

### Code Pattern
```python
# Creating the token
jti = str(uuid.uuid4())  # Unique token identifier
payload = {
    "sub": player_id,
    "jti": jti,  # Include JTI in payload
    "exp": expiration_timestamp,
}
jwt_token = encode_jwt(payload, secret_key)
jti_hash = hash_token(jti)  # Store hash of JTI, not the entire token
# Save jti_hash to database

# Validating the token
decoded = decode_jwt(token, secret_key)
jti_from_token = decoded.get("jti")
jti_hash_computed = hash_token(jti_from_token)
# Compare jti_hash_computed with stored jti_hash
```

### Lessons Learned
- **JTI is the source of truth for token identity.** The JWT ID claim uniquely identifies a token;
  use it as the primary identifier in validation logic.
- **Hash the JTI for storage, not the entire token.** Storing a hash of the JTI (not the full
  JWT) is secure and avoids the circular problem of hashing a JWT that contains the JTI.
- **Token revocation via timestamps.** Instead of deleting tokens, set a `revoked_at` timestamp.
  This preserves audit trails and simplifies cleanup (e.g., delete tokens older than 30 days where
  `revoked_at IS NOT NULL`).

## FastAPI HTTP Parameter Annotations (November 2025)

### The Problem
An IR authentication dependency declared `authorization` and `ir_access_token` as plain optional
parameters. FastAPI treated them as query parameters instead of reading from HTTP headers and cookies.

### The Solution
Use FastAPI's `Header()` and `Cookie()` parameter annotations:
```python
async def get_ir_current_player(
    authorization: str | None = Header(None, alias="Authorization"),
    ir_access_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> IRPlayer:
    """Get current authenticated IR player from token."""
```

- `Header(None, alias="Authorization")` reads from the HTTP `Authorization` header
- `Cookie(None)` reads from HTTP cookies
- Without these annotations, FastAPI looks for query parameters instead

### Lessons Learned
- **Always use FastAPI parameter annotations for headers and cookies.** Plain optional parameters
  default to query parameters, which breaks authentication that relies on HTTP headers/cookies.
- **Use `alias` for canonical header names.** HTTP headers are case-insensitive but conventionally
  capitalized. Use `alias="Authorization"` to match the standard header name while allowing
  Python to use lowercase parameter names.
