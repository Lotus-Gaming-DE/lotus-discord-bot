from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


LANGUAGES = ("de", "en")

REQUIRED_TABLES = {
    "abilities",
    "classes",
    "continents",
    "dungeons",
    "factions",
    "instance_drops",
    "items",
    "power_types",
    "profession_recipes",
    "professions",
    "race_classes",
    "races",
    "racial_traits",
    "spell_categories",
    "spells",
    "talent_trees",
    "talents",
    "zones",
}

REQUIRED_FIELDS = {
    "abilities": {"id", "spell_id", "class_id", "hardcore_valid"},
    "classes": {"id", "blizzard_id", "name", "power_type_id"},
    "continents": {"id", "name"},
    "dungeons": {
        "id",
        "zone_id",
        "wowhead_id",
        "type",
        "name",
        "level_range",
        "player_count",
        "hardcore_enabled",
        "source_urls",
    },
    "factions": {"id", "name"},
    "instance_drops": {
        "id",
        "instance_id",
        "item_id",
        "source_name",
        "mode",
        "season",
        "include_in_hardcore_quiz",
    },
    "items": {
        "id",
        "wowhead_id",
        "name",
        "item_class",
        "item_subclass",
        "quality",
        "is_quest_item",
        "source_urls",
    },
    "power_types": {"id", "name"},
    "profession_recipes": {
        "id",
        "profession_id",
        "spell_id",
        "creates_item_id",
        "required_skill",
        "learned_from",
        "hardcore_valid",
    },
    "professions": {"id", "name", "type"},
    "race_classes": {"id", "race_id", "class_id"},
    "races": {"id", "blizzard_id", "faction_id", "name"},
    "racial_traits": {"id", "race_id", "spell_id", "hardcore_valid"},
    "spell_categories": {"id", "name"},
    "spells": {"id", "wowhead_id", "category_id", "name", "description", "source_urls"},
    "talent_trees": {"id", "class_id", "name"},
    "talents": {"id", "spell_id", "class_id", "tree_id", "hardcore_valid"},
    "zones": {"id", "wowhead_id", "name", "type", "hardcore_enabled", "source_urls"},
}

LOCALIZED_FIELDS = {
    "classes": {"name"},
    "continents": {"name"},
    "dungeons": {"name"},
    "factions": {"name"},
    "items": {"name"},
    "power_types": {"name"},
    "professions": {"name"},
    "races": {"name"},
    "spell_categories": {"name"},
    "spells": {"name", "description"},
    "talent_trees": {"name"},
    "zones": {"name"},
}

REFERENCE_FIELDS = {
    "abilities": {"spell_id": "spells", "class_id": "classes"},
    "classes": {"power_type_id": "power_types"},
    "dungeons": {"location_zone_id": "zones", "territory_id": "factions"},
    "instance_drops": {"instance_id": "dungeons", "item_id": "items"},
    "profession_recipes": {
        "profession_id": "professions",
        "spell_id": "spells",
        "creates_item_id": "items",
    },
    "professions": {"spell_id": "spells"},
    "race_classes": {"race_id": "races", "class_id": "classes"},
    "races": {"faction_id": "factions"},
    "racial_traits": {"race_id": "races", "spell_id": "spells"},
    "spells": {"category_id": "spell_categories"},
    "talent_trees": {"class_id": "classes"},
    "talents": {"spell_id": "spells", "class_id": "classes", "tree_id": "talent_trees"},
    "zones": {"continent_id": "continents", "territory_id": "factions"},
}


@dataclass(frozen=True)
class WoWValidationError:
    table: str
    record_id: str
    message: str

    def __str__(self) -> str:
        location = self.table if not self.record_id else f"{self.table}:{self.record_id}"
        return f"{location}: {self.message}"


def validate_wow_data(data: Mapping[str, Any]) -> list[WoWValidationError]:
    errors: list[WoWValidationError] = []
    ids_by_table: dict[str, set[str]] = {}

    for table in sorted(REQUIRED_TABLES):
        records = data.get(table)
        if records is None:
            errors.append(WoWValidationError(table, "", "missing table"))
            continue
        if not isinstance(records, list):
            errors.append(WoWValidationError(table, "", "table must be a JSON list"))
            continue
        ids_by_table[table] = _validate_records(table, records, errors)

    for table, references in REFERENCE_FIELDS.items():
        records = data.get(table, [])
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            record_id = str(record.get("id") or "")
            for field, target_table in references.items():
                value = record.get(field)
                if value in (None, ""):
                    continue
                if value not in ids_by_table.get(target_table, set()):
                    errors.append(
                        WoWValidationError(
                            table,
                            record_id,
                            f"{field} references unknown {target_table} id '{value}'",
                        )
                    )

    _validate_quiz_filters(data, errors)
    _validate_semantic_consistency(data, errors)
    return errors


def assert_valid_wow_data(data: Mapping[str, Any]) -> None:
    errors = validate_wow_data(data)
    if errors:
        detail = "\n".join(str(error) for error in errors)
        raise ValueError(f"Invalid WoW Classic HC data:\n{detail}")


def _validate_records(
    table: str,
    records: Sequence[Any],
    errors: list[WoWValidationError],
) -> set[str]:
    ids: set[str] = set()
    required = REQUIRED_FIELDS[table]

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(WoWValidationError(table, str(index), "record must be an object"))
            continue

        record_id = str(record.get("id") or "")
        if not record_id:
            errors.append(WoWValidationError(table, str(index), "missing id"))
        elif record_id in ids:
            errors.append(WoWValidationError(table, record_id, "duplicate id"))
        else:
            ids.add(record_id)

        for field in sorted(required):
            if field not in record:
                errors.append(WoWValidationError(table, record_id, f"missing {field}"))

        for field in LOCALIZED_FIELDS.get(table, set()):
            if field in record:
                _validate_localized_field(table, record_id, field, record[field], errors)

        if "source_urls" in record:
            _validate_localized_field(
                table, record_id, "source_urls", record["source_urls"], errors
            )

    return ids


def _validate_localized_field(
    table: str,
    record_id: str,
    field: str,
    value: Any,
    errors: list[WoWValidationError],
) -> None:
    if not isinstance(value, dict):
        errors.append(WoWValidationError(table, record_id, f"{field} must be localized"))
        return

    for language in LANGUAGES:
        text = value.get(language)
        if not isinstance(text, str) or not text.strip():
            errors.append(
                WoWValidationError(
                    table,
                    record_id,
                    f"{field}.{language} must be a non-empty string",
                )
            )


def _validate_quiz_filters(
    data: Mapping[str, Any],
    errors: list[WoWValidationError],
) -> None:
    items = {
        record.get("id"): record
        for record in data.get("items", [])
        if isinstance(record, dict)
    }

    for drop in data.get("instance_drops", []):
        if not isinstance(drop, dict) or not drop.get("include_in_hardcore_quiz"):
            continue
        record_id = str(drop.get("id") or "")
        if drop.get("season") != "classic_era":
            errors.append(WoWValidationError("instance_drops", record_id, "quiz drop is not classic_era"))
        if drop.get("mode") != "normal":
            errors.append(WoWValidationError("instance_drops", record_id, "quiz drop is not normal mode"))
        item = items.get(drop.get("item_id"))
        if item and item.get("is_quest_item"):
            errors.append(WoWValidationError("instance_drops", record_id, "quiz drop item is a quest item"))

    for zone in data.get("zones", []):
        if not isinstance(zone, dict):
            continue
        record_id = str(zone.get("id") or "")
        if zone.get("type") == "battleground" and zone.get("hardcore_enabled"):
            errors.append(WoWValidationError("zones", record_id, "battleground cannot be hardcore_enabled"))


def _validate_semantic_consistency(
    data: Mapping[str, Any],
    errors: list[WoWValidationError],
) -> None:
    spells = {
        record.get("id"): record
        for record in data.get("spells", [])
        if isinstance(record, dict)
    }
    trees = {
        record.get("id"): record
        for record in data.get("talent_trees", [])
        if isinstance(record, dict)
    }

    for talent in data.get("talents", []):
        if not isinstance(talent, dict):
            continue
        record_id = str(talent.get("id") or "")
        tree = trees.get(talent.get("tree_id"))
        if tree and tree.get("class_id") != talent.get("class_id"):
            errors.append(WoWValidationError("talents", record_id, "tree class does not match talent class"))
        spell = spells.get(talent.get("spell_id"))
        if spell and spell.get("category_id") != "talent":
            errors.append(WoWValidationError("talents", record_id, "spell is not a talent"))

    for ability in data.get("abilities", []):
        if not isinstance(ability, dict):
            continue
        spell = spells.get(ability.get("spell_id"))
        if spell and spell.get("category_id") != "class_ability":
            errors.append(WoWValidationError("abilities", str(ability.get("id") or ""), "spell is not a class ability"))

    for trait in data.get("racial_traits", []):
        if not isinstance(trait, dict):
            continue
        spell = spells.get(trait.get("spell_id"))
        if spell and spell.get("category_id") != "racial_trait":
            errors.append(WoWValidationError("racial_traits", str(trait.get("id") or ""), "spell is not a racial trait"))
