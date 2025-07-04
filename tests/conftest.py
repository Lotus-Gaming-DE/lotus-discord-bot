import os
import sys
import pytest
import pytest_asyncio
import discord
import asyncio
import json
from pathlib import Path

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def event_loop():
    """Create a dedicated event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
for path in (SRC, ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("server_id", "0")


@pytest.fixture(autouse=True, scope="session")
def configure_logging():
    import lotus_bot.log_setup as log_setup

    log_setup.setup_logging("INFO")


class DummyTask:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


@pytest.fixture
def patch_logged_task(monkeypatch):
    """Patch ``create_logged_task`` globally and in additional modules."""

    def apply(*modules):
        def fake_task(coro, logger=None):
            coro.close()
            return DummyTask()

        import lotus_bot.log_setup as log_setup

        monkeypatch.setattr(log_setup, "create_logged_task", fake_task)
        for module in modules:
            monkeypatch.setattr(module, "create_logged_task", fake_task, raising=False)

        return fake_task

    return apply


@pytest.fixture(autouse=True)
def auto_stop_views(monkeypatch):
    """Stop all ``discord.ui.View`` instances created during tests."""

    created: list[discord.ui.View] = []
    original_init = discord.ui.View.__init__

    def init(self, *args, **kwargs):
        kwargs.setdefault("timeout", None)
        original_init(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(discord.ui.View, "__init__", init)

    yield

    for view in created:
        try:
            view.stop()
        except Exception:
            pass


@pytest_asyncio.fixture(autouse=True)
async def assert_no_tasks():
    """Ensure that tests do not leave running tasks behind."""

    yield

    current = asyncio.current_task()
    stray = [t for t in asyncio.all_tasks() if t is not current and not t.done()]

    assert not stray, f"Stray tasks detected: {stray}"


@pytest_asyncio.fixture
async def wcr_data(monkeypatch):
    """Load WCR data from local JSON files and patch API fetcher."""

    async def fake_fetch(base_url: str):
        base = Path("tests/data")
        units = json.load(open(base / "wcr_units.json", encoding="utf-8"))
        categories = json.load(open(base / "wcr_categories.json", encoding="utf-8"))
        meta = json.load(open("data/wcr/faction_meta.json", encoding="utf-8"))
        meta_map = {
            m["id"]: {k: m[k] for k in ("icon", "color") if k in m}
            for m in meta.get("factions", [])
        }
        combinations = meta.get("combinations", {})
        for faction in categories.get("factions", []):
            faction.update(meta_map.get(faction.get("id"), {}))

        return {
            "units": {"units": units},
            "categories": categories,
            "faction_combinations": combinations,
        }

    monkeypatch.setattr("lotus_bot.cogs.wcr.utils.fetch_wcr_data", fake_fetch)
    from lotus_bot.cogs.wcr.utils import load_wcr_data

    return await load_wcr_data("http://test")


@pytest_asyncio.fixture
async def bot():
    """Yield a ``MyBot`` instance and ensure it is properly closed."""
    from lotus_bot.bot import MyBot

    bot = MyBot()
    try:
        yield bot
    finally:
        await bot.close()
