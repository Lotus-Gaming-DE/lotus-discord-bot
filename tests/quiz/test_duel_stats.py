import pytest

from cogs.quiz.duel_stats import DuelStats
from cogs.quiz.slash_commands import duelstats


class DummyUser:
    def __init__(self, uid):
        self.id = uid
        self.display_name = f"user{uid}"


class DummyResponse:
    def __init__(self):
        self.deferred = None

    async def defer(self, thinking=False, ephemeral=False):
        self.deferred = {"thinking": thinking, "ephemeral": ephemeral}


class DummyFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})


class DummyGuild:
    def __init__(self, members):
        self.members = {m.id: m for m in members}

    def get_member(self, uid):
        return self.members.get(uid)

    async def fetch_member(self, uid):
        return self.members.get(uid)


class DummyBot:
    def __init__(self, stats):
        self._cog = type("Cog", (), {"duel_stats": stats})()

    def get_cog(self, name):
        return self._cog if name == "QuizCog" else None


class DummyInteraction:
    def __init__(self, bot, guild, user):
        self.client = bot
        self.guild = guild
        self.user = user
        self.response = DummyResponse()
        self.followup = DummyFollowup()


@pytest.mark.asyncio
async def test_duel_stats_update(tmp_path):
    db = DuelStats(str(tmp_path / "duel.db"))
    await db.record_result(1, 2)
    await db.record_result(1, 3)
    await db.record_result(2, 1)

    wins1, losses1 = await db.get_stats(1)
    wins2, losses2 = await db.get_stats(2)

    assert (wins1, losses1) == (2, 1)
    assert (wins2, losses2) == (1, 1)
    await db.close()


@pytest.mark.asyncio
async def test_duelstats_command_personal(tmp_path):
    db = DuelStats(str(tmp_path / "duel.db"))
    await db.record_result(1, 2)
    bot = DummyBot(db)
    guild = DummyGuild([DummyUser(1), DummyUser(2)])
    inter = DummyInteraction(bot, guild, DummyUser(1))

    await duelstats.callback(inter, None)

    assert inter.response.deferred == {"thinking": False, "ephemeral": True}
    msg = inter.followup.sent[0]
    assert msg["ephemeral"] is True
    assert "1 Siege" in msg["content"]


@pytest.mark.asyncio
async def test_duelstats_command_leaderboard(tmp_path):
    db = DuelStats(str(tmp_path / "duel.db"))
    await db.record_result(1, 2)
    await db.record_result(1, 3)
    await db.record_result(2, 3)
    bot = DummyBot(db)
    guild = DummyGuild([DummyUser(1), DummyUser(2), DummyUser(3)])
    inter = DummyInteraction(bot, guild, DummyUser(2))

    await duelstats.callback(inter, 2)

    assert inter.response.deferred == {"thinking": True, "ephemeral": False}
    msg = inter.followup.sent[0]["content"]
    assert "Rang" in msg and "user1" in msg
