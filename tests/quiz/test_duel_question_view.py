import datetime
import pytest


from lotus_bot.cogs.quiz.duel import DuelQuestionView, _DuelAnswerModal
import discord


class DummyMember:
    def __init__(self, uid):
        self.id = uid
        self.display_name = f"user{uid}"
        self.mention = f"<@{uid}>"


class DummyResponse:
    def __init__(self):
        self.sent = []

    async def send_message(self, content, **kwargs):
        self.sent.append((content, kwargs))


class DummyMessage:
    def __init__(self, created_at=None):
        self.embeds = [discord.Embed(title="t")]
        self.edited = None
        self.created_at = created_at or datetime.datetime.utcnow()

    async def edit(self, **kwargs):
        self.edited = kwargs


class DummyDuelInteraction:
    def __init__(self, user):
        self.user = user
        self.response = DummyResponse()
        self.created_at = datetime.datetime.utcnow()


@pytest.mark.asyncio
async def test_finish_sets_winner_and_disables_buttons():
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    view = DuelQuestionView(challenger, opponent, ["yes"], 30)
    base = datetime.datetime(2022, 1, 1, 0, 0, 0)
    view.message = DummyMessage(created_at=base)

    assert view.timeout == 30

    view.responses = {
        challenger.id: ("yes", base + datetime.timedelta(seconds=1)),
        opponent.id: ("yes", base),
    }

    await view._finish()

    assert view.winner_id == opponent.id
    assert all(child.disabled for child in view.children)
    fields = {f.name: f.value for f in view.message.edited["embed"].fields}
    assert "Richtige Antwort" in fields
    assert "Antworten" in fields
    lines = fields["Antworten"].split("\n")
    assert lines[0].endswith("(1.0s)")
    assert lines[1].endswith("(0.0s)")
    view.stop()


@pytest.mark.asyncio
async def test_modal_ignores_after_finish():
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    view = DuelQuestionView(challenger, opponent, ["yes"], 30)

    await view._finish()
    await view._finish()

    modal = _DuelAnswerModal(view)
    modal.answer._value = "foo"
    inter = DummyDuelInteraction(challenger)

    await modal.on_submit(inter)

    assert view.responses == {}
    assert inter.response.sent == [
        ("Die Runde ist bereits beendet.", {"ephemeral": True})
    ]
    view.stop()


@pytest.mark.asyncio
async def test_on_timeout_sets_footer():
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    view = DuelQuestionView(challenger, opponent, ["yes"], 30)
    view.message = DummyMessage()

    await view.on_timeout()

    assert view.message.edited["embed"].footer.text.startswith("⏰")
    view.stop()
