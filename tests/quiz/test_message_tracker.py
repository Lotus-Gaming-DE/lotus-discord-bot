

from cogs.quiz.message_tracker import MessageTracker
import cogs.quiz.message_tracker as msg_mod
import pytest
from cogs.quiz.quiz_config import QuizAreaConfig


class DummyAuthor:
    def __init__(self, is_bot=False, uid=0):
        self.bot = is_bot
        self.id = uid


class DummyChannel:
    def __init__(self, cid):
        self.id = cid


class DummyMessage:
    def __init__(self, cid, is_bot=False, embed_title=None, uid=0):
        self.author = DummyAuthor(is_bot, uid)
        self.channel = DummyChannel(cid)
        self.embeds = [type("Embed", (), {"title": embed_title})()] if embed_title else []


class DummyManager:
    def __init__(self):
        self.scheduled = []

    async def ask_question(self, area, end_time):
        self.scheduled.append((area, end_time))


class DummyCog:
    def __init__(self):
        self.manager = DummyManager()
        self.awaiting_activity = {}


class DummyBot:
    def __init__(self):
        self.quiz_cog = DummyCog()
        self.quiz_data = {"area1": QuizAreaConfig(channel_id=123, activity_threshold=3)}


def test_register_message_increments_and_triggers(monkeypatch, patch_logged_task):
    bot = DummyBot()
    tracker = MessageTracker(bot, bot.quiz_cog.manager.ask_question)
    bot.quiz_cog.awaiting_activity = {123: ("area1", "end")}

    triggered = []

    base_task = patch_logged_task(msg_mod)

    def wrapper(coro, logger):
        triggered.append(coro)
        base_task(coro, logger)

    monkeypatch.setattr(msg_mod, "create_logged_task", wrapper, raising=False)

    msg = DummyMessage(123)
    tracker.register_message(msg)
    assert tracker.get(123) == 1
    tracker.register_message(msg)
    assert tracker.get(123) == 2
    assert len(triggered) == 0
    tracker.register_message(msg)
    assert tracker.get(123) == 3
    assert len(triggered) == 1


@pytest.mark.asyncio
async def test_initialize_counts_history(monkeypatch):
    quiz_embed_title = "Quiz f\u00fcr AREA1"

    msgs = [
        DummyMessage(123, uid=1),
        DummyMessage(123, is_bot=True, uid=2),
        DummyMessage(123, is_bot=True, embed_title=quiz_embed_title, uid=999),
    ]

    class DummyChannel:
        def __init__(self, cid, messages):
            self.id = cid
            self._msgs = messages

        def history(self, limit=20):
            async def gen():
                for m in self._msgs:
                    yield m

            return gen()

    class DummyBot:
        def __init__(self):
            self.quiz_data = {"area1": QuizAreaConfig(channel_id=123, activity_threshold=3)}
            self.user = type("User", (), {"id": 999})()

        async def wait_until_ready(self):
            pass

        async def fetch_channel(self, cid):
            return DummyChannel(cid, msgs)

    monkeypatch.setattr(msg_mod.discord, "TextChannel", DummyChannel)

    bot = DummyBot()
    tracker = MessageTracker(bot, None)

    await tracker.initialize()

    assert tracker.get(123) == 1
    assert tracker.is_initialized(123)


@pytest.mark.asyncio
async def test_initialize_uses_threshold_when_no_quiz(monkeypatch):
    msgs: list[DummyMessage] = [DummyMessage(123, uid=1), DummyMessage(123, uid=2)]

    class DummyChannel:
        def __init__(self, cid, messages):
            self.id = cid
            self._msgs = messages

        def history(self, limit=20):
            async def gen():
                for m in self._msgs:
                    yield m

            return gen()

    class DummyBot:
        def __init__(self):
            self.quiz_data = {"area1": QuizAreaConfig(channel_id=123, activity_threshold=3)}
            self.user = type("User", (), {"id": 999})()

        async def wait_until_ready(self):
            pass

        async def fetch_channel(self, cid):
            return DummyChannel(cid, msgs)

    monkeypatch.setattr(msg_mod.discord, "TextChannel", DummyChannel)

    bot = DummyBot()
    tracker = MessageTracker(bot, None)

    await tracker.initialize()

    assert tracker.get(123) == 3
    assert tracker.is_initialized(123)
