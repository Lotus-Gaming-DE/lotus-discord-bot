import os
import sys
import json
import random


from cogs.quiz.area_providers.wcr import WCRQuestionProvider
from cogs.quiz.area_providers.base import DynamicQuestionProvider

class DummyBot:
    pass

def create_provider():
    bot = DummyBot()
    bot.data = {
        "wcr": {
            "units": json.load(open("data/wcr/units.json", "r", encoding="utf-8")),
            "locals": {
                "de": json.load(open("data/wcr/locals/de.json", "r", encoding="utf-8")),
                "en": json.load(open("data/wcr/locals/en.json", "r", encoding="utf-8")),
            },
            "pictures": json.load(open("data/wcr/pictures.json", "r", encoding="utf-8")),
        }
    }
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
    units = provider.units
    monkeypatch.setattr(random, "sample", lambda seq, k: [units[0], units[1]])
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    q = provider.generate_type_5()
    assert q is not None
    assert "frage" in q and "antwort" in q and "id" in q


def test_generate_all_types(monkeypatch):
    provider = create_provider()

    monkeypatch.setattr(provider, "generate_type_1", lambda: {"frage": "f1", "antwort": "a", "id": 1})
    monkeypatch.setattr(provider, "generate_type_2", lambda: {"frage": "f2", "antwort": "b", "id": 2})
    monkeypatch.setattr(provider, "generate_type_3", lambda: {"frage": "f3", "antwort": "c", "id": 3})
    monkeypatch.setattr(provider, "generate_type_4", lambda: {"frage": "f4", "antwort": "d", "id": 4})
    monkeypatch.setattr(provider, "generate_type_5", lambda: {"frage": "f5", "antwort": "e", "id": 5})

    qs = provider.generate_all_types()
    assert [q["id"] for q in qs] == [1, 2, 3, 4, 5]
