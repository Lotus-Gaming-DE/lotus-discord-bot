# cogs/wcr/helpers.py


from log_setup import get_logger

logger = get_logger(__name__)


def build_category_lookup(languages: dict, pictures: dict) -> tuple[dict, dict]:
    """Return lookup dictionaries for faster category access."""
    lang_lookup: dict[str, dict[str, dict[int, dict]]] = {}
    for lang, lang_data in languages.items():
        categories = lang_data.get("categories", {})
        lookup = {}
        for name, items in categories.items():
            lookup[name] = {item["id"]: item for item in items}
        lang_lookup[lang] = lookup

    pic_categories = pictures.get("categories", {})
    pic_lookup = {
        name: {item["id"]: item for item in items}
        for name, items in pic_categories.items()
    }
    return lang_lookup, pic_lookup


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


def get_faction_data(faction_id: int, pictures: dict) -> dict:
    """Return faction meta information for ``faction_id``."""
    factions = pictures.get("category_lookup", {}).get("factions")
    if factions is None:
        factions = {
            f["id"]: f for f in pictures.get("categories", {}).get("factions", [])
        }
    return factions.get(faction_id, {})


def get_category_name(
    category: str, category_id: int, lang: str, languages: dict
) -> str:
    """Return the localized name of a category item."""
    cat_lookup = languages.get(lang, {}).get("category_lookup")
    if cat_lookup is None:
        categories = languages.get(lang, {}).get("categories", {})
        cat_lookup = {
            k: {item["id"]: item for item in v} for k, v in categories.items()
        }
    item = cat_lookup.get(category, {}).get(category_id)
    if item:
        return item.get("name", "Unbekannt")
    return "Unbekannt"


def get_faction_icon(faction_id: int, pictures: dict) -> str:
    """Return the emoji/icon name for a faction."""
    faction_data = get_faction_data(faction_id, pictures)
    return faction_data.get("icon", "")


def normalize_name(name: str) -> list[str]:
    """Normalize a name for comparison and return a list of tokens."""
    return "".join(c for c in name if c.isalnum() or c.isspace()).lower().split()


def find_category_id(
    category_name: str, category: str, lang: str, languages: dict
) -> int | None:
    """Return the ID of ``category_name`` searching all languages."""
    # Zuerst in der aktuellen Sprache suchen
    lookup = languages[lang].get("category_lookup")
    if lookup is None:
        lookup = {
            k: {i["id"]: i for i in v}
            for k, v in languages[lang].get("categories", {}).items()
        }
    category_dict = lookup.get(category, {})
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
    for other_lang, other_texts in languages.items():
        if other_lang == lang:
            continue
        lookup = other_texts.get("category_lookup")
        if lookup is None:
            lookup = {
                k: {i["id"]: i for i in v}
                for k, v in other_texts.get("categories", {}).items()
            }
        category_dict = lookup.get(category, {})
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
