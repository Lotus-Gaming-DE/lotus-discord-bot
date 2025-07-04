import json
import datetime


from lotus_bot.cogs.quiz.question_state import QuestionStateManager, QuestionInfo


import pytest


@pytest.mark.asyncio
async def test_set_active_question(tmp_path):
    state_file = tmp_path / "state.json"
    manager = QuestionStateManager(str(state_file))
    question = QuestionInfo(
        message_id=1,
        end_time=datetime.datetime.utcnow(),
        answers=["a"],
        frage="foo",
    )
    await manager.set_active_question("area1", question)

    restored = manager.get_active_question("area1")
    assert restored == question

    with open(state_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["active"]["area1"] == question.to_dict()


@pytest.mark.asyncio
async def test_mark_question_as_asked(tmp_path):
    state_file = tmp_path / "state.json"
    manager = QuestionStateManager(str(state_file))
    await manager.mark_question_as_asked("area1", 42)
    await manager.mark_question_as_asked("area1", 42)

    assert manager.get_asked_questions("area1") == [42]

    with open(state_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["history"]["area1"] == [42]


@pytest.mark.asyncio
async def test_filter_unasked_questions(tmp_path):
    state_file = tmp_path / "state.json"
    manager = QuestionStateManager(str(state_file))
    await manager.mark_question_as_asked("area1", 1)
    await manager.mark_question_as_asked("area1", 3)

    questions = [
        {"id": 1},
        {"id": 2},
        {"id": 3},
        {"id": 4},
    ]

    filtered = manager.filter_unasked_questions("area1", questions)
    filtered_ids = [q["id"] for q in filtered]

    assert filtered_ids == [2, 4]
