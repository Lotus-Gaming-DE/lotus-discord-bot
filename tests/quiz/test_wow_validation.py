import copy

import pytest

from lotus_bot.bot import load_wow_data
from lotus_bot.cogs.quiz.area_providers.wow_validation import (
    assert_valid_wow_data,
    validate_wow_data,
)


def test_current_wow_data_is_valid():
    data = load_wow_data("data/wow/classic_hc")

    assert validate_wow_data(data) == []


def test_rejects_duplicate_ids():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    data["items"].append(copy.deepcopy(data["items"][0]))

    errors = validate_wow_data(data)

    assert any("duplicate id" in str(error) for error in errors)


def test_rejects_missing_required_field():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    spell_id = data["spells"][0]["id"]
    data["spells"][0].pop("source_urls")

    errors = validate_wow_data(data)

    assert any(f"spells:{spell_id}: missing source_urls" == str(error) for error in errors)


def test_rejects_unknown_references():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    data["talents"][0]["spell_id"] = "spell.missing"

    errors = validate_wow_data(data)

    assert any("spell_id references unknown spells id 'spell.missing'" in str(error) for error in errors)


def test_rejects_incomplete_localized_fields():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    data["items"][0]["name"].pop("de")

    errors = validate_wow_data(data)

    assert any("name.de must be a non-empty string" in str(error) for error in errors)


def test_rejects_hardcore_quiz_drop_for_quest_item():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    drop_item_id = next(
        drop["item_id"]
        for drop in data["instance_drops"]
        if drop["include_in_hardcore_quiz"]
    )
    for item in data["items"]:
        if item["id"] == drop_item_id:
            item["is_quest_item"] = True
            break

    errors = validate_wow_data(data)

    assert any("quiz drop item is a quest item" in str(error) for error in errors)


def test_rejects_hardcore_enabled_battleground():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    battleground = next(zone for zone in data["zones"] if zone["type"] == "battleground")
    battleground["hardcore_enabled"] = True

    errors = validate_wow_data(data)

    assert any("battleground cannot be hardcore_enabled" in str(error) for error in errors)


def test_assert_valid_wow_data_raises_readable_error():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    data["race_classes"][0]["class_id"] = "bard"

    with pytest.raises(ValueError, match="Invalid WoW Classic HC data"):
        assert_valid_wow_data(data)


def test_rejects_talent_tree_class_mismatch():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    data["talents"][0]["class_id"] = "mage"

    errors = validate_wow_data(data)

    assert any("tree class does not match talent class" in str(error) for error in errors)


def test_rejects_ability_with_non_ability_spell():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    talent_spell_id = data["talents"][0]["spell_id"]
    data["abilities"][0]["spell_id"] = talent_spell_id

    errors = validate_wow_data(data)

    assert any("spell is not a class ability" in str(error) for error in errors)
