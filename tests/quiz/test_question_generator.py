import random
import pytest

from cogs.quiz.question_generator import QuestionGenerator


class DummyStateManager:
    def __init__(self):
        self.asked = {}

    def filter_unasked_questions(self, area, questions):
        asked = set(self.asked.get(area, []))
        return [q for q in questions if q.get("id") not in asked]

    async def mark_question_as_asked(self, area, question_id):
        self.asked.setdefault(area, []).append(question_id)

    def get_asked_questions(self, area):
        return self.asked.get(area, [])


def create_generator():
    questions = {
        "de": {
            "area1": [
                {"id": 1, "frage": "f1", "antwort": "a1"},
                {"id": 2, "frage": "f2", "antwort": "a2"},
            ]
        }
    }
    return QuestionGenerator(questions, DummyStateManager(), {})


@pytest.mark.asyncio
async def test_generate_selects_unasked(monkeypatch):
    gen = create_generator()
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q1 = await gen.generate("area1")
    assert q1["id"] == 1

    q2 = await gen.generate("area1")
    assert q2["id"] == 2

    assert await gen.generate("area1") is None


@pytest.mark.asyncio
async def test_generate_handles_missing_area(monkeypatch):
    state = DummyStateManager()
    gen = QuestionGenerator({"de": {}}, state, {})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    assert await gen.generate("missing") is None
    assert await gen.generate(None) is None


def test_get_dynamic_provider():
    state = DummyStateManager()
    provider = object()
    gen = QuestionGenerator({"de": {}}, state, {"area": provider})
    assert gen.get_dynamic_provider("area") is provider
    assert gen.get_dynamic_provider("missing") is None


@pytest.mark.asyncio
async def test_generate_dynamic_retries(monkeypatch):
    class DummyProvider:
        def __init__(self):
            self.calls = 0

        def generate(self):
            self.calls += 1
            if self.calls == 1:
                return {"id": 1, "frage": "f1", "antwort": "a1"}
            return {"id": 2, "frage": "f2", "antwort": "a2"}

    state = DummyStateManager()
    state.asked = {"area": [1]}

    gen = QuestionGenerator({"de": {}}, state, {"area": DummyProvider()})
    q = await gen.generate("area")

    assert q["id"] == 2


@pytest.mark.asyncio
async def test_generate_dynamic_fallback(monkeypatch):
    class DummyProvider:
        def __init__(self):
            self.calls = 0
            self.fallback_calls = 0

        def generate(self):
            self.calls += 1
            return {"id": 1, "frage": "f1", "antwort": "a1"}

        def generate_all_types(self):
            self.fallback_calls += 1
            return [
                {"id": 1, "frage": "f1", "antwort": "a1"},
                {"id": 2, "frage": "f2", "antwort": "a2"},
            ]

    state = DummyStateManager()
    state.asked = {"area": [1]}

    gen = QuestionGenerator({"de": {}}, state, {"area": DummyProvider()})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = await gen.generate("area")

    assert q["id"] == 2

    assert gen.dynamic_providers["area"].calls == 5
    assert gen.dynamic_providers["area"].fallback_calls == 1
