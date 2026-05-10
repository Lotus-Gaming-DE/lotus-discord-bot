from lotus_bot.cogs.quiz.area_providers.wow_audit import (
    apply_wow_qa,
    audit_wow_data,
    has_fallback_description,
    has_quality_flag,
)


def test_audit_detects_fallback_spell_description():
    data = {
        "spells": [
            {
                "id": "spell.foo",
                "name": {"de": "Präzision", "en": "Precision"},
                "description": {"de": "Präzision", "en": "Increases hit chance."},
            }
        ]
    }

    report = audit_wow_data(data)

    assert report["summary"]["spells"]["fallback_description"] == 1
    assert has_fallback_description(data["spells"][0])


def test_audit_detects_drops_without_source_name():
    data = {
        "instance_drops": [
            {"id": "drop.unknown", "source_name": {"de": "", "en": ""}}
        ]
    }

    report = audit_wow_data(data)

    assert report["summary"]["instance_drops"]["missing_source_name"] == 1


def test_audit_detects_miscellaneous_item_types():
    data = {
        "items": [
            {
                "id": "item.misc",
                "item_class": "miscellaneous",
                "item_subclass": "miscellaneous",
            }
        ]
    }

    report = audit_wow_data(data)

    assert report["summary"]["items"]["miscellaneous_item_class"] == 1
    assert report["summary"]["items"]["miscellaneous_item_subclass"] == 1


def test_audit_detects_hc_zones_without_level_range():
    data = {
        "zones": [
            {"id": "zone.city", "hardcore_enabled": True, "level_range": ""}
        ]
    }

    report = audit_wow_data(data)

    assert report["summary"]["zones"]["missing_level_range"] == 1


def test_audit_detects_uncertain_recipe_source():
    data = {
        "profession_recipes": [
            {"id": "recipe.unknown", "learned_from": "unknown"}
        ]
    }

    report = audit_wow_data(data)

    assert report["summary"]["profession_recipes"]["learned_from_uncertain"] == 1


def test_apply_wow_qa_marks_data_without_deleting_records():
    data = {
        "spells": [
            {
                "id": "spell.foo",
                "name": {"de": "Präzision", "en": "Precision"},
                "description": {"de": "Präzision", "en": "Precision"},
            }
        ],
        "items": [
            {
                "id": "item.misc",
                "item_class": "miscellaneous",
                "item_subclass": "miscellaneous",
            }
        ],
    }

    updated, report = apply_wow_qa(data)

    assert len(updated["spells"]) == 1
    assert updated["spells"][0]["quiz_eligible"] is False
    assert has_quality_flag(updated["spells"][0], "fallback_description")
    assert has_quality_flag(updated["items"][0], "miscellaneous_item_subclass")
    assert report["summary"]["spells"]["fallback_description"] == 1
