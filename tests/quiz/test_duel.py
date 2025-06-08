import datetime
import discord
import pytest


from cogs.quiz.duel import QuizDuelGame, DuelInviteView, DuelConfig, DuelQuestionView
from cogs.quiz.quiz_config import QuizAreaConfig


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
        self.active_duels = set()


class DummyThread:
    def __init__(self):
        self.sent = []
        self.archived = False
        self.mention = "#thread"

    async def send(self, msg, **kwargs):
        self.sent.append(msg)

    async def edit(self, archived=True):
        self.archived = archived


class DummyChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


class DummyMessage:
    def __init__(self, thread=None, channel=None):
        self.thread = thread or DummyThread()
        self.channel = channel or DummyChannel()
        self.edited_view = "INIT"
        self.embeds = []

    async def create_thread(self, name, **kwargs):
        self.thread.name = name
        return self.thread

    async def edit(self, view=None, **kwargs):
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
    game = QuizDuelGame(
        cog, thread, "area", challenger, opponent, 20, "box", None, best_of=3
    )
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
    game = QuizDuelGame(
        cog, thread, "area", challenger, opponent, 20, "box", None, best_of=3
    )
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
    game = QuizDuelGame(
        cog, thread, "area", challenger, opponent, 20, "box", None, best_of=3
    )
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
    view = DuelInviteView(challenger, DuelConfig("area", 20, "box", best_of=3), cog)
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
    assert message.edited_view is None
    assert run_called


@pytest.mark.asyncio
async def test_start_duel_no_champion_system():
    bot = DummyBot(champion=False)
    cog = DummyCog(bot)
    message = DummyMessage()
    view = DuelInviteView(DummyMember(1), DuelConfig("area", 20, "box", best_of=3), cog)
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
    view = DuelInviteView(challenger, DuelConfig("area", 20, "box", best_of=3), cog)
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
    view = DuelInviteView(challenger, DuelConfig("area", 20, "box", best_of=3), cog)
    view.message = message
    interaction = DummyInteraction(DummyMember(2))

    await view.start_duel(interaction)

    assert view.accepted is False
    assert message.edited_view == "INIT"
    assert bot._champion.calls == []
    assert interaction.followup.sent[0][0].startswith("Du hast nicht genug")


@pytest.mark.asyncio
async def test_start_duel_thread_fail(monkeypatch):
    bot = DummyBot()
    bot._champion.data.totals = {"1": 30, "2": 30}
    cog = DummyCog(bot)
    message = DummyMessage()

    async def fail_thread(*args, **kwargs):
        raise Exception("thread fail")

    monkeypatch.setattr(DummyMessage, "create_thread", fail_thread)

    challenger = DummyMember(1)
    view = DuelInviteView(challenger, DuelConfig("area", 20, "box", best_of=3), cog)
    view.message = message
    view.accepted = True
    interaction = DummyInteraction(DummyMember(2))

    await view.start_duel(interaction)

    assert view.accepted is False
    assert message.edited_view is None
    assert bot._champion.calls == [
        (1, -20, "Quiz-Duell Einsatz"),
        (2, -20, "Quiz-Duell Einsatz"),
        (1, 20, "Quiz-Duell Rückgabe"),
        (2, 20, "Quiz-Duell Rückgabe"),
    ]


@pytest.mark.asyncio
async def test_invite_timeout_notifies():
    class DummyChannel:
        def __init__(self):
            self.sent = []

        async def send(self, msg, **kwargs):
            self.sent.append(msg)

    class DummyMessage:
        def __init__(self, channel):
            self.channel = channel
            self.edited_view = "INIT"

        async def edit(self, view=None):
            self.edited_view = view

    channel = DummyChannel()
    message = DummyMessage(channel)
    bot = DummyBot()
    cog = DummyCog(bot)
    challenger = DummyMember(1)
    view = DuelInviteView(challenger, DuelConfig("area", 20, "box", best_of=3), cog)
    channel = DummyChannel()
    message = DummyMessage(channel=channel)
    view = DuelInviteView(DummyMember(1), DuelConfig("area", 5, "box", best_of=3), cog)
    view.message = message

    await view.on_timeout()

    assert channel.sent == [f"{challenger.mention}, deine Duellanfrage ist abgelaufen."]
    assert message.edited_view is None
    assert message.edited_view is None
    assert channel.sent == ["<@1>, deine Duellanfrage ist abgelaufen."]


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
    bot.quiz_data = {"area": QuizAreaConfig(question_generator=DummyQG())}
    cog = DummyCog(bot)

    responses = [
        {
            challenger.id: (
                "a1",
                datetime.datetime.utcnow() + datetime.timedelta(seconds=1),
            ),
            opponent.id: ("a1", datetime.datetime.utcnow()),
        },
        {challenger.id: ("a2", datetime.datetime.utcnow())},
        {
            challenger.id: ("a3", datetime.datetime.utcnow()),
            opponent.id: (
                "a3",
                datetime.datetime.utcnow() + datetime.timedelta(seconds=1),
            ),
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
    game = QuizDuelGame(cog, thread, "area", challenger, opponent, 20, "dynamic", None)
    await game.run()

    embeds = [m for m in thread.sent if isinstance(m, discord.Embed)]
    assert len(embeds) == 3
    assert game.scores == {1: 2, 2: 1}


@pytest.mark.asyncio
async def test_game_run_dynamic_tiebreak(monkeypatch):
    challenger = DummyMember(1)
    opponent = DummyMember(2)

    class DummyProvider:
        def generate_all_types(self):
            return [
                {"frage": "f1", "antwort": "a1"},
                {"frage": "f2", "antwort": "a2"},
            ]

    class DummyQG:
        def __init__(self):
            self.dynamic_providers = {"area": DummyProvider()}

        def generate(self, area):
            return None

        def get_dynamic_provider(self, area):
            return self.dynamic_providers.get(area)

    bot = DummyBot()
    bot.quiz_data = {"area": QuizAreaConfig(question_generator=DummyQG())}
    cog = DummyCog(bot)

    base = datetime.datetime.utcnow()
    responses = [
        {challenger.id: ("a1", base)},
        {opponent.id: ("a2", base + datetime.timedelta(seconds=5))},
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
    game = QuizDuelGame(cog, thread, "area", challenger, opponent, 20, "dynamic", None)
    await game.run()

    assert game.scores == {1: 1, 2: 1}
    assert game.winner_id == opponent.id


@pytest.mark.asyncio
async def test_game_run_sequential_sends_question():
    class DummyQG:
        def __init__(self):
            self.calls = 0

        def generate(self, area):
            self.calls += 1
            if self.calls == 1:
                return {"frage": "f1", "antwort": "a1"}
            return None

    class DummyRunThread(DummyThread):
        async def send(self, msg=None, **kwargs):
            self.sent.append(kwargs.get("embed", msg))
            if view := kwargs.get("view"):
                await view._finish()
            return DummyMessage()

    bot = DummyBot()
    bot.quiz_data = {"area": QuizAreaConfig(question_generator=DummyQG())}
    cog = DummyCog(bot)
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    thread = DummyRunThread()
    game = QuizDuelGame(
        cog, thread, "area", challenger, opponent, 20, "box", None, best_of=3
    )

    await game.run()

    embeds = [m for m in thread.sent if isinstance(m, discord.Embed)]
    assert embeds


@pytest.mark.asyncio
async def test_game_run_fetches_user_when_cache_empty(monkeypatch):
    class DummyQG:
        def generate(self, area):
            return {"frage": "f1", "antwort": "a1"}

    class DummyRunThread(DummyThread):
        async def send(self, msg=None, **kwargs):
            self.sent.append(kwargs.get("embed", msg))
            if view := kwargs.get("view"):
                await view._finish()
            return DummyMessage()

    class AutoView(DuelQuestionView):
        async def wait(self):
            self.winner_id = challenger.id
            await self._finish()

    class NoCacheBot(DummyBot):
        def get_user(self, uid):
            return None

    challenger = DummyMember(1)
    opponent = DummyMember(2)
    bot = NoCacheBot()

    async def fetch(uid):
        return DummyMember(uid)

    bot.fetch_user = fetch
    bot.quiz_data = {"area": QuizAreaConfig(question_generator=DummyQG())}
    cog = DummyCog(bot)

    monkeypatch.setattr("cogs.quiz.duel.DuelQuestionView", AutoView)

    thread = DummyRunThread()
    game = QuizDuelGame(
        cog, thread, "area", challenger, opponent, 20, "box", None, best_of=3
    )
    game.scores = {challenger.id: 1, opponent.id: 1}
    await game.run()

    assert any("user1" in m for m in thread.sent if isinstance(m, str))


@pytest.mark.asyncio
async def test_finish_fetches_user_when_cache_empty():
    class NoCacheBot(DummyBot):
        def get_user(self, uid):
            return None

    fetch_calls = []

    async def fetch(uid):
        fetch_calls.append(uid)
        return DummyMember(uid)

    bot = NoCacheBot()
    bot.fetch_user = fetch
    cog = DummyCog(bot)
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    thread = DummyThread()
    game = QuizDuelGame(
        cog, thread, "area", challenger, opponent, 20, "box", None, best_of=3
    )
    game.scores = {1: 2, 2: 1}

    await game._finish()

    assert fetch_calls == [1]
    assert any("user1" in m for m in thread.sent)


@pytest.mark.asyncio
async def test_start_duel_blocks_active_players():
    bot = DummyBot()
    bot._champion.data.totals = {"1": 30, "2": 30}
    cog = DummyCog(bot)
    cog.active_duels.add(1)
    message = DummyMessage()
    view = DuelInviteView(DummyMember(1), DuelConfig("area", 20, "bo3"), cog)
    view.message = message
    interaction = DummyInteraction(DummyMember(2))

    await view.start_duel(interaction)

    assert interaction.followup.sent
    assert view.accepted is False
    assert bot._champion.calls == []
    assert message.edited_view is None


@pytest.mark.asyncio
async def test_finish_removes_active_duels():
    bot = DummyBot()
    cog = DummyCog(bot)
    cog.active_duels = {1, 2}
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    thread = DummyThread()
    game = QuizDuelGame(cog, thread, "area", challenger, opponent, 20, "bo3", None)
    game.scores = {1: 2, 2: 1}

    await game._finish()

    assert cog.active_duels == set()


class SlashResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, msg, **kwargs):
        self.messages.append((msg, kwargs))


class SlashChannel:
    def __init__(self, cid=123):
        self.id = cid
        self.sent = []

    async def send(self, embed=None, view=None):
        self.sent.append((embed, view))
        return DummyMessage()


class SlashInteraction:
    def __init__(self, bot, user, channel):
        self.client = bot
        self.user = user
        self.channel = channel
        self.response = SlashResponse()


@pytest.mark.asyncio
async def test_slash_duel_blocks_active_player(monkeypatch):
    bot = DummyBot()
    bot._champion.data.totals = {"1": 50}

    class DummyQG:
        def __init__(self):
            self.dynamic_providers = {}

    bot.quiz_data = {
        "area": QuizAreaConfig(channel_id=123, question_generator=DummyQG())
    }
    quiz_cog = DummyCog(bot)
    quiz_cog.active_duels.add(1)

    def get_cog(name):
        if name == "ChampionCog":
            return bot._champion
        if name == "QuizCog":
            return quiz_cog
        return None

    monkeypatch.setattr(bot, "get_cog", get_cog)

    from cogs.quiz.slash_commands import duel as duel_cmd

    inter = SlashInteraction(bot, DummyMember(1), SlashChannel())
    await duel_cmd.callback(inter, 10)

    assert inter.response.messages
    msg, kwargs = inter.response.messages[0]
    assert "bereits" in msg
    assert kwargs.get("ephemeral")
    assert not inter.channel.sent
