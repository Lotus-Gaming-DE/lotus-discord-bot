# cogs/wcr/utils.py

import json
from pathlib import Path

from log_setup import get_logger

logger = get_logger(__name__)

BASE_PATH = Path("data/wcr")


def load_units():
    """Lädt die Einheitendaten aus units.json."""
    path = BASE_PATH / "units.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            units = json.load(f)
        logger.info("[WCRUtils] Einheiten erfolgreich geladen.")
        return units
    except Exception as e:
        logger.error(f"[WCRUtils] Fehler beim Laden der Einheiten: {e}")
        return {}


def load_languages():
    """Lädt alle Lokalisierungsdateien aus dem Unterordner 'locals'."""
    folder = BASE_PATH / "locals"
    result = {}
    for file in folder.glob("*.json"):
        lang = file.stem
        try:
            with open(file, "r", encoding="utf-8") as f:
                result[lang] = json.load(f)
        except Exception as e:
            logger.error(f"[WCRUtils] Fehler beim Laden von {file}: {e}")
    logger.info(
        f"[WCRUtils] Sprachdateien erfolgreich geladen: {list(result.keys())}")
    return result


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


def load_wcr_data():
    """Fasst alle WCR-Daten zusammen, wie sie im Bot verwendet werden."""
    return {
        "units": load_units(),
        "locals": load_languages(),
        "pictures": load_pictures(),
    }
