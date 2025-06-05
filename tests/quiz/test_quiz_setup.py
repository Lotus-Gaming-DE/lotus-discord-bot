import os
import sys
import pytest


from bot import MyBot
from cogs import quiz
from cogs.quiz.slash_commands import quiz_group
import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.message_tracker as msg_mod


@pytest.mark.asyncio
async def test_quiz_setup_registers_cog_and_commands(monkeypatch):
    def fake_task(coro, logger):
        coro.close()

    monkeypatch.setattr(quiz_cog_mod, "create_logged_task", fake_task)
    monkeypatch.setattr(msg_mod, "create_logged_task", fake_task)

    bot = MyBot()
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {}

    await quiz.setup(bot)

    assert bot.get_cog("QuizCog") is not None
    registered = [cmd.name for cmd in bot.tree.get_commands(guild=bot.main_guild)]
    assert quiz_group.name in registered
