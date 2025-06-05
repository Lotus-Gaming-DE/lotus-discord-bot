import os
import sys
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from cogs.quiz.question_generator import QuestionGenerator


class DummyStateManager:
    def __init__(self):
        self.asked = {}

    def filter_unasked_questions(self, area, questions):
        asked = set(self.asked.get(area, []))
        return [q for q in questions if q.get("id") not in asked]

    def mark_question_as_asked(self, area, question_id):
        self.asked.setdefault(area, []).append(question_id)


def create_generator():
    questions = {"de": {"area1": [
        {"id": 1, "frage": "f1", "antwort": "a1"},
        {"id": 2, "frage": "f2", "antwort": "a2"},
    ]}}
    return QuestionGenerator(questions, DummyStateManager(), {})


def test_generate_selects_unasked(monkeypatch):
    gen = create_generator()
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q1 = gen.generate("area1")
    assert q1["id"] == 1

    q2 = gen.generate("area1")
    assert q2["id"] == 2

    assert gen.generate("area1") is None


def test_generate_handles_missing_area(monkeypatch):
    state = DummyStateManager()
    gen = QuestionGenerator({"de": {}}, state, {})
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    assert gen.generate("missing") is None
    assert gen.generate(None) is None


def test_get_dynamic_provider():
    state = DummyStateManager()
    provider = object()
    gen = QuestionGenerator({"de": {}}, state, {"area": provider})
    assert gen.get_dynamic_provider("area") is provider
    assert gen.get_dynamic_provider("missing") is None
