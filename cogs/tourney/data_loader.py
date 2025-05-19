import os
import json
import logging

# Logger für das Tourney-Data-Modul
logger = logging.getLogger("cogs.tourney.data_loader")

# Ordner und Dateipfad festlegen
DATA_FOLDER = "data/tourney"
FILE_PATH = os.path.join(DATA_FOLDER, "tournaments.json")


def load_tournaments():
    """
    Lädt die Liste aller Turniere aus data/tourney/tournaments.json.
    Legt Ordner und Datei an, falls noch nicht vorhanden.
    Gibt eine Python-Liste zurück.
    """
    # Ordner anlegen, falls er fehlt
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        logger.info(f"Ordner angelegt: {DATA_FOLDER!r}")

    # Datei mit leerer Liste anlegen, falls sie fehlt
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        logger.info(f"Leere Datei angelegt: {FILE_PATH!r}")

    # Datei einlesen
    logger.info(f"Lade Turniere aus {FILE_PATH!r}")
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"{len(data)} Turnier(e) geladen")
    return data


def save_tournaments(tournaments):
    """
    Speichert die gegebene Liste von Turnier-Daten in data/tourney/tournaments.json.
    'tournaments' muss eine Python-Liste sein.
    """
    # Ordner anlegen, falls er fehlt
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        logger.info(f"Ordner angelegt: {DATA_FOLDER!r}")

    # Liste als JSON-Datei speichern
    logger.info(f"Speichere {len(tournaments)} Turnier(e) nach {FILE_PATH!r}")
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(tournaments, f, indent=4, ensure_ascii=False)
    logger.info("Speichern erfolgreich")
