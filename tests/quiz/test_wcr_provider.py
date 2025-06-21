import random
import log_setup

from cogs.quiz.area_providers.wcr import WCRQuestionProvider
from cogs.quiz.utils import create_permutations_list


class DummyBot:
    def __init__(self, units, locals_, templates):
        self.data = {
            "wcr": {"units": units, "locals": locals_},
            "quiz": {"templates": {"wcr": templates}},
        }


def test_generate_type_1(monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    units = [{"id": 1}]
    locals_ = {
        "de": {"units": [{"id": 1, "name": "Einheit", "talents": [{"name": "Talent"}]}]}
    }
    templates = {"de": {"type_1": "Wer hat {talent_name}?"}}
    bot = DummyBot(units, locals_, templates)
    provider = WCRQuestionProvider(bot, language="de")
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_1()

    assert q["frage"] == "Wer hat Talent?"
    assert set(q["antwort"]) == set(create_permutations_list(["Einheit"]))
    assert q["category"] == "Mechanik"
    assert isinstance(q["id"], int)

    provider.units = []
    assert provider.generate_type_1() is None


def test_generate_type_2(monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    units = [{"id": 1}, {"id": 2}]
    locals_ = {
        "de": {
            "units": [
                {
                    "id": 1,
                    "name": "U1",
                    "talents": [{"name": "T1", "description": "desc"}],
                },
                {
                    "id": 2,
                    "name": "U2",
                    "talents": [{"name": "T2", "description": "desc"}],
                },
            ]
        }
    }
    templates = {"de": {"type_2": "{talent_description}?"}}
    bot = DummyBot(units, locals_, templates)
    provider = WCRQuestionProvider(bot, language="de")
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_2()

    expected_answers = create_permutations_list(["T1", "T2"])
    assert "desc" in q["frage"]
    assert set(q["antwort"]) == set(expected_answers)
    assert isinstance(q["id"], int)

    provider.locals["de"]["units"] = []
    assert provider.generate_type_2() is None


def test_generate_type_3(monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    units = [{"id": 1, "faction_id": 1}]
    locals_ = {
        "de": {
            "units": [{"id": 1, "name": "U1"}],
            "categories": {"factions": [{"id": 1, "name": "Faction"}]},
        }
    }
    templates = {"de": {"type_3": "Fraktion von {unit_name}?"}}
    bot = DummyBot(units, locals_, templates)
    provider = WCRQuestionProvider(bot, language="de")
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_3()

    assert "U1" in q["frage"]
    assert set(q["antwort"]) == set(create_permutations_list(["Faction"]))
    assert q["category"] == "Franchise"

    provider.units = []
    assert provider.generate_type_3() is None


def test_generate_type_4(monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    units = [{"id": 1, "cost": 5}]
    locals_ = {
        "de": {
            "units": [{"id": 1, "name": "U1"}],
        }
    }
    templates = {"de": {"type_4": "Kosten von {unit_name}?"}}
    bot = DummyBot(units, locals_, templates)
    provider = WCRQuestionProvider(bot, language="de")
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_4()

    assert "U1" in q["frage"]
    assert set(q["antwort"]) == set(create_permutations_list(["5"]))
    assert q["category"] == "Mechanik"

    provider.units = []
    assert provider.generate_type_4() is None


def test_generate_type_5(monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    units = [
        {"id": 1, "stats": {"health": 100}},
        {"id": 2, "stats": {"health": 50}},
    ]
    locals_ = {
        "de": {
            "units": [{"id": 1, "name": "U1"}, {"id": 2, "name": "U2"}],
        }
    }
    templates = {"de": {"type_5": "Wer hat mehr {stat_label}, {unit1} oder {unit2}?"}}
    bot = DummyBot(units, locals_, templates)
    provider = WCRQuestionProvider(bot, language="de")
    monkeypatch.setattr(random, "choice", lambda seq: "health")
    monkeypatch.setattr(random, "sample", lambda seq, k: seq[:k])

    q = provider.generate_type_5()

    assert "health" in q["frage"]
    assert set(q["antwort"]) == set(create_permutations_list(["U1"]))
    assert q["category"] == "Mechanik"

    provider.units = [{"id": 1, "stats": {"health": 100}}]
    assert provider.generate_type_5() is None
