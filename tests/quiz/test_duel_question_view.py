import datetime
import pytest


from cogs.quiz.duel import DuelQuestionView, _DuelAnswerModal


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


class DummyDuelInteraction:
    def __init__(self, user):
        self.user = user
        self.response = DummyResponse()
        self.created_at = datetime.datetime.utcnow()


@pytest.mark.asyncio
async def test_finish_sets_winner_and_disables_buttons():
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    view = DuelQuestionView(challenger, opponent, ["yes"])

    assert view.timeout == 30

    base = datetime.datetime.utcnow()
    view.responses = {
        challenger.id: ("yes", base + datetime.timedelta(seconds=1)),
        opponent.id: ("yes", base),
    }

    await view._finish()

    assert view.winner_id == opponent.id
    assert all(child.disabled for child in view.children)


@pytest.mark.asyncio
async def test_modal_ignores_after_finish():
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    view = DuelQuestionView(challenger, opponent, ["yes"])

    await view._finish()
    modal = _DuelAnswerModal(view)
    modal.answer._value = "foo"
    inter = DummyDuelInteraction(challenger)

    await modal.on_submit(inter)

    assert view.responses == {}
    assert inter.response.sent == [
        ("Die Runde ist bereits beendet.", {"ephemeral": True})
    ]
