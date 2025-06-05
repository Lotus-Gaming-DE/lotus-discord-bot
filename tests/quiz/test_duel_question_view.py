import os
import sys
import datetime
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from cogs.quiz.duel import DuelQuestionView


class DummyMember:
    def __init__(self, uid):
        self.id = uid
        self.display_name = f"user{uid}"
        self.mention = f"<@{uid}>"


@pytest.mark.asyncio
async def test_finish_sets_winner_and_disables_buttons():
    challenger = DummyMember(1)
    opponent = DummyMember(2)
    view = DuelQuestionView(challenger, opponent, ["yes"])

    base = datetime.datetime.utcnow()
    view.responses = {
        challenger.id: ("yes", base + datetime.timedelta(seconds=1)),
        opponent.id: ("yes", base),
    }

    await view._finish()

    assert view.winner_id == opponent.id
    assert all(child.disabled for child in view.children)
