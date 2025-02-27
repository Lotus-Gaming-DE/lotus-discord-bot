# cogs/wcr/data_loader.py
import json
import os
import logging

logger = logging.getLogger(__name__)


def load_units():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        units_path = os.path.join(
            current_dir, '..', '..', 'data', 'wcr', 'units.json')
        units_path = os.path.normpath(units_path)

        with open(units_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info("Einheiten erfolgreich geladen.")
        return data['units']
    except Exception as e:
        logger.error(f"Fehler beim Laden der Einheiten: {e}", exc_info=True)
        return []


def load_languages():
    try:
        languages = {}
        current_dir = os.path.dirname(os.path.abspath(__file__))
        locals_dir = os.path.join(
            current_dir, '..', '..', 'data', 'wcr', 'locals')
        locals_dir = os.path.normpath(locals_dir)

        for lang_file in os.listdir(locals_dir):
            if lang_file.endswith('.json'):
                lang_code = lang_file.split('.')[0]
                with open(os.path.join(locals_dir, lang_file), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                languages[lang_code] = data
        logger.info("Sprachdateien erfolgreich geladen.")
        return languages
    except Exception as e:
        logger.error(f"Fehler beim Laden der Sprachdateien: {
                     e}", exc_info=True)
        return {}


def load_pictures():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        pictures_path = os.path.join(
            current_dir, '..', '..', 'data', 'wcr', 'pictures.json')
        pictures_path = os.path.normpath(pictures_path)

        with open(pictures_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info("Bilddaten erfolgreich geladen.")
        return data
    except Exception as e:
        logger.error(f"Fehler beim Laden der Bilddaten: {e}", exc_info=True)
        return {}


def load_emojis():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        emojis_path = os.path.join(
            current_dir, '..', '..', 'data', 'emojis.json')
        emojis_path = os.path.normpath(emojis_path)

        with open(emojis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info("Emojis erfolgreich geladen.")
        return data
    except Exception as e:
        logger.error(f"Fehler beim Laden der Emojis: {e}", exc_info=True)
        return {}
