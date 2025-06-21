import random


from cogs.quiz.area_providers.wcr import WCRQuestionProvider
from cogs.quiz.area_providers.base import DynamicQuestionProvider


class DummyBot:
    pass


def create_provider():
    bot = DummyBot()
    from cogs.wcr.utils import load_wcr_data

    bot.data = {"wcr": load_wcr_data()}
    return WCRQuestionProvider(bot, language="de")


def test_provider_inherits_base():
    provider = create_provider()
    assert isinstance(provider, DynamicQuestionProvider)


def test_generate_type_1():
    provider = create_provider()
    q = provider.generate_type_1()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_2():
    provider = create_provider()
    q = provider.generate_type_2()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_3():
    provider = create_provider()
    q = provider.generate_type_3()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_4(monkeypatch):
    provider = create_provider()
    # make selection deterministic
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    q = provider.generate_type_4()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_5(monkeypatch):
    provider = create_provider()
    monkeypatch.setattr(random, "choice", lambda seq: "damage")
    monkeypatch.setattr(random, "sample", lambda seq, k: seq[:k])
    q = provider.generate_type_5()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_type_5_requires_two_units(monkeypatch):
    provider = create_provider()
    units = provider.units
    provider.units = [units[1], units[3]]

    monkeypatch.setattr(random, "choice", lambda seq: "damage")

    def fail(*args, **kwargs):
        raise AssertionError("sample should not be called")

    monkeypatch.setattr(random, "sample", fail)
    q = provider.generate_type_5()
    assert q is None


def test_generate_all_types(monkeypatch):
    provider = create_provider()

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
