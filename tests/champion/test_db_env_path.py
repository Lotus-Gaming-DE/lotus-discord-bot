import pytest
import lotus_bot.cogs.champion.cog as champion_cog_mod
import lotus_bot.log_setup as log_setup
from lotus_bot.cogs.champion.cog import ChampionCog


class DummyBot:
    def __init__(self):
        self.data = {"champion": {"roles": []}}
        self.main_guild = None
        self.guilds = []


@pytest.mark.asyncio
async def test_env_db_path(monkeypatch, patch_logged_task, tmp_path):
    path = tmp_path / "custom.db"
    monkeypatch.setenv("CHAMPION_DB_PATH", str(path))
    patch_logged_task(champion_cog_mod, log_setup)

    bot = DummyBot()
    cog = ChampionCog(bot)

    assert cog.data.db_path == str(path)

    await cog.cog_unload()
    await cog.wait_closed()
