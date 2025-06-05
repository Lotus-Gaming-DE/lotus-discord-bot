import os
import sys


from cogs.quiz.message_tracker import MessageTracker
from cogs.quiz.quiz_config import QuizAreaConfig


class DummyAuthor:
    def __init__(self, is_bot=False):
        self.bot = is_bot


class DummyChannel:
    def __init__(self, cid):
        self.id = cid


class DummyMessage:
    def __init__(self, cid, is_bot=False):
        self.author = DummyAuthor(is_bot)
        self.channel = DummyChannel(cid)


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


def test_register_message_increments_and_triggers(monkeypatch):
    bot = DummyBot()
    tracker = MessageTracker(bot, bot.quiz_cog.manager.ask_question)
    bot.quiz_cog.awaiting_activity = {123: ("area1", "end")}

    triggered = []

    def fake_task(coro, logger):
        triggered.append(coro)
        coro.close()

    monkeypatch.setattr("cogs.quiz.message_tracker.create_logged_task", fake_task)

    msg = DummyMessage(123)
    tracker.register_message(msg)
    assert tracker.get(123) == 1
    tracker.register_message(msg)
    assert tracker.get(123) == 2
    assert len(triggered) == 0
    tracker.register_message(msg)
    assert tracker.get(123) == 3
    assert len(triggered) == 1
