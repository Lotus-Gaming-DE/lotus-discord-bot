import datetime
import pytest
import discord

from cogs.quiz.question_manager import QuestionManager
from cogs.quiz.quiz_config import QuizAreaConfig


class DummyGenerator:
    def __init__(self, question=None, use_default=True):
        if question is None and use_default:
            self.question = {"frage": "f", "antwort": "a", "category": "c"}
        else:
            self.question = question

    async def generate(self, area, language="de"):
        return self.question


class DummyChannel:
    def __init__(self):
        self.id = 1
        self.sent = []

    async def send(self, *, embed=None, view=None):
        self.sent.append((embed, view))
        msg = discord.Object(id=42)
        return msg


class DummyTracker:
    def __init__(self):
        self.reset_called = False

    def reset(self, cid):
        self.reset_called = True


class DummyState:
    def __init__(self):
        self.recorded = []

    async def set_active_question(self, area, qinfo):
        self.recorded.append((area, qinfo))


class DummyCloser:
    async def auto_close(self, area, delay):
        pass


class DummyCog:
    def __init__(self, bot):
        self.bot = bot
        self.tracker = DummyTracker()
        self.state = DummyState()
        self.closer = DummyCloser()
        self.current_questions = {}
        self.answered_users = {"area": set()}
        self.awaiting_activity = {}

        def _track_task(coro):
            coro.close()

        self._track_task = _track_task


class DummyBot:
    def __init__(self, channel, generator):
        self.quiz_data = {
            "area": QuizAreaConfig(
                channel_id=channel.id, question_generator=generator, language="de"
            )
        }
        self.main_guild = 0
        self.main_guild_id = 0
        self.data = {}
        self._channel = channel

    def get_channel(self, cid):
        return self._channel


@pytest.mark.asyncio
async def test_ask_question_posts_and_tracks(monkeypatch):
    channel = DummyChannel()
    generator = DummyGenerator()
    bot = DummyBot(channel, generator)
    cog = DummyCog(bot)
    manager = QuestionManager(cog)

    end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
    await manager.ask_question("area", end_time)

    assert cog.current_questions["area"].message_id == 42
    assert cog.tracker.reset_called
    assert cog.state.recorded
    assert channel.sent


@pytest.mark.asyncio
async def test_ask_question_no_question():
    channel = DummyChannel()
    generator = DummyGenerator(question=None, use_default=False)
    bot = DummyBot(channel, generator)
    cog = DummyCog(bot)
    manager = QuestionManager(cog)

    end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)
    await manager.ask_question("area", end_time)

    assert "area" not in cog.current_questions
    assert not channel.sent
