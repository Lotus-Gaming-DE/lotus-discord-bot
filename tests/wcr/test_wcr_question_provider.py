import random
import json


from cogs.quiz.area_providers.wcr import WCRQuestionProvider
from cogs.quiz.area_providers.base import DynamicQuestionProvider


class DummyBot:
    pass


def create_provider(wcr_data):
    bot = DummyBot()
    from pathlib import Path

    with open(Path("data/quiz/templates/wcr.json"), "r", encoding="utf-8") as f:
        templates = json.load(f)

    bot.data = {"wcr": wcr_data, "quiz": {"templates": {"wcr": templates}}}
    return WCRQuestionProvider(bot, language="de")


def test_provider_inherits_base(wcr_data):
    provider = create_provider(wcr_data)
    assert isinstance(provider, DynamicQuestionProvider)


def test_generate_type_1(wcr_data):
    provider = create_provider(wcr_data)
    q = provider.generate_type_1()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_2(wcr_data):
    provider = create_provider(wcr_data)
    q = provider.generate_type_2()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_3(wcr_data):
    provider = create_provider(wcr_data)
    q = provider.generate_type_3()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_4(wcr_data, monkeypatch):
    provider = create_provider(wcr_data)
    # make selection deterministic
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    q = provider.generate_type_4()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_5(wcr_data, monkeypatch):
    provider = create_provider(wcr_data)
    monkeypatch.setattr(random, "choice", lambda seq: "damage")
    monkeypatch.setattr(random, "sample", lambda seq, k: seq[:k])
    q = provider.generate_type_5()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_5_requires_two_units(wcr_data, monkeypatch):
    provider = create_provider(wcr_data)
    units = provider.units
    provider.units = [units[1], units[3]]

    monkeypatch.setattr(random, "choice", lambda seq: "damage")

    def fail(*args, **kwargs):
        raise AssertionError("sample should not be called")

    monkeypatch.setattr(random, "sample", fail)
    q = provider.generate_type_5()
    assert q is None


def test_generate_all_types(wcr_data, monkeypatch):
    provider = create_provider(wcr_data)

    monkeypatch.setattr(
        provider, "generate_type_1", lambda: {"frage": "f1", "antwort": "a", "id": 1}
    )
    monkeypatch.setattr(
        provider, "generate_type_2", lambda: {"frage": "f2", "antwort": "b", "id": 2}
    )
    monkeypatch.setattr(
        provider, "generate_type_3", lambda: {"frage": "f3", "antwort": "c", "id": 3}
    )
    monkeypatch.setattr(
        provider, "generate_type_4", lambda: {"frage": "f4", "antwort": "d", "id": 4}
    )
    monkeypatch.setattr(
        provider, "generate_type_5", lambda: {"frage": "f5", "antwort": "e", "id": 5}
    )

    qs = provider.generate_all_types()
    assert [q["id"] for q in qs] == [1, 2, 3, 4, 5]
