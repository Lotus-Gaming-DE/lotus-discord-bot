import datetime
import pytest

import lotus_bot.cogs.quiz.question_restorer as restorer_mod
from lotus_bot.cogs.quiz.question_state import QuestionInfo
from lotus_bot.cogs.quiz.quiz_config import QuizAreaConfig


class DummyBot:
    def __init__(self, channel):
        self._channel = channel
        self.quiz_data = {
            "area": QuizAreaConfig(channel_id=channel.id, question_state=None)
        }
        self.quiz_cog = type(
            "QuizCog",
            (),
            {
                "current_questions": {},
                "answered_users": {"area": set()},
                "closer": type("Closer", (), {"auto_close": lambda *a, **k: None})(),
            },
        )()

    async def fetch_channel(self, cid):
        return self._channel


class DummyMessage:
    def __init__(self, mid):
        self.id = mid
        self.embeds = []
        self.edits = []

    async def edit(self, *, embed=None, view=None):
        self.edits.append((embed, view))


class DummyChannel:
    def __init__(self, message=None, raise_notfound=False):
        self.id = 1
        self.message = message or DummyMessage(42)
        self.raise_notfound = raise_notfound

    async def fetch_message(self, mid):
        if self.raise_notfound:
            raise restorer_mod.discord.NotFound(None, None)
        return self.message


class DummyState:
    def __init__(self):
        self.cleared = []

    async def clear_active_question(self, area):
        self.cleared.append(area)

    def get_active_question(self, area):
        return None


def make_restorer(channel):
    bot = DummyBot(channel)

    def create_task(coro):
        return None

    state = DummyState()
    r = restorer_mod.QuestionRestorer(bot, state, create_task)
    return r, bot, state


@pytest.mark.asyncio
async def test_repost_question_success():
    channel = DummyChannel()
    rest, bot, state = make_restorer(channel)
    qinfo = QuestionInfo(
        message_id=42,
        end_time=datetime.datetime.utcnow() + datetime.timedelta(seconds=1),
        answers=["a"],
        frage="f",
        category="c",
    )

    await rest.repost_question("area", qinfo)

    assert bot.quiz_cog.current_questions["area"].message_id == 42
    assert channel.message.edits


@pytest.mark.asyncio
async def test_repost_question_missing_message():
    channel = DummyChannel(raise_notfound=True)
    rest, bot, state = make_restorer(channel)
    qinfo = QuestionInfo(
        message_id=42,
        end_time=datetime.datetime.utcnow(),
        answers=["a"],
        frage="f",
        category="c",
    )

    await rest.repost_question("area", qinfo)

    assert state.cleared == ["area"]
