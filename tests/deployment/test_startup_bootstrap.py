import pytest

import backend.main as main_module


pytestmark = pytest.mark.owner_platform


@pytest.mark.asyncio
async def test_run_startup_bootstrap_invokes_expected_steps(monkeypatch):
    calls: list[str] = []

    class FakeSessionContext:
        async def __aenter__(self):
            calls.append("open_session")
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            calls.append("close_session")
            return False

    class FakeSessionFactory:
        def __call__(self):
            return FakeSessionContext()

    async def record(name: str, *_args, **_kwargs):
        calls.append(name)

    monkeypatch.setattr(main_module, "sync_prompts_with_database", lambda: record("sync_prompts"))
    monkeypatch.setattr(main_module, "initialize_missing_player_quests", lambda: record("init_quests"))
    monkeypatch.setattr(main_module, "import_meme_mint_images", lambda: record("mm_images"))
    monkeypatch.setattr(main_module, "seed_prompts", lambda db: record("seed_prompts", db))
    monkeypatch.setattr(main_module, "seed_answers", lambda db: record("seed_answers", db))
    monkeypatch.setattr(main_module, "cleanup_tl_prompts", lambda db: record("cleanup_tl_prompts", db))
    monkeypatch.setattr("backend.database.AsyncSessionLocal", FakeSessionFactory())

    await main_module.run_startup_bootstrap()

    assert calls == [
        "sync_prompts",
        "init_quests",
        "mm_images",
        "open_session",
        "seed_prompts",
        "close_session",
        "open_session",
        "seed_answers",
        "close_session",
        "open_session",
        "cleanup_tl_prompts",
        "close_session",
    ]


@pytest.mark.asyncio
async def test_maybe_run_startup_bootstrap_skips_production(monkeypatch):
    called = False

    async def fake_bootstrap():
        nonlocal called
        called = True

    monkeypatch.setattr(main_module.settings, "environment", "production", raising=False)
    monkeypatch.setattr(main_module, "run_startup_bootstrap", fake_bootstrap)

    await main_module.maybe_run_startup_bootstrap()

    assert called is False
