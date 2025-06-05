import os
import sys
import asyncio
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from cogs.champion.cog import ChampionCog
from cogs.champion.data import ChampionData


class DummyBot:
    def __init__(self):
        self.data = {"champion": {"roles": []}}
        self.main_guild = None
        self.guilds = []


@pytest.mark.asyncio
async def test_update_user_score_saves_and_calls(monkeypatch, tmp_path):
    bot = DummyBot()
    cog = ChampionCog(bot)
    cog.data = ChampionData(str(tmp_path / "points.db"))

    called = []

    async def fake_apply(user_id, score):
        called.append((user_id, score))

    def fake_task(coro, logger):
        asyncio.create_task(coro)

    monkeypatch.setattr("cogs.champion.cog.create_logged_task", fake_task)
    monkeypatch.setattr(cog, "_apply_champion_role", fake_apply)

    total = await cog.update_user_score(123, 5, "test")
    await asyncio.sleep(0)
    assert total == 5
    assert called == [("123", 5)]


def test_get_current_role():
    bot = DummyBot()
    bot.data["champion"]["roles"] = [
        {"name": "Gold", "threshold": 50},
        {"name": "Silver", "threshold": 20},
    ]
    cog = ChampionCog(bot)

    assert cog.get_current_role(55) == "Gold"
    assert cog.get_current_role(25) == "Silver"
    assert cog.get_current_role(10) is None
