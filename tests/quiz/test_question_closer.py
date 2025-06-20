import datetime
import pytest
import discord

from cogs.quiz.question_closer import QuestionCloser
from cogs.quiz.question_state import QuestionInfo
from cogs.quiz.quiz_config import QuizAreaConfig


class DummyState:
    def __init__(self):
        self.cleared = []

    async def clear_active_question(self, area):
        self.cleared.append(area)


class DummyTracker:
    def __init__(self):
        self.inits = []

    def set_initialized(self, cid):
        self.inits.append(cid)


class DummyMessage:
    def __init__(self):
        self.id = 1
        self.embeds = [discord.Embed(title="t")]
        self.edited = None

    async def edit(self, **kwargs):
        self.edited = kwargs


class DummyChannel:
    def __init__(self, message):
        self.message = message

    async def fetch_message(self, mid):
        assert mid == self.message.id
        return self.message


class DummyUser:
    def __init__(self, name="Winner"):
        self.display_name = name


class DummyQuizCog:
    def __init__(self, tracker):
        self.current_questions = {}
        self.tracker = tracker


class DummyBot:
    def __init__(self, channel, tracker):
        self.quiz_data = {"area": QuizAreaConfig(channel_id=123, active=True)}
        self.quiz_cog = DummyQuizCog(tracker)
        self.main_guild = 0
        self._channel = channel

    def get_channel(self, cid):
        assert cid == 123
        return self._channel


@pytest.mark.asyncio
async def test_close_question_adds_user_answer():
    message = DummyMessage()
    channel = DummyChannel(message)
    tracker = DummyTracker()
    bot = DummyBot(channel, tracker)
    state = DummyState()
    closer = QuestionCloser(bot=bot, state=state)

    qinfo = QuestionInfo(
        message_id=1,
        end_time=datetime.datetime.utcnow(),
        answers=["yes"],
        frage="f",
    )
    bot.quiz_cog.current_questions["area"] = qinfo

    user = DummyUser("Tester")
    await closer.close_question(
        area="area",
        qinfo=qinfo,
        timed_out=False,
        winner=user,
        correct_answer="ja",
    )

    assert message.edited is not None
    embed = message.edited["embed"]
    fields = {f.name: f.value for f in embed.fields}
    assert fields.get("Richtige Antwort") == "yes"
    assert fields.get("Eingegebene Antwort") == "ja"
    assert embed.footer.text.startswith("✅ Tester")
    assert state.cleared == ["area"]
    assert tracker.inits == [123]
    assert "area" not in bot.quiz_cog.current_questions
