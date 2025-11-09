"""Utility functions for Alembic migrations."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op


def get_uuid_type():
    """Get the appropriate UUID column type for the current database dialect.

    Returns:
        Column type compatible with the current database dialect:
        - PostgreSQL: native UUID type (with as_uuid=True for Python UUID objects)
        - SQLite/other: String(36) for hex-formatted UUID strings

    Example usage in a migration:
        from backend.migrations.util import get_uuid_type

        def upgrade() -> None:
            uuid = get_uuid_type()
            op.create_table(
                'my_table',
                sa.Column('id', uuid, nullable=False),
                sa.Column('foreign_id', uuid, nullable=True),
                ...
            )
    """
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == 'postgresql':
        return UUID(as_uuid=True)
    else:
        return sa.String(length=36)
