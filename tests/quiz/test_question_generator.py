import random


from cogs.quiz.question_generator import QuestionGenerator


class DummyStateManager:
    def __init__(self):
        self.asked = {}

    def filter_unasked_questions(self, area, questions):
        asked = set(self.asked.get(area, []))
        return [q for q in questions if q.get("id") not in asked]

    def mark_question_as_asked(self, area, question_id):
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


def test_generate_dynamic_retries(monkeypatch):
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
    q = gen.generate("area")

    assert q["id"] == 2
