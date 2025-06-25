import json
import random
from pathlib import Path

import lotus_bot.log_setup as log_setup

from lotus_bot.cogs.quiz.area_providers.wcr import WCRQuestionProvider
from lotus_bot.cogs.quiz.utils import create_permutations_list


def create_bot(wcr_data):
    with open(Path("data/quiz/templates/wcr.json"), "r", encoding="utf-8") as f:
        templates = json.load(f)
    return DummyBot(templates, wcr_data)


def create_provider(wcr_data):
    bot = create_bot(wcr_data)
    return bot, WCRQuestionProvider(bot, language="de")


class DummyBot:
    def __init__(self, templates, wcr_data):
        self.data = {
            "wcr": wcr_data,
            "quiz": {"templates": {"wcr": templates}},
        }


def test_generate_type_1(wcr_data, monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    bot, provider = create_provider(wcr_data)
    first_unit = provider.locals["de"]["units"][0]
    first_talent = first_unit["talents"][0]
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_1()

    template = provider.templates["de"]["type_1"]
    expected_question = template.format(talent_name=first_talent["name"])
    expected_answers = create_permutations_list([first_unit["name"]])

    assert q["frage"] == expected_question
    assert set(q["antwort"]) == set(expected_answers)
    assert q["category"] == "Mechanik"
    assert isinstance(q["id"], int)

    provider.units = []
    assert provider.generate_type_1() is None


def test_generate_type_2(wcr_data, monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    bot, provider = create_provider(wcr_data)
    first_talent = provider.locals["de"]["units"][0]["talents"][0]
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_2()

    template = provider.templates["de"]["type_2"]
    expected_question = template.format(talent_description=first_talent["description"])
    expected_answers = create_permutations_list([first_talent["name"]])

    assert q["frage"] == expected_question
    assert set(q["antwort"]) == set(expected_answers)
    assert isinstance(q["id"], int)

    provider.locals = {}
    assert provider.generate_type_2() is None


def test_generate_type_3(wcr_data, monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    bot, provider = create_provider(wcr_data)
    first_unit = provider.units[0]
    first_unit_name = provider.locals["de"]["units"][0]["name"]
    faction_lookup = provider.lang_category_lookup["de"]["factions"]
    faction_name = faction_lookup[first_unit["faction_id"]]["name"]
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_3()

    template = provider.templates["de"]["type_3"]
    expected_question = template.format(unit_name=first_unit_name)
    expected_answers = create_permutations_list([faction_name])

    assert q["frage"] == expected_question
    assert set(q["antwort"]) == set(expected_answers)
    assert q["category"] == "Franchise"

    provider.units = []
    assert provider.generate_type_3() is None


def test_generate_type_4(wcr_data, monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    bot, provider = create_provider(wcr_data)
    first_unit = provider.units[0]
    first_unit_name = provider.locals["de"]["units"][0]["name"]
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    q = provider.generate_type_4()

    template = provider.templates["de"]["type_4"]
    expected_question = template.format(unit_name=first_unit_name)
    expected_answers = create_permutations_list([str(first_unit["cost"])])

    assert q["frage"] == expected_question
    assert set(q["antwort"]) == set(expected_answers)
    assert q["category"] == "Mechanik"

    provider.units = []
    assert provider.generate_type_4() is None


def test_generate_type_5(wcr_data, monkeypatch, patch_logged_task):
    patch_logged_task(log_setup)
    bot, provider = create_provider(wcr_data)
    monkeypatch.setattr(random, "choice", lambda seq: "health")
    monkeypatch.setattr(random, "sample", lambda seq, k: seq[:k])

    q = provider.generate_type_5()

    unit_names = [provider.locals["de"]["units"][i]["name"] for i in range(2)]
    expected_answers = create_permutations_list([unit_names[0]])

    assert "health" in q["frage"]
    assert set(q["antwort"]) == set(expected_answers)
    assert q["category"] == "Mechanik"

    provider.units = [provider.units[0]]
    assert provider.generate_type_5() is None
