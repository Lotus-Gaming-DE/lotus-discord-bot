import pytest

from cogs.quiz.question_generator import QuestionGenerator
from cogs.quiz.quiz_config import QuizAreaConfig
import cogs.quiz.slash_commands as slash_mod


class DummyProvider:
    def __init__(self, language="de"):
        self.language = language


class DummyState:
    def filter_unasked_questions(self, area, questions):
        return questions

    async def mark_question_as_asked(self, area, qid):
        pass

    def get_asked_questions(self, area):
        return []


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content, **kwargs):
        self.messages.append({"content": content, **kwargs})


class DummyChannel:
    def __init__(self, cid):
        self.id = cid


class DummyInteraction:
    def __init__(self, bot, channel_id=1):
        self.client = bot
        self.channel = DummyChannel(channel_id)
        self.response = DummyResponse()


class DummyBot:
    def __init__(self):
        self.quiz_data = {}

    def get_cog(self, name):
        return None


@pytest.mark.asyncio
async def test_language_command_updates_provider(monkeypatch):
    monkeypatch.setattr(slash_mod, "save_area_config", lambda b: None)
    provider = DummyProvider("de")
    qg = QuestionGenerator({}, DummyState(), {"area": provider})
    bot = DummyBot()
    bot.quiz_data = {
        "area": QuizAreaConfig(
            channel_id=1,
            language="de",
            question_state=DummyState(),
            question_generator=qg,
        )
    }
    inter = DummyInteraction(bot, 1)

    await slash_mod.language.callback(inter, "en")

    assert provider.language == "en"
    assert bot.quiz_data["area"].language == "en"


@pytest.mark.asyncio
async def test_enable_command_updates_provider(monkeypatch):
    monkeypatch.setattr(slash_mod, "save_area_config", lambda b: None)
    provider = DummyProvider("de")
    qg = QuestionGenerator({}, DummyState(), {"area": provider})
    bot = DummyBot()
    bot.quiz_data = {
        "area": QuizAreaConfig(
            channel_id=None,
            language="de",
            active=False,
            question_state=DummyState(),
            question_generator=qg,
        )
    }
    inter = DummyInteraction(bot, 1)

    await slash_mod.enable.callback(inter, "area", "en")

    assert provider.language == "en"
    assert bot.quiz_data["area"].language == "en"
    assert bot.quiz_data["area"].channel_id == 1
