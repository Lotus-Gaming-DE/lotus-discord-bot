import pytest

import lotus_bot.cogs.quiz.cog as quiz_cog_mod
import lotus_bot.cogs.quiz.message_tracker as msg_mod
import lotus_bot.log_setup as log_setup
from lotus_bot.cogs.quiz.quiz_config import QuizAreaConfig


class DummyState:
    async def set_schedule(self, *args):
        pass

    def get_schedule(self, area):
        return None


@pytest.mark.asyncio
async def test_cog_unload_removes_attribute(monkeypatch, patch_logged_task, bot):
    patch_logged_task(log_setup, msg_mod)

    async def dummy_restore(self):
        return None

    async def dummy_init(self):
        return None

    async def dummy_run(self):
        return None

    monkeypatch.setattr(quiz_cog_mod.QuestionRestorer, "restore_all", dummy_restore)
    monkeypatch.setattr(quiz_cog_mod.MessageTracker, "initialize", dummy_init)
    monkeypatch.setattr(quiz_cog_mod.QuizScheduler, "run", dummy_run)

    bot.quiz_data = {
        "area": QuizAreaConfig(channel_id=1, active=False, question_state=DummyState())
    }
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}

    cog = quiz_cog_mod.QuizCog(bot)
    assert hasattr(bot, "quiz_cog")

    cog.cog_unload()
    await cog.wait_closed()

    assert not hasattr(bot, "quiz_cog")
