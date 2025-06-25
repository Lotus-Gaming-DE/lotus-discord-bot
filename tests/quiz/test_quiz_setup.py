import pytest


from lotus_bot.cogs import quiz
from lotus_bot.cogs.quiz.slash_commands import quiz_group
import lotus_bot.cogs.quiz.message_tracker as msg_mod
import lotus_bot.log_setup as log_setup


@pytest.mark.asyncio
async def test_quiz_setup_registers_cog_and_commands(
    monkeypatch, patch_logged_task, bot
):
    patch_logged_task(log_setup, msg_mod)
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {}

    async def fake_sync(*, guild=None):
        pass

    monkeypatch.setattr(bot.tree, "sync", fake_sync)

    await quiz.setup(bot)

    assert bot.get_cog("QuizCog") is not None
    registered = [cmd.name for cmd in bot.tree.get_commands(guild=bot.main_guild)]
    assert quiz_group.name in registered
