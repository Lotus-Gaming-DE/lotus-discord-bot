import datetime
import asyncio
import pytest

import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.scheduler as scheduler_mod
import cogs.quiz.message_tracker as msg_mod
from cogs.quiz.quiz_config import QuizAreaConfig
from cogs.quiz.question_state import QuestionStateManager
import log_setup


class DummyBot:
    def __init__(self):
        self.data = {}
        self.quiz_data = {}
        self.main_guild = 0


@pytest.mark.asyncio
async def test_scheduler_resume(monkeypatch, patch_logged_task, tmp_path):
    patch_logged_task(log_setup, msg_mod)

    async def dummy_restore(self):
        return None

    monkeypatch.setattr(quiz_cog_mod.QuestionRestorer, "restore_all", dummy_restore)

    async def dummy_prepare(self, area, end):
        raise asyncio.CancelledError()

    monkeypatch.setattr(quiz_cog_mod.QuestionManager, "prepare_question", dummy_prepare)

    state_file = tmp_path / "state.json"
    manager = QuestionStateManager(str(state_file))

    bot = DummyBot()
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {
        "area1": QuizAreaConfig(
            channel_id=1,
            active=True,
            time_window=datetime.timedelta(seconds=10),
            question_state=manager,
        )
    }

    cog = quiz_cog_mod.QuizCog(bot)
    monkeypatch.setattr(
        bot, "get_cog", lambda name: cog if name == "QuizCog" else None, raising=False
    )

    async def instant_sleep(delay):
        return

    async def dummy_prepare(area, end):
        raise asyncio.CancelledError()

    monkeypatch.setattr(scheduler_mod.asyncio, "sleep", instant_sleep)
    monkeypatch.setattr(scheduler_mod.random, "uniform", lambda a, b: 0)

    async def wait_ready():
        return

    monkeypatch.setattr(bot, "wait_until_ready", wait_ready, raising=False)
    monkeypatch.setattr(cog.closer, "close_question", lambda *a, **k: None)

    scheduler = cog.schedulers["area1"]
    with pytest.raises(asyncio.CancelledError):
        await scheduler.run()

    saved = manager.get_schedule("area1")
    assert saved is not None
    post_time, window_end = saved

    # simulate restart
    patch_logged_task(log_setup, msg_mod)

    async def dummy_restore2(self):
        return None

    monkeypatch.setattr(quiz_cog_mod.QuestionRestorer, "restore_all", dummy_restore2)

    bot2 = DummyBot()
    bot2.data = bot.data
    bot2.quiz_data = {
        "area1": QuizAreaConfig(
            channel_id=1,
            active=True,
            question_state=manager,
        )
    }

    cog2 = quiz_cog_mod.QuizCog(bot2)
    sched = cog2.schedulers["area1"]
    assert sched.post_time == post_time
    assert sched.window_end == window_end
