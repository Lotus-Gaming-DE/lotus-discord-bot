# cogs/wcr/helpers.py
import os
import itertools
import logging

logger = logging.getLogger(__name__)


def get_text_data(unit_id, lang, languages):
    texts = languages.get(lang, languages.get("de", {}))
    unit_text = next(
        (unit for unit in texts.get("units", []) if unit["id"] == unit_id), {})
    return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt"), unit_text.get("talents", [])


def get_pose_url(unit_id, pictures):
    unit_pictures = pictures.get("units", [])
    unit_picture = next(
        (pic for pic in unit_pictures if pic["id"] == unit_id), {})
    return unit_picture.get("pose", "")


def get_faction_data(faction_id, pictures):
    factions = pictures.get("categories", {}).get("factions", [])
    faction_data = next(
        (faction for faction in factions if faction["id"] == faction_id), {})
    return faction_data


def get_category_name(category, category_id, lang, languages):
    categories = languages.get(
        lang, {}).get("categories", {}).get(category, [])
    category_item = next(
        (item for item in categories if item["id"] == category_id), {})
    return category_item.get("name", "Unbekannt")


def get_faction_icon(faction_id, pictures):
    faction_data = get_faction_data(faction_id, pictures)
    return faction_data.get("icon", "")


def normalize_name(name):
    return ''.join(c for c in name if c.isalnum() or c.isspace()).lower().split()


def find_category_id(category_name, category, lang, languages):
    # Zuerst in der aktuellen Sprache suchen
    category_list = languages[lang]['categories'][category]
    matching_item = next(
        (item for item in category_list if item['name'].lower() == category_name.lower()), None)
    if matching_item:
        return matching_item['id']

    # In anderen Sprachen suchen
    for other_lang, other_texts in languages.items():
        if other_lang == lang:
            continue
        category_list = other_texts['categories'][category]
        matching_item = next(
            (item for item in category_list if item['name'].lower() == category_name.lower()), None)
        if matching_item:
            return matching_item['id']

    # Wenn nicht gefunden, None zurückgeben
    return None
