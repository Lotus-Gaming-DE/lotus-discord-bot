import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.scheduler as scheduler_mod
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


def fake_task_general(coro, logger):
    coro.close()
    return DummyTask()


def fake_task_scheduler(coro, logger):
    coro.close()
    task = DummyTask()
    fake_task_scheduler.tasks.append(task)
    return task

fake_task_scheduler.tasks = []


class DummyState:
    pass


@pytest.mark.asyncio
async def test_scheduler_start_and_stop(monkeypatch, patch_logged_task, bot):
    patch_logged_task(quiz_cog_mod, msg_mod)
    monkeypatch.setattr(scheduler_mod, "create_logged_task", fake_task_scheduler)
    monkeypatch.setattr(quiz_cog_mod.QuestionRestorer, "restore_all", lambda self: None)

    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {
        "area1": QuizAreaConfig(channel_id=1, active=True, question_state=DummyState()),
        "area2": QuizAreaConfig(channel_id=2, active=False, question_state=DummyState()),
    }

    cog = quiz_cog_mod.QuizCog(bot)
    monkeypatch.setattr(bot, "get_cog", lambda name: cog if name == "QuizCog" else None)

    assert list(cog.schedulers.keys()) == ["area1"]
    assert len(fake_task_scheduler.tasks) == 1
    task = fake_task_scheduler.tasks[0]
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
    monkeypatch.setattr(scheduler_mod, "create_logged_task", fake_task_scheduler)
    monkeypatch.setattr(quiz_cog_mod.QuestionRestorer, "restore_all", lambda self: None)
    monkeypatch.setattr(slash_mod, "save_area_config", lambda b: None)

    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {
        "area1": QuizAreaConfig(channel_id=1, active=False, question_state=DummyState()),
    }

    cog = quiz_cog_mod.QuizCog(bot)
    monkeypatch.setattr(bot, "get_cog", lambda name: cog if name == "QuizCog" else None)

    assert not cog.schedulers

    inter = DummyInteraction(bot, DummyChannel(1))
    await slash_mod.enable.callback(inter, "area1")

    assert "area1" in cog.schedulers
    task = fake_task_scheduler.tasks[-1]
    assert not task.cancelled

    await slash_mod.disable.callback(inter)

    assert "area1" not in cog.schedulers
    assert task.cancelled
