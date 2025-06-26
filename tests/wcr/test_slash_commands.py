import pytest
import discord

from lotus_bot.cogs.wcr.slash_commands import (
    filter as cmd_filter,
    name as cmd_name,
    duell as cmd_duell,
    debug as cmd_debug,
)


class DummyCog:
    def __init__(self):
        self.calls = []

    async def cmd_filter(self, *args):
        self.calls.append(("filter", args))

    async def cmd_name(self, *args):
        self.calls.append(("name", args))

    async def cmd_duel(self, *args):
        self.calls.append(("duel", args))

    async def cmd_debug(self, *args):
        self.calls.append(("debug", args))


class DummyBot:
    def __init__(self, cog):
        self._cog = cog

    def get_cog(self, name):
        return self._cog if name == "WCRCog" else None


class DummyInteraction:
    def __init__(self, bot):
        self.client = bot
        self.user = discord.Object(id=1)
        self.response = type("Resp", (), {"defer": lambda self, **k: None})()
        self.followup = type("F", (), {"send": lambda self, **k: None})()


@pytest.mark.asyncio()
async def test_filter_calls_cog():
    cog = DummyCog()
    bot = DummyBot(cog)
    inter = DummyInteraction(bot)
    await cmd_filter.callback(inter, cost="5")
    assert cog.calls[0][0] == "filter"


@pytest.mark.asyncio()
async def test_name_calls_cog():
    cog = DummyCog()
    bot = DummyBot(cog)
    inter = DummyInteraction(bot)
    await cmd_name.callback(inter, "foo")
    assert cog.calls[0][0] == "name"


@pytest.mark.asyncio()
async def test_duel_calls_cog():
    cog = DummyCog()
    bot = DummyBot(cog)
    inter = DummyInteraction(bot)
    await cmd_duell.callback(inter, "a", "b")
    assert cog.calls[0][0] == "duel"


@pytest.mark.asyncio()
async def test_debug_calls_cog():
    cog = DummyCog()
    bot = DummyBot(cog)
    inter = DummyInteraction(bot)
    await cmd_debug.callback(inter)
    assert cog.calls[0][0] == "debug"
