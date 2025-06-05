import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from bot import MyBot
import cogs.quiz.cog as quiz_cog_mod
import cogs.quiz.scheduler as scheduler_mod
import cogs.quiz.message_tracker as msg_mod


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


def test_scheduler_start_and_stop(monkeypatch):
    monkeypatch.setattr(quiz_cog_mod, "create_logged_task", fake_task_general)
    monkeypatch.setattr(msg_mod, "create_logged_task", fake_task_general)
    monkeypatch.setattr(scheduler_mod, "create_logged_task", fake_task_scheduler)
    monkeypatch.setattr(quiz_cog_mod.QuestionRestorer, "restore_all", lambda self: None)

    bot = MyBot()
    bot.data = {"quiz": {"questions": {"de": {}}, "languages": ["de"]}}
    bot.quiz_data = {
        "area1": {"channel_id": 1, "active": True, "question_state": DummyState()},
        "area2": {"channel_id": 2, "active": False, "question_state": DummyState()},
    }

    cog = quiz_cog_mod.QuizCog(bot)

    assert len(cog.schedulers) == 1
    assert len(fake_task_scheduler.tasks) == 1
    task = fake_task_scheduler.tasks[0]
    assert not task.cancelled

    cog.cog_unload()
    assert task.cancelled
