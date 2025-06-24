import pytest


from cogs.wcr import helpers


@pytest.fixture
def languages(wcr_data):
    return wcr_data["locals"]


@pytest.fixture
def categories(wcr_data):
    return wcr_data["categories"]


@pytest.fixture
def lang_lookup(categories):
    """Erzeuge die Kategorie-Lookup-Tabelle für die Tests."""
    return helpers.build_category_lookup(categories)


def test_get_text_data_known(languages):
    name, desc, talents = helpers.get_text_data("1", "de", languages)
    assert name == "Abscheulichkeit"
    assert "Fleisch-und-Stahl" in desc
    assert isinstance(talents, list) and len(talents) == 3


def test_get_text_data_unknown(languages):
    name, desc, talents = helpers.get_text_data("9999", "de", languages)
    assert name == "Unbekannt"
    assert desc == "Beschreibung fehlt"
    assert talents == []


def test_get_text_data_fallback_to_en(languages):
    en_data = languages["en"]
    del languages["de"]
    name, desc, _ = helpers.get_text_data("1", "de", languages)
    assert name == en_data["units"][0]["name"]
    assert desc == en_data["units"][0]["description"]


def test_get_pose_url_known(wcr_data):
    unit = wcr_data["units"][0]
    url = helpers.get_pose_url(unit)
    assert url.startswith("https://")
    assert "Abomination" in url


def test_get_pose_url_unknown():
    assert helpers.get_pose_url({}) == ""


def test_get_pose_url_relative_default_base(wcr_data, monkeypatch):
    unit = wcr_data["units"][0]
    unit["image"] = "images/test.webp"
    monkeypatch.delenv("WCR_IMAGE_BASE", raising=False)
    url = helpers.get_pose_url(unit)
    assert url == "https://www.method.gg/images/test.webp"


def test_get_pose_url_relative_custom_base(wcr_data, monkeypatch):
    unit = wcr_data["units"][0]
    unit["image"] = "/img/foobar.webp"
    monkeypatch.setenv("WCR_IMAGE_BASE", "https://cdn.example.com")
    url = helpers.get_pose_url(unit)
    assert url == "https://cdn.example.com/img/foobar.webp"


def test_get_category_name_known(lang_lookup):
    name = helpers.get_category_name("factions", 1, "de", lang_lookup)
    assert name == "Untote"


def test_get_category_name_unknown(lang_lookup):
    name = helpers.get_category_name("factions", 9999, "de", lang_lookup)
    assert name == "Unbekannt"


def test_get_category_name_fallback_to_en(categories):
    for item in categories["factions"]:
        item["names"].pop("de", None)
    lang_lookup = helpers.build_category_lookup(categories)
    name = helpers.get_category_name("factions", 1, "de", lang_lookup)
    assert name == "Undead"


def test_get_faction_data_known(lang_lookup):
    data = helpers.get_faction_data("1", lang_lookup)
    assert data.get("icon") in {"wcr_undead", None}


def test_get_faction_data_unknown(lang_lookup):
    assert helpers.get_faction_data(9999, lang_lookup) == {}


def test_get_faction_icon_known(lang_lookup):
    icon = helpers.get_faction_icon("1", lang_lookup)
    assert icon in {"wcr_undead", ""}


def test_get_faction_icon_unknown(lang_lookup):
    assert helpers.get_faction_icon(9999, lang_lookup) == ""


def test_find_category_id_in_current_lang(lang_lookup):
    cid = helpers.find_category_id("Untote", "factions", "de", lang_lookup)
    assert cid == "1"


def test_find_category_id_in_other_lang(lang_lookup):
    cid = helpers.find_category_id("Alliance", "factions", "de", lang_lookup)
    assert cid == "3"


def test_find_category_id_case_insensitive(lang_lookup):
    cid = helpers.find_category_id("untote", "factions", "de", lang_lookup)
    assert cid == "1"


def test_find_category_id_unknown(lang_lookup):
    cid = helpers.find_category_id("Foobar", "factions", "de", lang_lookup)
    assert cid is None


def test_normalize_name():
    tokens = helpers.normalize_name("Fresh Meat!")
    assert tokens == ["fresh", "meat"]
