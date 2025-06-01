# cogs/quiz/data_loader.py

import os
import json
import logging

logger = logging.getLogger(__name__)


class DataLoader:
    QUIZ_DIR = './data/quiz/'
    QUESTIONS_FILE_TEMPLATE = 'questions_{}.json'
    SCORES_FILE = os.path.join(QUIZ_DIR, 'scores.json')
    ASKED_QUESTIONS_FILE = os.path.join(QUIZ_DIR, 'asked_questions.json')

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

    def load_scores(self) -> dict:
        try:
            if os.path.exists(self.SCORES_FILE):
                with open(self.SCORES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(
                    f"[DataLoader] Scores file '{self.SCORES_FILE}' not found.")
                return {}
        except Exception as e:
            logger.error(
                f"[DataLoader] Error loading scores: {e}", exc_info=True)
            return {}

    def save_scores(self, scores: dict):
        try:
            with open(self.SCORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(scores, f, ensure_ascii=False, indent=4)
            logger.info("[DataLoader] Scores saved successfully.")
        except Exception as e:
            logger.error(
                f"[DataLoader] Error saving scores: {e}", exc_info=True)

    def load_asked_questions(self) -> dict:
        try:
            if os.path.exists(self.ASKED_QUESTIONS_FILE):
                with open(self.ASKED_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.info(
                    "[DataLoader] No asked-questions file found. Starting fresh.")
                return {}
        except Exception as e:
            logger.error(
                f"[DataLoader] Error loading asked questions: {e}", exc_info=True)
            return {}

    def mark_question_as_asked(self, area: str, question_id: int):
        asked = self.load_asked_questions()
        asked.setdefault(area, [])
        if question_id not in asked[area]:
            asked[area].append(question_id)
            try:
                with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(asked, f, ensure_ascii=False, indent=4)
                logger.info(
                    f"[DataLoader] Question '{question_id}' marked as asked for '{area}'.")
            except Exception as e:
                logger.error(
                    f"[DataLoader] Error saving asked question: {e}", exc_info=True)

    def reset_asked_questions(self, area: str):
        asked = self.load_asked_questions()
        asked[area] = []
        try:
            with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(asked, f, ensure_ascii=False, indent=4)
            logger.info(f"[DataLoader] Asked questions reset for '{area}'.")
        except Exception as e:
            logger.error(
                f"[DataLoader] Error resetting asked questions: {e}", exc_info=True)
