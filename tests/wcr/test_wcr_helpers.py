import json
import pytest


from cogs.wcr import helpers


@pytest.fixture(scope="module")
def languages():
    from cogs.wcr.utils import load_languages

    return load_languages()


@pytest.fixture(scope="module")
def pictures():
    return json.load(open("data/wcr/pictures.json", "r", encoding="utf-8"))


def test_get_text_data_known(languages):
    name, desc, talents = helpers.get_text_data(1, "de", languages)
    assert name == "Abscheulichkeit"
    assert "Fleisch-und-Stahl" in desc
    assert isinstance(talents, list) and len(talents) == 3


def test_get_text_data_unknown(languages):
    name, desc, talents = helpers.get_text_data(9999, "de", languages)
    assert name == "Unbekannt"
    assert desc == "Beschreibung fehlt"
    assert talents == []


def test_get_pose_url_known(pictures):
    url = helpers.get_pose_url(1, pictures)
    assert url.startswith("https://")
    assert "Abomination" in url


def test_get_pose_url_unknown(pictures):
    assert helpers.get_pose_url(9999, pictures) == ""


def test_get_category_name_known(languages):
    name = helpers.get_category_name("factions", 1, "de", languages)
    assert name == "Untote"


def test_get_category_name_unknown(languages):
    name = helpers.get_category_name("factions", 9999, "de", languages)
    assert name == "Unbekannt"


def test_get_faction_data_known(pictures):
    data = helpers.get_faction_data(1, pictures)
    assert data["icon"] == "wcr_undead"


def test_get_faction_data_unknown(pictures):
    assert helpers.get_faction_data(9999, pictures) == {}


def test_get_faction_icon_known(pictures):
    assert helpers.get_faction_icon(1, pictures) == "wcr_undead"


def test_get_faction_icon_unknown(pictures):
    assert helpers.get_faction_icon(9999, pictures) == ""


def test_find_category_id_in_current_lang(languages):
    cid = helpers.find_category_id("Untote", "factions", "de", languages)
    assert cid == 1


def test_find_category_id_in_other_lang(languages):
    cid = helpers.find_category_id("Alliance", "factions", "de", languages)
    assert cid == 3


def test_find_category_id_case_insensitive(languages):
    cid = helpers.find_category_id("untote", "factions", "de", languages)
    assert cid == 1


def test_find_category_id_unknown(languages):
    cid = helpers.find_category_id("Foobar", "factions", "de", languages)
    assert cid is None


def test_normalize_name():
    tokens = helpers.normalize_name("Fresh Meat!")
    assert tokens == ["fresh", "meat"]
