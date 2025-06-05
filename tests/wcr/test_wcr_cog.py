import json
import pytest
import discord

from cogs.wcr.cog import WCRCog
from cogs.wcr.views import MiniSelectView


class DummyBot:
    def __init__(self):
        self.data = {
            "emojis": {},
            "wcr": {
                "units": json.load(open("data/wcr/units.json", "r", encoding="utf-8")),
                "locals": {
                    "de": json.load(open("data/wcr/locals/de.json", "r", encoding="utf-8")),
                    "en": json.load(open("data/wcr/locals/en.json", "r", encoding="utf-8")),
                },
                "pictures": json.load(open("data/wcr/pictures.json", "r", encoding="utf-8")),
            },
        }


class DummyResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, content, view=None, ephemeral=False):
        self.messages.append({"content": content, "view": view, "ephemeral": ephemeral})

    async def defer(self, ephemeral=False):
        self.deferred = ephemeral


class DummyFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kwargs):
        self.sent.append({"content": content, **kwargs})


class DummyInteraction:
    def __init__(self):
        self.user = "tester"
        self.response = DummyResponse()
        self.followup = DummyFollowup()


@pytest.mark.asyncio
async def test_cmd_filter_no_emojis():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de")

    assert inter.response.messages
    msg = inter.response.messages[0]
    assert isinstance(msg["view"], MiniSelectView)
    assert msg["ephemeral"] is True


@pytest.mark.asyncio
async def test_cmd_filter_generates_options():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de")

    msg = inter.response.messages[0]
    view = msg["view"]
    options = view.children[0].options

    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    names = {
        u["id"]: n["name"]
        for n in bot.data["wcr"]["locals"]["de"]["units"]
        for u in units
        if u["id"] == n["id"]
    }
    expected = [names[u["id"]] for u in units if u["cost"] == 6]

    assert [o.label for o in options] == expected


@pytest.mark.asyncio
async def test_cmd_name_creates_embed():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_name(inter, "Abscheulichkeit", lang="de")

    assert inter.followup.sent
    msg = inter.followup.sent[0]
    embed = msg.get("embed")

    assert isinstance(embed, discord.Embed)
    assert msg["ephemeral"] is True
    assert embed.title.strip() == "Abscheulichkeit"
    assert embed.thumbnail.url.endswith("Statue_Abomination_Pose.webp")
    assert embed.fields[0].name.strip() == "Cost"
    assert embed.fields[0].value == "6"
