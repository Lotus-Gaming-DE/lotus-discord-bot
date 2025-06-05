import os
import sys
import datetime
import discord
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cogs.quiz.duel import QuizDuelGame, DuelInviteView, DuelConfig, DuelQuestionView


class DummyMember:
    def __init__(self, uid):
        self.id = uid
        self.display_name = f"user{uid}"
        self.mention = f"<@{uid}>"


class DummyChampionCog:
    def __init__(self):
        self.calls = []

        class DummyData:
            def __init__(self, totals):
                self.totals = totals

            async def get_total(self, uid):
                return self.totals.get(uid, 0)

        self.data = DummyData({})

    async def update_user_score(self, uid, delta, reason):
        self.calls.append((uid, delta, reason))


class DummyBot:
    def __init__(self, champion=True):
        self._champion = DummyChampionCog() if champion else None

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
        self.mention = "#thread"

    async def send(self, msg, **kwargs):
        self.sent.append(msg)

    async def edit(self, archived=True):
        self.archived = archived


class DummyMessage:
    def __init__(self, thread=None):
        self.thread = thread or DummyThread()
        self.edited_view = "INIT"

    async def create_thread(self, name):
        self.thread.name = name
        return self.thread

    async def edit(self, view=None):
        self.edited_view = view


class DummyFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, content, **kwargs):
        self.sent.append((content, kwargs))


class DummyResponse:
    async def defer(self):
        pass


class DummyInteraction:
    def __init__(self, user):
        self.user = user
        self.followup = DummyFollowup()
        self.response = DummyResponse()


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


@pytest.mark.asyncio
async def test_finish_handles_missing_champion():
    bot = DummyBot(champion=False)
    cog = DummyCog(bot)
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    thread = DummyThread()
    game = QuizDuelGame(cog, thread, "area", challenger, opponent, 20, "bo3")
    game.scores = {1: 2, 2: 1}

    await game._finish()

    assert thread.archived is True
    assert "Champion-System" in thread.sent[0]


@pytest.mark.asyncio
async def test_start_duel_success(monkeypatch):
    bot = DummyBot()
    bot._champion.data.totals = {"1": 50, "2": 40}
    cog = DummyCog(bot)
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    message = DummyMessage()
    view = DuelInviteView(challenger, DuelConfig("area", 20, "bo3"), cog)
    view.message = message

    run_called = []

    async def fake_run(self):
        run_called.append(True)

    monkeypatch.setattr(QuizDuelGame, "run", fake_run)

    interaction = DummyInteraction(opponent)
    await view.start_duel(interaction)

    assert bot._champion.calls[:2] == [
        (1, -20, "Quiz-Duell Einsatz"),
        (2, -20, "Quiz-Duell Einsatz"),
    ]
    assert message.edited_view == "INIT"
    assert run_called


@pytest.mark.asyncio
async def test_start_duel_no_champion_system():
    bot = DummyBot(champion=False)
    cog = DummyCog(bot)
    message = DummyMessage()
    view = DuelInviteView(DummyMember(1), DuelConfig("area", 20, "bo3"), cog)
    view.message = message
    interaction = DummyInteraction(DummyMember(2))

    await view.start_duel(interaction)

    assert view.accepted is False
    assert message.edited_view is None
    assert interaction.followup.sent[0][0].startswith("Champion-System")


@pytest.mark.asyncio
async def test_start_duel_insufficient_points_challenger():
    bot = DummyBot()
    bot._champion.data.totals = {"1": 10, "2": 30}
    cog = DummyCog(bot)
    message = DummyMessage()
    challenger = DummyMember(1)
    view = DuelInviteView(challenger, DuelConfig("area", 20, "bo3"), cog)
    view.message = message
    interaction = DummyInteraction(DummyMember(2))

    await view.start_duel(interaction)

    assert view.accepted is False
    assert message.edited_view is None
    assert bot._champion.calls == []
    assert interaction.followup.sent[0][0].startswith("Der Herausforderer")


@pytest.mark.asyncio
async def test_start_duel_insufficient_points_opponent():
    bot = DummyBot()
    bot._champion.data.totals = {"1": 30, "2": 10}
    cog = DummyCog(bot)
    message = DummyMessage()
    challenger = DummyMember(1)
    view = DuelInviteView(challenger, DuelConfig("area", 20, "bo3"), cog)
    view.message = message
    interaction = DummyInteraction(DummyMember(2))

    await view.start_duel(interaction)

    assert view.accepted is False
    assert message.edited_view == "INIT"
    assert bot._champion.calls == []
    assert interaction.followup.sent[0][0].startswith("Du hast nicht genug")


@pytest.mark.asyncio
async def test_game_run_dynamic(monkeypatch):
    challenger = DummyMember(1)
    opponent = DummyMember(2)

    class DummyProvider:
        def generate_all_types(self):
            return [
                {"frage": "f1", "antwort": "a1"},
                {"frage": "f2", "antwort": "a2"},
                {"frage": "f3", "antwort": "a3"},
            ]

    class DummyQG:
        def __init__(self):
            self.dynamic_providers = {"area": DummyProvider()}

        def generate(self, area):
            return None

        def get_dynamic_provider(self, area):
            return self.dynamic_providers.get(area)

    bot = DummyBot()
    bot.quiz_data = {"area": {"question_generator": DummyQG()}}
    cog = DummyCog(bot)

    responses = [
        {
            challenger.id: ("a1", datetime.datetime.utcnow() + datetime.timedelta(seconds=1)),
            opponent.id: ("a1", datetime.datetime.utcnow()),
        },
        {challenger.id: ("a2", datetime.datetime.utcnow())},
        {
            challenger.id: ("a3", datetime.datetime.utcnow()),
            opponent.id: ("a3", datetime.datetime.utcnow() + datetime.timedelta(seconds=1)),
        },
    ]
    resp_iter = iter(responses)

    class DummyRunThread(DummyThread):
        async def send(self, msg=None, **kwargs):
            self.sent.append(kwargs.get("embed", msg))
            return DummyMessage()

    class AutoView(DuelQuestionView):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._data = next(resp_iter)

        async def wait(self):
            self.responses = self._data
            await self._finish()

    monkeypatch.setattr("cogs.quiz.duel.DuelQuestionView", AutoView)

    thread = DummyRunThread()
    game = QuizDuelGame(cog, thread, "area", challenger, opponent, 20, "dynamic")
    await game.run()

    embeds = [m for m in thread.sent if isinstance(m, discord.Embed)]
    assert len(embeds) == 3
    assert game.scores == {1: 3, 2: 2}
