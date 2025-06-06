import pytest

from cogs.champion.cog import ChampionCog
from cogs.champion.data import ChampionData
from cogs.champion.slash_commands import syncroles


class DummyBot:
    def __init__(self):
        self.data = {"champion": {"roles": []}}
        self.main_guild = None
        self.guilds = []
        self._cog = None

    def get_cog(self, name):
        return self._cog if name == "ChampionCog" else None


class DummyResponse:
    def __init__(self):
        self.deferred = False

    async def defer(self, thinking=False):
        self.deferred = thinking


class DummyFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, message):
        self.sent.append(message)


class DummyInteraction:
    def __init__(self, bot):
        self.user = "tester"
        self.client = bot
        self.response = DummyResponse()
        self.followup = DummyFollowup()
        self.guild = None


@pytest.mark.asyncio
async def test_syncroles_processes_all_users(monkeypatch, tmp_path):
    bot = DummyBot()
    cog = ChampionCog(bot)
    bot._cog = cog
    cog.data = ChampionData(str(tmp_path / "points.db"))

    await cog.data.add_delta("1", 5, "init")
    await cog.data.add_delta("2", 3, "init")

    called = []

    async def fake_apply(uid, score):
        called.append((uid, score))

    monkeypatch.setattr(cog, "_apply_champion_role", fake_apply)

    inter = DummyInteraction(bot)

    await syncroles.callback(inter)

    assert set(called) == {("1", 5), ("2", 3)}
    assert inter.followup.sent
    await cog.data.close()
