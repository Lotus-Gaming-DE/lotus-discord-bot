import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.message_tracker as msg_mod
import cogs.quiz.slash_commands as slash_mod
from cogs.quiz.quiz_config import QuizAreaConfig
import pytest


class DummyBot:
    def __init__(self):
        self.data = {}
        self.quiz_data = {}


bot = DummyBot()


class DummyTask:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class DummyTaskGroup:
    def __init__(self):
        self.tasks = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, et, exc, tb):
        return False

    def create_task(self, coro):
        coro.close()
        self.tasks.append(DummyTask())
        return self.tasks[-1]

    def _abort(self):
        for t in self.tasks:
            t.cancel()


class DummyState:
    def get_schedule(self, area):
        return None


@pytest.mark.asyncio
async def test_scheduler_start_and_stop(monkeypatch, patch_logged_task, bot):
    patch_logged_task(quiz_cog_mod, msg_mod)
    monkeypatch.setattr(quiz_cog_mod.asyncio, "TaskGroup", DummyTaskGroup)

    async def dummy_restore(self):
        return None

    monkeypatch.setattr(
        quiz_cog_mod.QuestionRestorer,
        "restore_all",
        dummy_restore,
    )

    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {
        "area1": QuizAreaConfig(channel_id=1, active=True, question_state=DummyState()),
        "area2": QuizAreaConfig(
            channel_id=2, active=False, question_state=DummyState()
        ),
    }

    cog = quiz_cog_mod.QuizCog(bot)
    monkeypatch.setattr(bot, "get_cog", lambda name: cog if name == "QuizCog" else None)

    assert list(cog.schedulers.keys()) == ["area1"]
    assert len(cog.task_group.tasks) == 3  # tracker, restorer, scheduler
    task = cog.schedulers["area1"].task
    assert not task.cancelled

    cog.cog_unload()
    assert task.cancelled


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content, **kwargs):
        self.messages.append(content)


class DummyChannel:
    def __init__(self, cid):
        self.id = cid


class DummyInteraction:
    def __init__(self, bot, channel):
        self.client = bot
        self.channel = channel
        self.response = DummyResponse()


@pytest.mark.asyncio
async def test_enable_starts_and_disable_stops(monkeypatch, patch_logged_task, bot):
    patch_logged_task(quiz_cog_mod, msg_mod)
    monkeypatch.setattr(quiz_cog_mod.asyncio, "TaskGroup", DummyTaskGroup)

    async def dummy_restore(self):
        return None

    monkeypatch.setattr(quiz_cog_mod.QuestionRestorer, "restore_all", dummy_restore)
    monkeypatch.setattr(slash_mod, "save_area_config", lambda b: None)

    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {
        "area1": QuizAreaConfig(
            channel_id=1, active=False, question_state=DummyState()
        ),
    }

    cog = quiz_cog_mod.QuizCog(bot)
    monkeypatch.setattr(bot, "get_cog", lambda name: cog if name == "QuizCog" else None)

    assert not cog.schedulers

    inter = DummyInteraction(bot, DummyChannel(1))
    await slash_mod.enable.callback(inter, "area1")

    assert "area1" in cog.schedulers
    task = cog.schedulers["area1"].task
    assert not task.cancelled

    await slash_mod.disable.callback(inter)

    assert "area1" not in cog.schedulers
    assert task.cancelled
