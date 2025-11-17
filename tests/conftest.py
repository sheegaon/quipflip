"""Pytest configuration and fixtures."""
import os
import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Ensure the application uses a dedicated SQLite database during tests
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
# Disable the phrase validator API for tests (use local validation instead)
os.environ["USE_PHRASE_VALIDATOR_API"] = "false"
# Disable sentence transformers for tests (use lightweight similarity instead)
os.environ["USE_SENTENCE_TRANSFORMERS"] = "false"

from backend.config import get_settings
from backend.database import Base


BASE_DIR = Path(__file__).resolve().parent.parent
TEST_DB_PATH = BASE_DIR / "test.db"
settings = get_settings()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """Apply database migrations against the test database."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    alembic_cfg = AlembicConfig(str(BASE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")

    yield

    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    # Use SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_app(test_engine):
    """Create test app with database override."""
    from backend.main import app
    from backend.database import get_db

    # Override the get_db dependency
    async def override_get_db():
        async_session = async_sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def player_factory(db_session):
    """Factory for creating test players with default credentials."""
    from backend.services import PlayerService
    from backend.utils.passwords import hash_password
    import uuid

    player_service = PlayerService(db_session)

    async def _create_player(
        username: str | None = None,
        email: str | None = None,
        password: str = "TestPassword123!",
    ):
        # Use UUID to ensure unique usernames/emails across all tests
        unique_id = str(uuid.uuid4())[:8]

        if username is None:
            username = f"player{unique_id}"
        if email is None:
            email = f"player{unique_id}@example.com"

        password_hash = hash_password(password)
        return await player_service.create_player(
            username=username,
            email=email,
            password_hash=password_hash,
        )

    return _create_player
