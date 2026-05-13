from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import json
from typing import Any

from .wow_validation import assert_valid_wow_data

QA_TABLES = {
    "spells",
    "items",
    "instance_drops",
    "zones",
    "profession_recipes",
}

VALID_LEARNED_FROM = {"trainer", "recipe"}


def audit_wow_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return a compact QA report for normalized WoW Classic HC data."""

    findings: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    def add(table: str, flag: str, record_id: str) -> None:
        findings[table][flag] += 1
        if len(examples[table][flag]) < 10:
            examples[table][flag].append(record_id)

    for spell in _records(data, "spells"):
        if has_fallback_description(spell):
            add("spells", "fallback_description", str(spell.get("id") or ""))

    for drop in _records(data, "instance_drops"):
        if not _localized_text(drop.get("source_name")):
            add("instance_drops", "missing_source_name", str(drop.get("id") or ""))

    for item in _records(data, "items"):
        if _is_miscellaneous(item.get("item_class")):
            add("items", "miscellaneous_item_class", str(item.get("id") or ""))
        if _is_miscellaneous(item.get("item_subclass")):
            add("items", "miscellaneous_item_subclass", str(item.get("id") or ""))

    for zone in _records(data, "zones"):
        if zone.get("hardcore_enabled") and not zone.get("level_range"):
            add("zones", "missing_level_range", str(zone.get("id") or ""))

    for recipe in _records(data, "profession_recipes"):
        learned_from = recipe.get("learned_from")
        if learned_from not in VALID_LEARNED_FROM:
            add(
                "profession_recipes",
                "learned_from_uncertain",
                str(recipe.get("id") or ""),
            )

    return {
        "summary": {
            table: dict(flags) for table, flags in sorted(findings.items()) if flags
        },
        "examples": {
            table: dict(flags) for table, flags in sorted(examples.items()) if flags
        },
    }


def apply_wow_qa(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a deep-copied data set with conservative QA metadata applied."""

    updated = deepcopy(data)

    for spell in _records(updated, "spells"):
        if has_fallback_description(spell):
            _mark(
                spell,
                "fallback_description",
                quality="partial",
                quiz_eligible=False,
            )

    for drop in _records(updated, "instance_drops"):
        if not _localized_text(drop.get("source_name")):
            _mark(drop, "missing_source_name", quality="partial")

    for item in _records(updated, "items"):
        if _is_miscellaneous(item.get("item_class")):
            _mark(item, "miscellaneous_item_class", quality="partial")
        if _is_miscellaneous(item.get("item_subclass")):
            _mark(item, "miscellaneous_item_subclass", quality="partial")

    for zone in _records(updated, "zones"):
        if zone.get("hardcore_enabled") and not zone.get("level_range"):
            _mark(zone, "missing_level_range", quality="partial")

    for recipe in _records(updated, "profession_recipes"):
        if recipe.get("learned_from") not in VALID_LEARNED_FROM:
            _mark(recipe, "learned_from_uncertain", quality="partial")

    return updated, audit_wow_data(updated)


def write_wow_qa_data(base_path: str | Path, data: dict[str, Any]) -> None:
    """Write QA-managed tables and validate the resulting data set."""

    assert_valid_wow_data(data)
    base = Path(base_path)
    for table in sorted(QA_TABLES):
        records = data.get(table)
        if records is None:
            continue
        target = base / f"{table}.json"
        target.write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def has_fallback_description(record: dict[str, Any]) -> bool:
    """Return whether a spell description is only a name fallback."""

    name = record.get("name")
    description = record.get("description")
    if not isinstance(name, dict) or not isinstance(description, dict):
        return False

    for language, desc in description.items():
        if not isinstance(desc, str) or not desc.strip():
            continue
        localized_name = name.get(language)
        if isinstance(localized_name, str) and _norm(desc) == _norm(localized_name):
            return True
    return False


def has_quality_flag(record: dict[str, Any], flag: str) -> bool:
    flags = record.get("qa_flags")
    return isinstance(flags, list) and flag in flags


def _records(data: dict[str, Any], table: str) -> list[dict[str, Any]]:
    records = data.get(table, [])
    return [record for record in records if isinstance(record, dict)]


def _mark(
    record: dict[str, Any],
    flag: str,
    *,
    quality: str = "imported",
    quiz_eligible: bool | None = None,
) -> None:
    flags = record.setdefault("qa_flags", [])
    if flag not in flags:
        flags.append(flag)
        flags.sort()
    record["data_quality"] = quality
    if quiz_eligible is not None:
        record["quiz_eligible"] = quiz_eligible


def _localized_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for language in ("de", "en"):
            text = value.get(language)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def _is_miscellaneous(value: Any) -> bool:
    return isinstance(value, str) and value.lower() == "miscellaneous"


def _norm(value: str) -> str:
    return " ".join(value.casefold().split())
