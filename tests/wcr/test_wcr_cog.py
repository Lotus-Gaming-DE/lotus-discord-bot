import json
import logging
import pytest
import discord

from lotus_bot.cogs.wcr.cog import WCRCog
from lotus_bot.cogs.wcr import embed_builder
from lotus_bot.cogs.wcr.views import MiniSelectView
from lotus_bot.cogs.wcr.duel import DuelCalculator


class DummyBot:
    def __init__(self, wcr_data):
        self.data = {"emojis": {}, "wcr": wcr_data}


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
async def test_cmd_filter_no_emojis(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de")

    assert inter.response.messages
    msg = inter.response.messages[0]
    view: MiniSelectView = msg["view"]
    assert isinstance(view, MiniSelectView)
    assert msg["ephemeral"] is True
    view.stop()
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_filter_generates_options(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de")

    msg = inter.response.messages[0]
    view: MiniSelectView = msg["view"]
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
    view.stop()
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_filter_cross_faction(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, faction="Horde", lang="de")

    options = inter.response.messages[0]["view"].children[0].options
    labels = [o.label for o in options]
    assert any("Sylvanas" in label for label in labels)
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_name_creates_embed(wcr_data):
    bot = DummyBot(wcr_data)
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
    assert embed.fields[0].name.strip() == "Kosten"
    assert embed.fields[0].value == "6"
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_name_respects_lang(wcr_data, monkeypatch):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_name(inter, "Abscheulichkeit", lang="en")

    embed = inter.followup.sent[0]["embed"]
    assert embed.title.strip() == "Abomination"
    cog.cog_unload()


def test_name_map_contains_unit(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    assert cog.unit_name_map["de"]["abscheulichkeit"] == "1"
    cog.cog_unload()


def test_build_mini_embed_uses_emoji(wcr_data):
    bot = DummyBot(wcr_data)
    bot.data["emojis"] = {"wcr_undead": "<:wcr_undead:id>"}
    cog = WCRCog(bot)
    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    unit = next(u for u in units if u["id"] == "1")
    embed, _ = embed_builder.build_mini_embed(
        unit["id"],
        unit,
        "de",
        cog.emojis,
        cog.languages,
        cog.lang_category_lookup,
        cog.stat_labels,
        cog.faction_combinations,
    )
    assert isinstance(embed, discord.Embed)
    cog.cog_unload()


def test_build_mini_embed_combines_factions(wcr_data):
    bot = DummyBot(wcr_data)
    bot.data["emojis"] = {"wcr_undead_horde": "<:wcr_undead_horde:id>"}
    cog = WCRCog(bot)
    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    unit = next(u for u in units if u["id"] == "62")
    embed, _ = embed_builder.build_mini_embed(
        unit["id"],
        unit,
        "de",
        cog.emojis,
        cog.languages,
        cog.lang_category_lookup,
        cog.stat_labels,
        cog.faction_combinations,
    )
    assert embed.title.startswith("<:wcr_undead_horde:id>")
    cog.cog_unload()


def test_build_mini_embed_fallback_to_en(wcr_data):
    wcr_data["stat_labels"].pop("de")
    wcr_data["locals"].pop("de")
    for items in wcr_data["categories"].values():
        for item in items:
            item["names"].pop("de", None)

    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    unit = next(u for u in units if u["id"] == "1")
    embed, _ = embed_builder.build_mini_embed(
        unit["id"],
        unit,
        "de",
        cog.emojis,
        cog.languages,
        cog.lang_category_lookup,
        cog.stat_labels,
        cog.faction_combinations,
    )
    assert "Abomination" in embed.title
    assert any("Cost" in f.name for f in embed.fields)
    cog.cog_unload()


def test_category_lookups_created(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    assert "factions" in cog.lang_category_lookup["de"]
    assert "category_lookup" not in bot.data["wcr"]["locals"]["de"]
    cog.cog_unload()


def test_token_index_contains_token(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    assert "62" in cog.name_token_index["de"]["sylvanas"]
    cog.cog_unload()


def test_resolve_unit_cross_language(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    result = cog.resolve_unit("Abomination", "de")
    assert result is not None
    unit_id, _, lang = result
    assert unit_id == "1"
    assert lang == "en"
    cog.cog_unload()


def test_resolve_unit_fuzzy_partial(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    result = cog.resolve_unit("sylvanas", "de")
    assert result is not None
    unit_id, _, lang = result
    assert unit_id == "62"
    assert lang == "de"
    cog.cog_unload()


def test_resolve_unit_cross_language_fuzzy(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    result = cog.resolve_unit("windrunner", "de")
    assert result is not None
    unit_id, _, lang = result
    assert unit_id == "62"
    assert lang == "en"
    cog.cog_unload()


@pytest.mark.asyncio
async def test_select_view_timeout_disables_select(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de")

    view = inter.response.messages[0]["view"]
    select = view.children[0]
    assert not select.disabled

    await view.on_timeout()

    assert select.disabled is True
    cog.cog_unload()


def test_init_without_en_language(wcr_data, caplog):
    bot = DummyBot(wcr_data)
    del bot.data["wcr"]["locals"]["en"]

    with caplog.at_level(logging.WARNING):
        cog = WCRCog(bot)

    assert cog.speed_choices
    events = [json.loads(r.getMessage()).get("event", "") for r in caplog.records]
    assert any("language not found" in e for e in events)
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cost_autocomplete_returns_all(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.cost_autocomplete(inter, "")

    expected = [str(c) for c in sorted({1, 2, 3, 4, 5, 6})]
    assert [c.name for c in choices] == expected
    assert [c.value for c in choices] == expected
    cog.cog_unload()


@pytest.mark.asyncio
async def test_speed_autocomplete_matches_substring(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.speed_autocomplete(inter, "fast")

    assert [c.name for c in choices] == ["Med-Fast", "Fast"]
    assert [c.value for c in choices] == ["2", "4"]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_faction_autocomplete_case_insensitive(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.faction_autocomplete(inter, "und")

    assert len(choices) == 1
    assert choices[0].name == "Undead"
    assert choices[0].value == "1"
    cog.cog_unload()


@pytest.mark.asyncio
async def test_type_autocomplete_multiple_results(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.type_autocomplete(inter, "e")

    assert [c.name for c in choices] == ["Spell", "Leader"]
    assert [c.value for c in choices] == ["2", "3"]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_trait_autocomplete_returns_sorted_matches(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.trait_autocomplete(inter, "ele")

    assert [c.name for c in choices] == ["Melee", "Elemental"]
    assert [c.value for c in choices] == ["3", "8"]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_unit_name_autocomplete_multilang(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    choices = await cog.unit_name_autocomplete(inter, "abo")

    names = {c.name for c in choices}
    assert "Abscheulichkeit [de]" in names
    assert "Abomination [en]" in names
    values = {
        c.value
        for c in choices
        if c.name in {"Abscheulichkeit [de]", "Abomination [en]"}
    }
    assert values == {"1"}
    cog.cog_unload()


def test_scaled_stats_leveling(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    calculator = DuelCalculator()

    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    unit = next(u for u in units if u["id"] == "26")

    stats_lvl1 = calculator.scaled_stats(unit, 1)
    stats_lvl2 = calculator.scaled_stats(unit, 2)
    stats_lvl5 = calculator.scaled_stats(unit, 5)

    assert stats_lvl1["health"] == 1300
    assert stats_lvl2["health"] == pytest.approx(1430)
    assert stats_lvl5["health"] == pytest.approx(1820)
    assert stats_lvl2["dps"] == pytest.approx(162, rel=0.01)
    assert stats_lvl5["dps"] == pytest.approx(206, rel=0.01)
    cog.cog_unload()


def test_duel_result_flying_vs_melee(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]
    calculator = DuelCalculator()
    unit_a = next(u for u in units if u["id"] == "26")
    unit_b = next(u for u in units if u["id"] == "27")

    result = calculator.duel_result(unit_a, 1, unit_b, 1)
    assert result[0] == "a"
    cog.cog_unload()


def test_compute_dps_spell_hits_flying(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]

    calculator = DuelCalculator()
    spell = next(u for u in units if u["id"] == "10")
    flying = next(u for u in units if u["id"] == "6")

    stats_spell = calculator.scaled_stats(spell, 1)
    dps = calculator.compute_dps(spell, stats_spell, flying)

    assert dps >= 0
    cog.cog_unload()


def test_duel_result_spell_vs_mini(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]

    calculator = DuelCalculator()
    spell = next(u for u in units if u["id"] == "10")
    mini = next(u for u in units if u["id"] == "6")

    result = calculator.duel_result(spell, 31, mini, 1)
    assert result == ("a", 0.0)
    cog.cog_unload()


def test_duel_result_equal_damage_spells(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]

    calculator = DuelCalculator()
    spell_a = next(u for u in units if u["id"] == "10")  # Chain Lightning
    spell_b = next(u for u in units if u["id"] == "36")  # Holy Nova

    result = calculator.duel_result(spell_a, 1, spell_b, 1)
    assert result is None
    cog.cog_unload()


def test_duel_result_identical_minis(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)

    units = bot.data["wcr"]["units"]
    if isinstance(units, dict) and "units" in units:
        units = units["units"]

    calculator = DuelCalculator()
    mini = next(u for u in units if u["id"] == "1")  # Abscheulichkeit

    result = calculator.duel_result(mini, 1, mini, 1)
    assert result is None
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_filter_public(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_filter(inter, cost="6", lang="de", public=True)

    msg = inter.response.messages[0]
    view: MiniSelectView = msg["view"]
    assert msg["ephemeral"] is False
    view.stop()
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_name_public(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_name(inter, "Abscheulichkeit", lang="de", public=True)

    msg = inter.followup.sent[0]
    assert msg["ephemeral"] is False
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_duel_public(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    inter = DummyInteraction()

    await cog.cmd_duel(
        inter,
        "Gargoyle",
        "General Drakkisath",
        1,
        1,
        lang="de",
        public=True,
    )

    msg = inter.followup.sent[0]
    assert msg["ephemeral"] is False
    assert "Gargoyle" in msg["content"]
    assert "General Drakkisath" in msg["content"]
    assert "DPS" in msg["content"]
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_duel_no_damage_message(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    outcome = cog._compute_duel_outcome("Banshee", "Bergbewohner", 1, 1, "de")
    assert outcome.text == "Keines der Minis kann den Gegner treffen."
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_duel_identical_minis_tie(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    outcome = cog._compute_duel_outcome(
        "Abscheulichkeit", "Abscheulichkeit", 1, 1, "de"
    )
    assert outcome.text == "Unentschieden oder kein Schaden."
    cog.cog_unload()


@pytest.mark.asyncio
async def test_cmd_duel_unknown_mini(wcr_data):
    bot = DummyBot(wcr_data)
    cog = WCRCog(bot)
    outcome = cog._compute_duel_outcome(
        "Unbekanntes Mini", "Abscheulichkeit", 1, 1, "de"
    )
    assert outcome.text == "Eines der Minis wurde nicht gefunden."
    cog.cog_unload()


def test_init_without_localization_fallback(wcr_data, caplog):
    wcr_data["locals"] = {}
    bot = DummyBot(wcr_data)
    with caplog.at_level(logging.WARNING):
        cog = WCRCog(bot)

    events = [json.loads(r.getMessage()).get("event", "") for r in caplog.records]
    assert "falling back" in events[0].lower()
    assert "en" in cog.languages
    cog.cog_unload()
