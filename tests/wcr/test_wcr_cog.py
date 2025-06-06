import json
import logging
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
    cog.cog_unload()


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
    cog.cog_unload()


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
    cog.cog_unload()


def test_name_map_contains_unit():
    bot = DummyBot()
    cog = WCRCog(bot)
    assert cog.unit_name_map["de"]["abscheulichkeit"] == 1
    cog.cog_unload()


def test_resolve_unit_cross_language():
    bot = DummyBot()
    cog = WCRCog(bot)

    result = cog.resolve_unit("Abomination", "de")
    assert result is not None
    unit_id, _, lang, _ = result
    assert unit_id == 1
    assert lang == "en"
    cog.cog_unload()
@pytest.mark.asyncio
async def test_select_view_timeout_disables_select():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de")

    view = inter.response.messages[0]["view"]
    select = view.children[0]
    assert not select.disabled

    await view.on_timeout()

    assert select.disabled is True
    cog.cog_unload()


def test_init_without_en_language(caplog):
    bot = DummyBot()
    del bot.data["wcr"]["locals"]["en"]

    with caplog.at_level(logging.WARNING):
        cog = WCRCog(bot)

    assert cog.speed_choices
    assert any("language not found" in r.message for r in caplog.records)
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cost_autocomplete_returns_all():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.cost_autocomplete(inter, "")

    expected = [str(c) for c in sorted({1, 2, 3, 4, 5, 6})]
    assert [c.name for c in choices] == expected
    assert [c.value for c in choices] == expected
    cog.cog_unload()


@pytest.mark.asyncio
async def test_speed_autocomplete_matches_substring():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.speed_autocomplete(inter, "fast")

    assert [c.name for c in choices] == ["Med-Fast", "Fast"]
    assert [c.value for c in choices] == ["2", "4"]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_faction_autocomplete_case_insensitive():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.faction_autocomplete(inter, "und")

    assert len(choices) == 1
    assert choices[0].name == "Undead"
    assert choices[0].value == "1"
    cog.cog_unload()


@pytest.mark.asyncio
async def test_type_autocomplete_multiple_results():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.type_autocomplete(inter, "e")

    assert [c.name for c in choices] == ["Spell", "Leader"]
    assert [c.value for c in choices] == ["2", "3"]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_trait_autocomplete_returns_sorted_matches():
    bot = DummyBot()
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.trait_autocomplete(inter, "ele")

    assert [c.name for c in choices] == ["Melee", "Elemental"]
    assert [c.value for c in choices] == ["3", "8"]
    cog.cog_unload()
