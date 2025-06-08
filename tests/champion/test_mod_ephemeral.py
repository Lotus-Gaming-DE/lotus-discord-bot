import pytest

from cogs.champion.slash_commands import give, history, score


class DummyBot:
    def __init__(self):
        self._cog = None

    def get_cog(self, name):
        return self._cog if name == "ChampionCog" else None


class DummyCog:
    def __init__(self):
        self.updated = []
        self.data = type(
            "Data",
            (),
            {"get_history": self.get_history, "get_total": self.get_total},
        )()

    async def update_user_score(self, user_id, delta, reason):
        self.updated.append((user_id, delta, reason))
        return 5

    async def get_history(self, user_id, limit=10):
        return []

    async def get_total(self, user_id):
        return 0


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, msg, ephemeral=False):
        self.messages.append((msg, ephemeral))


class DummyInteraction:
    def __init__(self, bot):
        self.client = bot
        self.user = DummyMember(999)
        self.response = DummyResponse()
        self.followup = DummyResponse()
        self.guild = None


class DummyMember:
    def __init__(self, uid):
        self.id = uid
        self.mention = f"<@{uid}>"
        self.display_name = f"User{uid}"


@pytest.mark.asyncio
async def test_give_sends_ephemeral_message():
    bot = DummyBot()
    cog = DummyCog()
    bot._cog = cog
    inter = DummyInteraction(bot)
    target = DummyMember(1)

    await give.callback(inter, target, 3, "reason")

    assert cog.updated == [(1, 3, "reason")]
    assert inter.response.messages
    _, ephemeral = inter.response.messages[0]
    assert ephemeral is True


@pytest.mark.asyncio
async def test_history_empty_is_ephemeral():
    bot = DummyBot()
    cog = DummyCog()
    bot._cog = cog
    inter = DummyInteraction(bot)
    target = DummyMember(2)

    await history.callback(inter, target)

    assert inter.response.messages
    _, ephemeral = inter.response.messages[0]
    assert ephemeral is True


@pytest.mark.asyncio
async def test_score_is_ephemeral():
    bot = DummyBot()
    cog = DummyCog()
    bot._cog = cog
    inter = DummyInteraction(bot)

    await score.callback(inter, None)

    assert inter.response.messages
    _, ephemeral = inter.response.messages[0]
    assert ephemeral is True
