import pytest

from lotus_bot.cogs.champion.slash_commands import myhistory


class DummyBot:
    def __init__(self):
        self._cog = None

    def get_cog(self, name):
        return self._cog if name == "ChampionCog" else None


class DummyCog:
    def __init__(self):
        self.data = type(
            "Data", (), {"get_history": self.get_history, "get_total": self.get_total}
        )()

    async def get_history(self, user_id, limit=10):
        return []

    async def get_total(self, user_id):
        return 0


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, msg, ephemeral=False):
        self.messages.append((msg, ephemeral))


class DummyMember:
    def __init__(self, uid):
        self.id = uid
        self.mention = f"<@{uid}>"
        self.display_name = f"User{uid}"


class DummyInteraction:
    def __init__(self, bot):
        self.client = bot
        self.user = DummyMember(999)
        self.response = DummyResponse()
        self.followup = DummyResponse()
        self.guild = None


@pytest.mark.asyncio
async def test_myhistory_empty_is_ephemeral():
    bot = DummyBot()
    cog = DummyCog()
    bot._cog = cog
    inter = DummyInteraction(bot)

    await myhistory.callback(inter)

    assert inter.response.messages
    _, ephemeral = inter.response.messages[0]
    assert ephemeral is True
