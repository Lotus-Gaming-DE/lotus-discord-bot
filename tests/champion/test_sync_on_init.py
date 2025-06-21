import asyncio
import pytest

from cogs.champion.cog import ChampionCog
from cogs.champion.data import ChampionData
import cogs.champion.cog as champion_cog_mod
import log_setup


class DummyBot:
    def __init__(self):
        self.data = {"champion": {"roles": []}}
        self.main_guild = None
        self.guilds = []


@pytest.mark.asyncio
async def test_sync_called_on_init(monkeypatch, tmp_path):
    data = ChampionData(str(tmp_path / "points.db"))
    await data.add_delta("1", 5, "init")
    await data.add_delta("2", 3, "init")

    monkeypatch.setattr(champion_cog_mod, "ChampionData", lambda path: data)

    calls = []

    async def fake_apply(self, uid, score):
        calls.append((uid, score))

    tasks: list[asyncio.Task] = []

    def schedule_task(coro, logger=None):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    monkeypatch.setattr(log_setup, "create_logged_task", schedule_task)
    monkeypatch.setattr(
        champion_cog_mod.ChampionCog, "_apply_champion_role", fake_apply
    )

    bot = DummyBot()
    cog = ChampionCog(bot)

    await tasks[0]

    assert set(calls) == {("1", 5), ("2", 3)}

    cog.cog_unload()
    await data.close()
    await asyncio.gather(*tasks, return_exceptions=True)
    await cog.wait_closed()
