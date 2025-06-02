# cogs/quiz/data_loader.py

import os
import json
import logging

logger = logging.getLogger(__name__)


class DataLoader:
    QUIZ_DIR = './data/quiz/'
    QUESTIONS_FILE_TEMPLATE = 'questions_{}.json'

    DEFAULT_LANGUAGE = 'de'

    def __init__(self):
        self.language = self.DEFAULT_LANGUAGE
        self.questions_by_area = {}
        self.load_questions()

    def set_language(self, language_code: str):
        """Sprache wechseln und passende Fragen laden."""
        self.language = language_code
        self.load_questions()
        logger.info(f"[DataLoader] Language set to '{self.language}'.")

    def load_questions(self) -> dict:
        """Lade Fragen für die aktuelle Sprache."""
        questions_file = os.path.join(
            self.QUIZ_DIR,
            self.QUESTIONS_FILE_TEMPLATE.format(self.language)
        )
        try:
            if os.path.exists(questions_file):
                with open(questions_file, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
                self.questions_by_area = questions
                logger.info(
                    f"[DataLoader] Questions loaded from '{questions_file}'.")
            else:
                self.questions_by_area = {}
                logger.warning(
                    f"[DataLoader] Questions file '{questions_file}' not found.")
        except Exception as e:
            self.questions_by_area = {}
            logger.error(
                f"[DataLoader] Error loading questions: {e}", exc_info=True)
