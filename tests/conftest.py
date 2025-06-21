import os
import sys
import pytest
import pytest_asyncio
import discord

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("server_id", "0")


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

        import log_setup

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


@pytest_asyncio.fixture
async def bot():
    """Yield a ``MyBot`` instance and ensure it is properly closed."""
    from bot import MyBot

    bot = MyBot()
    try:
        yield bot
    finally:
        await bot.close()
