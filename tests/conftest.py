"""Pytest configuration and fixtures."""
import atexit
import asyncio
import os
import random
import socket
import tempfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Ensure each pytest run uses a dedicated, file-backed SQLite database.
_test_database_directory = tempfile.TemporaryDirectory(prefix="crowdcraft-pytest-")
atexit.register(_test_database_directory.cleanup)
TEST_DB_PATH = Path(_test_database_directory.name) / "deterministic.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
# Disable the phrase validator API for tests (use local validation instead)
os.environ["USE_PHRASE_VALIDATOR_API"] = "false"
os.environ["USE_SENTENCE_TRANSFORMERS"] = "false"
os.environ.setdefault("CROWDCRAFT_TEST_SEED", "20260622")

from backend.config import get_settings


BASE_DIR = Path(__file__).resolve().parent.parent
get_settings.cache_clear()
settings = get_settings()


def pytest_collection_modifyitems(items):
    """Assign exactly one tier and one owning subsystem to every test."""
    tier_markers = {"deterministic", "sqlite_integration", "smoke", "stress", "external"}
    owner_markers = {"owner_qf", "owner_mm", "owner_ir", "owner_tl", "owner_party", "owner_platform"}

    for item in items:
        path = str(item.path).replace("\\", "/")
        filename = item.path.name
        existing = {marker.name for marker in item.iter_markers()}

        if not existing.intersection(tier_markers):
            if "/sqlite_integration/" in path:
                item.add_marker(pytest.mark.sqlite_integration)
            elif filename == "test_tl_similarity_debug.py":
                item.add_marker(pytest.mark.external)
            elif filename == "test_stress_localhost.py":
                item.add_marker(pytest.mark.stress)
                item.add_marker(pytest.mark.localhost)
            elif "_localhost" in filename:
                item.add_marker(pytest.mark.smoke)
                item.add_marker(pytest.mark.localhost)
            else:
                item.add_marker(pytest.mark.deterministic)

        if not existing.intersection(owner_markers):
            if "/party/" in path or "party" in filename:
                item.add_marker(pytest.mark.owner_party)
            elif filename.startswith("test_mm_"):
                item.add_marker(pytest.mark.owner_mm)
            elif filename.startswith("test_ir_"):
                item.add_marker(pytest.mark.owner_ir)
            elif filename.startswith("test_tl_"):
                item.add_marker(pytest.mark.owner_tl)
            elif filename in {
                "test_migration_chain.py",
                "test_code_quality_improvements.py",
                "test_datetime_helpers.py",
                "test_rate_limiting.py",
                "test_simple_cache.py",
                "test_timezone_awareness.py",
                "test_verification_contract.py",
            }:
                item.add_marker(pytest.mark.owner_platform)
            else:
                item.add_marker(pytest.mark.owner_qf)


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """Apply database migrations against the test database."""
    alembic_cfg = AlembicConfig(str(BASE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(alembic_cfg, "head")

    yield


@pytest.fixture(autouse=True)
def isolate_process_globals(request, monkeypatch):
    """Reset mutable singleton state and prohibit network in deterministic tests."""
    if request.node.get_closest_marker("deterministic") is None:
        yield
        return

    seed = int(os.environ["CROWDCRAFT_TEST_SEED"])
    random.seed(seed)

    from backend.services import phrase_validator
    from backend.services.tl import dependencies as tl_dependencies
    from backend.utils import lock_client, queue_client
    from backend.utils.cache import dashboard_cache

    phrase_validator._phrase_validator = None
    dashboard_cache.clear()
    queue_client.reset()
    lock_client.reset()
    for dependency in (
        tl_dependencies.get_matching_service,
        tl_dependencies.get_scoring_service,
        tl_dependencies.get_prompt_service,
        tl_dependencies.get_clustering_service,
        tl_dependencies.get_round_service,
    ):
        dependency.cache_clear()

    def deny_network(*_args, **_kwargs):
        raise RuntimeError(
            "Unexpected network access in deterministic tests. "
            "Mock the provider boundary or use the smoke/external tier."
        )

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)
    yield

    dashboard_cache.clear()
    queue_client.reset()
    lock_client.reset()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine using the same database as migrations."""
    # Use the same database URL as the migrations
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        # Add connection pooling settings to help with cleanup
        pool_pre_ping=True,
        pool_recycle=300,
    )

    yield engine

    # Properly dispose of the engine to close all connections
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.connect() as connection:
        existing_tables = await connection.run_sync(
            lambda sync_connection: set(
                inspect(sync_connection).get_table_names()
            )
        )
        await connection.execute(text("PRAGMA foreign_keys=OFF"))
        await connection.commit()
        for table_name in sorted(existing_tables - {"alembic_version"}):
            await connection.execute(text(f'DELETE FROM "{table_name}"'))
        await connection.commit()
        await connection.execute(text("PRAGMA foreign_keys=ON"))
        assert await connection.scalar(text("PRAGMA foreign_keys")) == 1

    async with async_session() as session:
        yield session
        # Ensure transaction is rolled back and session is closed
        await session.rollback()
        await session.close()


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
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def player_factory(db_session):
    """Factory for creating test players with default credentials."""
    from backend.services import QFPlayerService
    from backend.utils.passwords import hash_password
    import uuid

    player_service = QFPlayerService(db_session)

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
