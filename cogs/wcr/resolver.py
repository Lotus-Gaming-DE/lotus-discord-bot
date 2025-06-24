# cogs/wcr/resolver.py
"""Hilfsfunktionen zur Namensauflösung für Warcraft Rumble Minis."""

from __future__ import annotations

import difflib
from typing import Any, Dict, Tuple, Set

from log_setup import get_logger
from . import helpers

logger = get_logger(__name__)


def build_lookup_tables(languages: Dict[str, Any]) -> Tuple[
    Dict[str, Dict[str, str]],
    Dict[str, Dict[str, str]],
    Dict[str, Dict[str, Set[str]]],
]:
    """Erzeuge Lookup-Tabellen für alle verfügbaren Sprachen."""

    unit_name_map: Dict[str, Dict[str, str]] = {}
    id_name_map: Dict[str, Dict[str, str]] = {}
    name_token_index: Dict[str, Dict[str, Set[str]]] = {}

    for lang, texts in languages.items():
        name_map: Dict[str, str] = {}
        id_map: Dict[str, str] = {}
        token_index: Dict[str, Set[str]] = {}
        for unit in texts.get("units", []):
            normalized = " ".join(helpers.normalize_name(unit.get("name", "")))
            unit_id = str(unit.get("id"))
            name_map[normalized] = unit_id
            id_map[unit_id] = normalized
            for token in normalized.split():
                token_index.setdefault(token, set()).add(unit_id)
        unit_name_map[lang] = name_map
        id_name_map[lang] = id_map
        name_token_index[lang] = token_index

    return unit_name_map, id_name_map, name_token_index


def find_unit_id_by_name(
    normalized: str,
    lang: str,
    unit_name_map: Dict[str, Dict[str, str]],
    id_name_map: Dict[str, Dict[str, str]],
    name_token_index: Dict[str, Dict[str, Set[str]]],
) -> Tuple[str | None, str]:
    """Sucht die ID eines Minis per fuzzy match."""

    mapping = unit_name_map.get(lang, {})
    id_map = id_name_map.get(lang, {})
    token_index = name_token_index.get(lang, {})

    if normalized in mapping:
        return mapping[normalized], lang

    tokens = normalized.split()
    candidate_ids: Set[str] = set()
    for token in tokens:
        candidate_ids.update(token_index.get(token, set()))

    if not candidate_ids:
        candidate_ids = set(mapping.values())

    for unit_id in candidate_ids:
        key = id_map.get(unit_id, "")
        if normalized in key:
            return unit_id, lang

    best_id = None
    best_ratio = 0.0
    for unit_id in candidate_ids:
        key = id_map.get(unit_id, "")
        ratio = difflib.SequenceMatcher(None, normalized, key).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = unit_id
    if best_ratio >= 0.6:
        return best_id, lang
    return None, lang
