import pytest


from cogs import quiz, champion, wcr, ptcgp
from cogs.quiz.slash_commands import quiz_group
from cogs.champion.slash_commands import champion_group, syncroles
from cogs.wcr.slash_commands import wcr_group
from cogs.ptcgp.slash_commands import ptcgp_group
import cogs.quiz.message_tracker as msg_mod
import log_setup
from cogs.wcr.utils import load_wcr_data


@pytest.mark.asyncio
async def test_quiz_setup_uses_main_guild(monkeypatch, patch_logged_task, bot):
    patch_logged_task(log_setup, msg_mod)
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {}

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    await quiz.setup(bot)

    assert called == [(quiz_group, bot.main_guild)]


@pytest.mark.asyncio
async def test_champion_setup_uses_main_guild(monkeypatch, bot, patch_logged_task):
    bot.data = {"champion": {"roles": []}, "emojis": {}}
    patch_logged_task(log_setup)

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    await champion.setup(bot)

    assert called == [
        (champion_group, bot.main_guild),
        (syncroles, bot.main_guild),
    ]


@pytest.mark.asyncio
async def test_wcr_setup_uses_main_guild(monkeypatch, bot):
    async def fake_load():
        return {
            "units": [],
            "locals": {"en": {"units": []}},
            "categories": {},
            "stat_labels": {},
            "faction_combinations": {},
        }

    monkeypatch.setattr("cogs.wcr.utils.load_wcr_data", fake_load)
    monkeypatch.setattr("tests.general.test_cogs_setup.load_wcr_data", fake_load)
    bot.data = {"wcr": await load_wcr_data(), "emojis": {}}

    async def fake_register(bot_, cog_cls, group):
        called.append((group, bot_.main_guild))

    monkeypatch.setattr(wcr, "register_cog_and_group", fake_register)

    called = []
    await wcr.setup(bot)

    assert called == [(wcr_group, bot.main_guild)]


@pytest.mark.asyncio
async def test_ptcgp_setup_uses_main_guild(monkeypatch, bot):
    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    await ptcgp.setup(bot)

    assert called == [(ptcgp_group, bot.main_guild)]
