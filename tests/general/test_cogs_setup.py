import pytest


from cogs import quiz, champion, wcr, ptcgp
from cogs.quiz.slash_commands import quiz_group
from cogs.champion.slash_commands import champion_group, syncroles
from cogs.wcr.slash_commands import wcr_group
from cogs.ptcgp.slash_commands import ptcgp_group
import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.message_tracker as msg_mod
from cogs.wcr.utils import load_wcr_data


@pytest.mark.asyncio
async def test_quiz_setup_uses_main_guild(monkeypatch, patch_logged_task, bot):
    patch_logged_task(quiz_cog_mod, msg_mod)
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {}

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    await quiz.setup(bot)

    assert called == [(quiz_group, bot.main_guild)]


@pytest.mark.asyncio
async def test_champion_setup_uses_main_guild(monkeypatch, bot):
    bot.data = {"champion": {"roles": []}, "emojis": {}}

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
    bot.data = {"wcr": load_wcr_data(), "emojis": {}}

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

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
