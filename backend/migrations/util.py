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


def get_uuid_default():
    """Get the appropriate server default for UUID generation.

    Returns:
        Server default compatible with the current database dialect:
        - PostgreSQL: gen_random_uuid() function
        - SQLite/other: None (UUID generation handled in Python)
    """
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == 'postgresql':
        return sa.text('gen_random_uuid()')
    else:
        return None


def get_timestamp_default():
    """Get the appropriate server default for timestamp columns.

    Returns:
        Server default compatible with the current database dialect:
        - PostgreSQL: NOW() function
        - SQLite: CURRENT_TIMESTAMP
    """
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    if dialect_name == 'postgresql':
        return sa.text('NOW()')
    else:
        return sa.text('CURRENT_TIMESTAMP')
