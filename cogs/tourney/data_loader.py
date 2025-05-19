# cogs/tourney/data_loader.py

import os
import json

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
    # Datei mit leerer Liste anlegen, falls sie fehlt
    if not os.path.exists(FILE_PATH):
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
    # Datei einlesen und zurückgeben
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_tournaments(tournaments):
    """
    Speichert die gegebene Liste von Turnier-Daten in data/tourney/tournaments.json.
    'tournaments' muss eine Python-Liste sein, z. B. eine Liste von Dictionaries.
    """
    # Ordner anlegen, falls er fehlt
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    # Liste als JSON-Datei speichern
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(tournaments, f, indent=4, ensure_ascii=False)
