# cogs/wcr/utils.py

import json
from pathlib import Path

from log_setup import get_logger

logger = get_logger(__name__)

BASE_PATH = Path("data/wcr")


def load_units():
    """Lädt die Einheitendaten aus ``units.json``."""
    path = BASE_PATH / "units.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        units = data.get("units", data)
        logger.info("[WCRUtils] Einheiten erfolgreich geladen.")
        return units
    except Exception as e:
        logger.error(f"[WCRUtils] Fehler beim Laden der Einheiten: {e}")
        return {}


def load_languages():
    """Lädt die Lokalisationen aus ``units.json``."""
    path = BASE_PATH / "units.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        locals_ = data.get("locals", {})
        # Einheiten-Texte aus den Units einsammeln
        for unit in data.get("units", []):
            texts = unit.get("texts", {})
            for lang, info in texts.items():
                lang_data = locals_.setdefault(lang, {})
                units = lang_data.setdefault("units", [])
                unit_entry = {"id": unit.get("id")}
                unit_entry.update(info)
                units.append(unit_entry)
        logger.info(
            "[WCRUtils] Sprachdateien erfolgreich geladen: %s",
            list(locals_.keys()),
        )
        return locals_
    except Exception as e:
        logger.error(f"[WCRUtils] Fehler beim Laden der Sprachdaten: {e}")
        return {}


def load_pictures():
    """Lädt Bilddaten aus pictures.json."""
    path = BASE_PATH / "pictures.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            pictures = json.load(f)
        logger.info("[WCRUtils] Bilddaten erfolgreich geladen.")
        return pictures
    except Exception as e:
        logger.error(f"[WCRUtils] Fehler beim Laden der Bilddaten: {e}")
        return {}


def load_categories():
    """Lädt die Kategorien aus ``categories.json``."""
    path = BASE_PATH / "categories.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            categories = json.load(f)
        logger.info("[WCRUtils] Kategorien erfolgreich geladen.")
        return categories
    except Exception as e:
        logger.error(f"[WCRUtils] Fehler beim Laden der Kategorien: {e}")
        return {}


def load_stat_labels():
    """Lädt die Stat-Labels aus ``stat_labels.json``."""
    path = BASE_PATH / "stat_labels.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            labels = json.load(f)
        logger.info("[WCRUtils] Stat-Labels erfolgreich geladen.")
        return labels
    except Exception as e:
        logger.error(f"[WCRUtils] Fehler beim Laden der Stat-Labels: {e}")
        return {}


def load_wcr_data():
    """Fasst alle WCR-Daten zusammen, wie sie im Bot verwendet werden."""
    return {
        "units": load_units(),
        "locals": load_languages(),
        "pictures": load_pictures(),
        "categories": load_categories(),
        "stat_labels": load_stat_labels(),
    }
