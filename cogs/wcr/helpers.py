# cogs/wcr/helpers.py


from log_setup import get_logger

logger = get_logger(__name__)


def build_category_lookup(categories: dict) -> dict:
    """Erstellt eine Lookup-Tabelle für Kategorien.

    Die Tabelle enthält für jede Sprache die verfügbaren Kategorien und
    speichert neben dem Namen auch Zusatzinformationen wie Icon und Farbe.
    """

    lang_lookup: dict[str, dict[str, dict[int, dict]]] = {}
    for cat_name, items in categories.items():
        for item in items:
            for lang, name in item.get("names", {}).items():
                lang_dict = lang_lookup.setdefault(lang, {})
                cat_dict = lang_dict.setdefault(cat_name, {})
                cat_dict[item["id"]] = {
                    "id": item["id"],
                    "name": name,
                    **{k: item[k] for k in ("icon", "color") if k in item},
                }

    return lang_lookup


def get_text_data(unit_id: int, lang: str, languages: dict) -> tuple[str, str, list]:
    """Return name, description and talents for a unit in ``lang``."""
    texts = languages.get(lang, languages.get("de", {}))
    unit_text = next(
        (unit for unit in texts.get("units", []) if unit["id"] == unit_id), {}
    )
    return (
        unit_text.get("name", "Unbekannt"),
        unit_text.get("description", "Beschreibung fehlt"),
        unit_text.get("talents", []),
    )


def get_pose_url(unit_id: int, pictures: dict) -> str:
    """Return the pose image URL for a unit."""
    unit_pictures = pictures.get("units", [])
    unit_picture = next((pic for pic in unit_pictures if pic["id"] == unit_id), {})
    return unit_picture.get("pose", "")


def get_faction_data(faction_id: int, lang_lookup: dict) -> dict:
    """Gibt Metadaten für eine Fraktion zurück.

    Die Daten enthalten Icon und Farbe der Fraktion. Es wird dabei die erste
    verfügbare Sprache im Lookup verwendet.
    """

    for cat_data in lang_lookup.values():
        factions = cat_data.get("factions")
        if factions and faction_id in factions:
            return factions[faction_id]
    return {}


def get_category_name(
    category: str, category_id: int, lang: str, lang_lookup: dict
) -> str:
    """Gibt den lokalisierten Namen eines Kategorie-Eintrags zurück."""
    item = lang_lookup.get(lang, {}).get(category, {}).get(category_id)
    if item:
        return item.get("name", "Unbekannt")
    return "Unbekannt"


def get_faction_icon(faction_id: int, lang_lookup: dict) -> str:
    """Gibt den Emoji-/Icon-Namen einer Fraktion zurück."""
    faction_data = get_faction_data(faction_id, lang_lookup)
    return faction_data.get("icon", "")


def normalize_name(name: str) -> list[str]:
    """Normalize a name for comparison and return a list of tokens."""
    return "".join(c for c in name if c.isalnum() or c.isspace()).lower().split()


def find_category_id(
    category_name: str, category: str, lang: str, lang_lookup: dict
) -> int | None:
    """Sucht die ID zu ``category_name`` über alle Sprachen hinweg."""
    # Zuerst in der aktuellen Sprache suchen
    category_dict = lang_lookup.get(lang, {}).get(category, {})
    matching_item = next(
        (
            item
            for item in category_dict.values()
            if item["name"].lower() == category_name.lower()
        ),
        None,
    )
    if matching_item:
        return matching_item["id"]

    # In anderen Sprachen suchen
    for other_lang, other_lookup in lang_lookup.items():
        if other_lang == lang:
            continue
        category_dict = other_lookup.get(category, {})
        matching_item = next(
            (
                item
                for item in category_dict.values()
                if item["name"].lower() == category_name.lower()
            ),
            None,
        )
        if matching_item:
            return matching_item["id"]

    # Wenn nicht gefunden, None zurückgeben
    return None
