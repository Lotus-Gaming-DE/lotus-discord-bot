import logging
import json
import pytest
import aiosqlite

import lotus_bot.cogs.champion.cog as champion_cog_mod
from lotus_bot.cogs.champion.cog import ChampionCog
from lotus_bot.cogs.champion.data import ChampionData
import lotus_bot.log_setup as log_setup


class DummyBot:
    def __init__(self):
        self.data = {"champion": {"roles": []}}
        self.main_guild = None
        self.guilds = []


@pytest.mark.asyncio
async def test_update_user_score_db_error(
    monkeypatch, patch_logged_task, tmp_path, caplog
):
    patch_logged_task(champion_cog_mod, log_setup)
    bot = DummyBot()
    cog = ChampionCog(bot)
    cog.data = ChampionData(str(tmp_path / "points.db"))

    async def fail(*args, **kwargs):
        raise aiosqlite.Error("boom")

    monkeypatch.setattr(cog.data, "add_delta", fail)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            await cog.update_user_score(1, 1, "test")

    events = [json.loads(r.getMessage()).get("event", "") for r in caplog.records]
    assert any("DB error" in e for e in events)

    await cog.cog_unload()
    await cog.wait_closed()
