import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cogs.quiz.duel import QuizDuelGame


class DummyMember:
    def __init__(self, uid):
        self.id = uid
        self.display_name = f"user{uid}"


class DummyChampionCog:
    def __init__(self):
        self.calls = []

    async def update_user_score(self, uid, delta, reason):
        self.calls.append((uid, delta, reason))


class DummyBot:
    def __init__(self):
        self._champion = DummyChampionCog()

    def get_cog(self, name):
        if name == "ChampionCog":
            return self._champion
        return None

    def get_user(self, uid):
        return DummyMember(uid)


class DummyCog:
    def __init__(self, bot):
        self.bot = bot


class DummyThread:
    def __init__(self):
        self.sent = []
        self.archived = False

    async def send(self, msg, **kwargs):
        self.sent.append(msg)

    async def edit(self, archived=True):
        self.archived = archived


@pytest.mark.asyncio
async def test_finish_awards_pot_to_winner():
    bot = DummyBot()
    cog = DummyCog(bot)
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    thread = DummyThread()
    game = QuizDuelGame(cog, thread, "area", challenger, opponent, 20, "bo3")
    game.scores = {1: 2, 2: 1}

    await game._finish()

    assert bot._champion.calls == [(1, 20, "Quiz-Duell Gewinn")]
    assert thread.archived is True


@pytest.mark.asyncio
async def test_finish_refunds_on_tie():
    bot = DummyBot()
    cog = DummyCog(bot)
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    thread = DummyThread()
    game = QuizDuelGame(cog, thread, "area", challenger, opponent, 20, "bo3")
    game.scores = {1: 1, 2: 1}

    await game._finish()

    assert set(bot._champion.calls) == {
        (1, 10, "Quiz-Duell Rückgabe"),
        (2, 10, "Quiz-Duell Rückgabe"),
    }
    assert thread.archived is True
