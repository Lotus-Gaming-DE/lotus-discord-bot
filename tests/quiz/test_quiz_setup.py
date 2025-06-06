import pytest


from cogs import quiz
from cogs.quiz.slash_commands import quiz_group
import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.message_tracker as msg_mod


@pytest.mark.asyncio
async def test_quiz_setup_registers_cog_and_commands(
    monkeypatch, patch_logged_task, bot
):
    patch_logged_task(quiz_cog_mod, msg_mod)
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {}

    await quiz.setup(bot)

    assert bot.get_cog("QuizCog") is not None
    registered = [cmd.name for cmd in bot.tree.get_commands(guild=bot.main_guild)]
    assert quiz_group.name in registered
