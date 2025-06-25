import pytest

from lotus_bot.cogs.quiz.quiz_config import QuizAreaConfig
from lotus_bot.cogs.quiz.slash_commands import area_autocomplete


class DummyBot:
    def __init__(self):
        self.quiz_data = {}


class DummyInteraction:
    def __init__(self, bot):
        self.client = bot


@pytest.mark.asyncio
async def test_area_autocomplete_returns_all():
    bot = DummyBot()
    bot.quiz_data = {"a": QuizAreaConfig(), "b": QuizAreaConfig()}
    inter = DummyInteraction(bot)

    choices = await area_autocomplete(inter, "")

    assert [c.name for c in choices] == ["a", "b"]
    assert [c.value for c in choices] == ["a", "b"]


@pytest.mark.asyncio
async def test_area_autocomplete_filters_case_insensitive():
    bot = DummyBot()
    bot.quiz_data = {"AreaOne": QuizAreaConfig(), "Two": QuizAreaConfig()}
    inter = DummyInteraction(bot)

    choices = await area_autocomplete(inter, "area")

    assert len(choices) == 1
    assert choices[0].name == "AreaOne"
    assert choices[0].value == "AreaOne"
