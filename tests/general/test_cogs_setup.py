import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from bot import MyBot
from cogs import quiz, champion, wcr
from cogs.quiz.slash_commands import quiz_group
from cogs.champion.slash_commands import champion_group
from cogs.wcr.slash_commands import wcr_group
import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.message_tracker as msg_mod
from cogs.wcr.utils import load_wcr_data


@pytest.mark.asyncio
async def test_quiz_setup_uses_main_guild(monkeypatch):
    def fake_task(coro, logger):
        coro.close()

    monkeypatch.setattr(quiz_cog_mod, "create_logged_task", fake_task)
    monkeypatch.setattr(msg_mod, "create_logged_task", fake_task)

    bot = MyBot()
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {}

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    await quiz.setup(bot)

    assert called == [(quiz_group, bot.main_guild)]


@pytest.mark.asyncio
async def test_champion_setup_uses_main_guild(monkeypatch):
    bot = MyBot()
    bot.data = {"champion": {"roles": []}, "emojis": {}}

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    await champion.setup(bot)

    assert called == [(champion_group, bot.main_guild)]


@pytest.mark.asyncio
async def test_wcr_setup_uses_main_guild(monkeypatch):
    bot = MyBot()
    bot.data = {"wcr": load_wcr_data(), "emojis": {}}

    called = []

    def fake_add(cmd, *, guild=None):
        called.append((cmd, guild))

    monkeypatch.setattr(bot.tree, "add_command", fake_add)

    await wcr.setup(bot)

    assert called == [(wcr_group, bot.main_guild)]
