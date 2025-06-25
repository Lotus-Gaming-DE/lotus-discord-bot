import pytest

from lotus_bot.cogs.quiz.stats import QuizStats
from lotus_bot.cogs.quiz.views import AnswerModal
from collections import defaultdict


class DummyUser:
    def __init__(self, uid):
        self.id = uid
        self.display_name = f"User{uid}"


class DummyResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content, **kwargs):
        self.messages.append((content, kwargs.get("ephemeral")))


class DummyInteraction:
    def __init__(self, user):
        self.user = user
        self.response = DummyResponse()
        self.created_at = None


class DummyBot:
    def get_cog(self, name):
        return None


class DummyCog:
    def __init__(self, stats):
        self.stats = stats
        self.bot = DummyBot()
        self.answered_users = defaultdict(set)
        self.current_questions = {}
        self.closer = None


@pytest.mark.asyncio
async def test_stats_increment(tmp_path):
    path = tmp_path / "stats.json"
    stats = QuizStats(str(path))

    assert stats.get(1) == 0
    await stats.increment(1)
    await stats.increment(1)
    assert stats.get(1) == 2
    assert path.exists()


@pytest.mark.asyncio
async def test_answer_modal_updates_stats(tmp_path):
    path = tmp_path / "stats.json"
    stats = QuizStats(str(path))
    cog = DummyCog(stats)
    modal = AnswerModal("area", ["yes"], cog)
    modal.answer._value = "yes"
    inter = DummyInteraction(DummyUser(1))

    await modal.on_submit(inter)

    assert stats.get(1) == 1
    assert inter.response.messages[0][0]
