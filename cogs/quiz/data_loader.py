# cogs/quiz/data_loader.py
import json
import os
import logging

logger = logging.getLogger(__name__)


class DataLoader:
    QUESTIONS_FILE = './data/questions.json'
    SCORES_FILE = './data/scores.json'
    ASKED_QUESTIONS_FILE = './data/asked_questions.json'
    WCR_UNITS_FILE = './data/wcr/units.json'
    WCR_LOCALS_DIR = './data/wcr/locals/'
    DEFAULT_LANGUAGE = 'en'  # Standardmäßig 'en', kann geändert werden

    def __init__(self):
        self.language = self.DEFAULT_LANGUAGE
        self.wcr_units = {}
        self.wcr_locals = {}
        self.questions_by_area = {}
        self.load_all_data()

    def load_all_data(self):
        self.questions_by_area = self.load_questions()
        self.wcr_units = self.load_wcr_units()
        self.wcr_locals = self.load_wcr_locals()

    def set_language(self, language_code):
        self.language = language_code
        self.wcr_locals = self.load_wcr_locals()
        logger.info(f"Language set to '{self.language}'.")

    def load_questions(self):
        try:
            if os.path.exists(self.QUESTIONS_FILE):
                with open(self.QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
                    logger.info("Questions loaded successfully.")
                    return questions
            else:
                logger.warning(f"{self.QUESTIONS_FILE} not found.")
                return {}
        except Exception as e:
            logger.error(f"Error loading questions: {e}")
            return {}

    def load_scores(self):
        try:
            if os.path.exists(self.SCORES_FILE):
                with open(self.SCORES_FILE, 'r', encoding='utf-8') as f:
                    scores = json.load(f)
                    logger.info("Scores loaded successfully.")
                    return scores
            else:
                logger.warning(f"{self.SCORES_FILE} not found.")
                return {}
        except Exception as e:
            logger.error(f"Error loading scores: {e}")
            return {}

    def save_scores(self, scores):
        try:
            with open(self.SCORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(scores, f, ensure_ascii=False, indent=4)
                logger.info("Scores saved successfully.")
        except Exception as e:
            logger.error(f"Error saving scores: {e}")

    def load_asked_questions(self):
        if os.path.exists(self.ASKED_QUESTIONS_FILE):
            with open(self.ASKED_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                asked_questions = json.load(f)
                logger.info("Asked questions loaded successfully.")
                return asked_questions
        else:
            return {}  # Initialisiere mit leerem Dict

    def mark_question_as_asked(self, area, question_id):
        asked_questions = self.load_asked_questions()
        if area not in asked_questions:
            asked_questions[area] = []
        if question_id not in asked_questions[area]:
            asked_questions[area].append(question_id)
            with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(asked_questions, f)
            logger.info(f"Question with ID {
                        question_id} marked as asked for area '{area}'.")
        else:
            logger.warning(f"Question with ID {
                question_id} was already marked as asked for area '{area}'.")

    def reset_asked_questions(self, area):
        asked_questions = self.load_asked_questions()
        asked_questions[area] = []
        with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(asked_questions, f)
        logger.info(f"Asked questions reset for area '{area}'.")

    def load_wcr_units(self):
        try:
            if os.path.exists(self.WCR_UNITS_FILE):
                with open(self.WCR_UNITS_FILE, 'r', encoding='utf-8') as f:
                    units = json.load(f)
                    logger.info("WCR units loaded successfully.")
                    return units.get('units', [])
            else:
                logger.warning(f"{self.WCR_UNITS_FILE} not found.")
                return []
        except Exception as e:
            logger.error(f"Error loading WCR units: {e}")
            return []

    def load_wcr_locals(self):
        locals_data = {}
        for filename in os.listdir(self.WCR_LOCALS_DIR):
            if filename.endswith('.json'):
                language_code = filename[:-5]  # Entferne '.json'
                local_file = os.path.join(self.WCR_LOCALS_DIR, filename)
                try:
                    with open(local_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        locals_data[language_code] = data
                        logger.info(f"WCR locals for language '{
                                    language_code}' loaded successfully.")
                except Exception as e:
                    logger.error(f"Error loading WCR locals '{filename}': {e}")
        return locals_data
