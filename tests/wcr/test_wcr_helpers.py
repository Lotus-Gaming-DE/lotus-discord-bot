import json
import pytest


from cogs.wcr import helpers


@pytest.fixture(scope="module")
def languages():
    from cogs.wcr.utils import load_languages

    return load_languages()


@pytest.fixture(scope="module")
def categories():
    from cogs.wcr.utils import load_categories

    return load_categories()


@pytest.fixture(scope="module")
def lang_lookup(categories):
    """Erzeuge die Kategorie-Lookup-Tabelle für die Tests."""
    return helpers.build_category_lookup(categories)


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


def test_get_category_name_known(lang_lookup):
    name = helpers.get_category_name("factions", 1, "de", lang_lookup)
    assert name == "Untote"


def test_get_category_name_unknown(lang_lookup):
    name = helpers.get_category_name("factions", 9999, "de", lang_lookup)
    assert name == "Unbekannt"


def test_get_faction_data_known(lang_lookup):
    data = helpers.get_faction_data(1, lang_lookup)
    assert data["icon"] == "wcr_undead"


def test_get_faction_data_unknown(lang_lookup):
    assert helpers.get_faction_data(9999, lang_lookup) == {}


def test_get_faction_icon_known(lang_lookup):
    assert helpers.get_faction_icon(1, lang_lookup) == "wcr_undead"


def test_get_faction_icon_unknown(lang_lookup):
    assert helpers.get_faction_icon(9999, lang_lookup) == ""


def test_find_category_id_in_current_lang(lang_lookup):
    cid = helpers.find_category_id("Untote", "factions", "de", lang_lookup)
    assert cid == 1


def test_find_category_id_in_other_lang(lang_lookup):
    cid = helpers.find_category_id("Alliance", "factions", "de", lang_lookup)
    assert cid == 3


def test_find_category_id_case_insensitive(lang_lookup):
    cid = helpers.find_category_id("untote", "factions", "de", lang_lookup)
    assert cid == 1


def test_find_category_id_unknown(lang_lookup):
    cid = helpers.find_category_id("Foobar", "factions", "de", lang_lookup)
    assert cid is None


def test_normalize_name():
    tokens = helpers.normalize_name("Fresh Meat!")
    assert tokens == ["fresh", "meat"]
