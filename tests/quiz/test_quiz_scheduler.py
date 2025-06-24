import lotusbot.cogs.quiz.cog as quiz_cog_mod
import lotusbot.cogs.quiz.message_tracker as msg_mod
import lotusbot.cogs.quiz.slash_commands as slash_mod
from lotusbot.cogs.quiz.quiz_config import QuizAreaConfig
import pytest
from lotusbot import log_setup


class DummyBot:
    def __init__(self):
        self.data = {}
        self.quiz_data = {}


bot = DummyBot()


class DummyState:
    def get_schedule(self, area):
        return None


@pytest.mark.asyncio
async def test_scheduler_start_and_stop(monkeypatch, patch_logged_task, bot):
    patch_logged_task(log_setup, msg_mod)

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
    assert len(cog.tasks) == 3  # tracker, restorer, scheduler
    task = cog.schedulers["area1"].task
    assert not task.cancelled

    cog.cog_unload()
    await cog.wait_closed()
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
    patch_logged_task(log_setup, msg_mod)

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
    cog.cog_unload()
    await cog.wait_closed()
