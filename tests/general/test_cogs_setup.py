import pytest


from lotus_bot.cogs import quiz, champion, wcr, ptcgp
from lotus_bot.cogs.quiz.slash_commands import quiz_group
from lotus_bot.cogs.champion.slash_commands import champion_group, syncroles
from lotus_bot.cogs.wcr.slash_commands import wcr_group
from lotus_bot.cogs.ptcgp.slash_commands import ptcgp_group
import lotus_bot.cogs.quiz.message_tracker as msg_mod
import lotus_bot.log_setup as log_setup
from lotus_bot.cogs.wcr.utils import load_wcr_data


@pytest.mark.asyncio
async def test_quiz_setup_uses_main_guild(monkeypatch, patch_logged_task, bot):
    patch_logged_task(log_setup, msg_mod)
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {}

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    async def fake_sync(*, guild=None):
        pass

    monkeypatch.setattr(bot.tree, "sync", fake_sync)

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

    async def fake_sync(*, guild=None):
        pass

    monkeypatch.setattr(bot.tree, "sync", fake_sync)

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

    monkeypatch.setattr("lotus_bot.cogs.wcr.utils.load_wcr_data", fake_load)
    monkeypatch.setattr("tests.general.test_cogs_setup.load_wcr_data", fake_load)
    bot.data = {"wcr": await load_wcr_data(), "emojis": {}}

    async def fake_register(bot_, cog_cls, group):
        called.append((group, bot_.main_guild))

    monkeypatch.setattr(wcr, "register_cog_and_group", fake_register)

    async def fake_sync(*, guild=None):
        pass

    monkeypatch.setattr(bot.tree, "sync", fake_sync)

    called = []
    await wcr.setup(bot)

    assert called == [(wcr_group, bot.main_guild)]


@pytest.mark.asyncio
async def test_ptcgp_setup_uses_main_guild(monkeypatch, bot):
    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    async def fake_sync(*, guild=None):
        pass

    monkeypatch.setattr(bot.tree, "sync", fake_sync)

    await ptcgp.setup(bot)

    assert called == [(ptcgp_group, bot.main_guild)]


@pytest.mark.asyncio
async def test_wcr_setup_raises_on_error(monkeypatch, bot):
    async def fake_register(*args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(wcr, "register_cog_and_group", fake_register)

    with pytest.raises(RuntimeError):
        await wcr.setup(bot)
