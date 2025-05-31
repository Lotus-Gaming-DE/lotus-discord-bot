# cogs/quiz/data_loader.py

import json
import os
import logging

logger = logging.getLogger(__name__)  # z.B. "cogs.quiz.data_loader"


class DataLoader:
    QUIZ_DIR = './data/quiz/'
    QUESTIONS_FILE_TEMPLATE = 'questions_{}.json'
    SCORES_FILE = os.path.join(QUIZ_DIR, 'scores.json')
    ASKED_QUESTIONS_FILE = os.path.join(QUIZ_DIR, 'asked_questions.json')

    # Pfade für WCR‐Daten
    WCR_UNITS_FILE = './data/wcr/units.json'
    WCR_LOCALS_DIR = './data/wcr/locals/'

    DEFAULT_LANGUAGE = 'en'

    def __init__(self):
        self.language = self.DEFAULT_LANGUAGE
        self.wcr_units = {}
        self.wcr_locals = {}
        self.questions_by_area = {}
        self.load_all_data()

    def load_all_data(self):
        """Lade beim Start alle Quiz‐ und WCR‐Daten ein."""
        self.questions_by_area = self.load_questions()
        self.wcr_units = self.load_wcr_units()
        self.wcr_locals = self.load_wcr_locals()

    def set_language(self, language_code: str):
        """Sprache umschalten und Fragen sowie WCR‐Lokalisierungen neu laden."""
        self.language = language_code
        self.questions_by_area = self.load_questions()
        self.wcr_locals = self.load_wcr_locals()
        logger.info(f"[DataLoader] Language set to '{self.language}'.")

    def load_questions(self) -> dict:
        """Lade die Quizfragen für die aktuell eingestellte Sprache."""
        questions_file = os.path.join(
            self.QUIZ_DIR,
            self.QUESTIONS_FILE_TEMPLATE.format(self.language)
        )
        try:
            if os.path.exists(questions_file):
                with open(questions_file, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
                logger.info(
                    f"[DataLoader] Questions loaded successfully from '{questions_file}'."
                )
                return questions
            else:
                logger.warning(
                    f"[DataLoader] Questions file '{questions_file}' not found."
                )
                return {}
        except Exception as e:
            logger.error(
                f"[DataLoader] Error loading questions from '{questions_file}': {e}",
                exc_info=True
            )
            return {}

    def load_scores(self) -> dict:
        """Lade die persistierten Benutzer‐Punktestände."""
        try:
            if os.path.exists(self.SCORES_FILE):
                with open(self.SCORES_FILE, 'r', encoding='utf-8') as f:
                    scores = json.load(f)
                logger.info("[DataLoader] Scores loaded successfully.")
                return scores
            else:
                logger.warning(
                    f"[DataLoader] Scores file '{self.SCORES_FILE}' not found."
                )
                return {}
        except Exception as e:
            logger.error(
                f"[DataLoader] Error loading scores: {e}", exc_info=True)
            return {}

    def save_scores(self, scores: dict):
        """Speichere die aktualisierten Benutzer‐Punktestände."""
        try:
            with open(self.SCORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(scores, f, ensure_ascii=False, indent=4)
            logger.info("[DataLoader] Scores saved successfully.")
        except Exception as e:
            logger.error(
                f"[DataLoader] Error saving scores: {e}", exc_info=True)

    def load_asked_questions(self) -> dict:
        """Lade die Historie bereits gestellter Fragen."""
        try:
            if os.path.exists(self.ASKED_QUESTIONS_FILE):
                with open(self.ASKED_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                    asked_questions = json.load(f)
                logger.info(
                    "[DataLoader] Asked questions loaded successfully."
                )
                return asked_questions
            else:
                logger.info(
                    "[DataLoader] No asked-questions file found; initializing empty dict."
                )
                return {}
        except Exception as e:
            logger.error(
                f"[DataLoader] Error loading asked questions: {e}", exc_info=True
            )
            return {}

    def mark_question_as_asked(self, area: str, question_id: int):
        """Kennzeichne eine Frage als gestellt, damit sie nicht wiederholt wird."""
        asked = self.load_asked_questions()
        asked.setdefault(area, [])
        if question_id not in asked[area]:
            asked[area].append(question_id)
            try:
                with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(asked, f, ensure_ascii=False, indent=4)
                logger.info(
                    f"[DataLoader] Question id '{question_id}' marked as asked for area '{area}'."
                )
            except Exception as e:
                logger.error(
                    f"[DataLoader] Error marking question id '{question_id}' as asked: {e}",
                    exc_info=True
                )
        else:
            logger.warning(
                f"[DataLoader] Question id '{question_id}' was already marked as asked for area '{area}'."
            )

    def reset_asked_questions(self, area: str):
        """Setze die Liste gestellter Fragen für eine Area zurück (z.B. wenn alle Fragen durch sind)."""
        asked = self.load_asked_questions()
        asked[area] = []
        try:
            with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(asked, f, ensure_ascii=False, indent=4)
            logger.info(
                f"[DataLoader] Asked questions reset for area '{area}'.")
        except Exception as e:
            logger.error(
                f"[DataLoader] Error resetting asked questions for area '{area}': {e}",
                exc_info=True
            )

    def load_wcr_units(self) -> list:
        """Lade die Einheiten‐Definitionen für dynamische WCR‐Fragen."""
        try:
            if os.path.exists(self.WCR_UNITS_FILE):
                with open(self.WCR_UNITS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info("[DataLoader] WCR units loaded successfully.")
                return data.get('units', [])
            else:
                logger.warning(
                    f"[DataLoader] WCR units file '{self.WCR_UNITS_FILE}' not found."
                )
                return []
        except Exception as e:
            logger.error(
                f"[DataLoader] Error loading WCR units: {e}", exc_info=True)
            return []

    def load_wcr_locals(self) -> dict:
        """Lade pro Sprache die Lokalisierungen für WCR (Namen, Templates etc.)."""
        locals_data = {}
        try:
            for filename in os.listdir(self.WCR_LOCALS_DIR):
                if filename.endswith('.json'):
                    lang = filename[:-5]  # entferne ".json"
                    path = os.path.join(self.WCR_LOCALS_DIR, filename)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        locals_data[lang] = data
                        logger.info(
                            f"[DataLoader] WCR locals for language '{lang}' loaded successfully."
                        )
                    except Exception as e:
                        logger.error(
                            f"[DataLoader] Error loading WCR locals from '{filename}': {e}",
                            exc_info=True
                        )
        except Exception as e:
            logger.error(
                f"[DataLoader] Error accessing WCR locals directory '{self.WCR_LOCALS_DIR}': {e}",
                exc_info=True
            )

        return locals_data
