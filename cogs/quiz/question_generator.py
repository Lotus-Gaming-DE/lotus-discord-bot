import logging
import random

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, questions_by_area, state_manager, dynamic_providers=None):
        self.questions_by_area = questions_by_area
        self.state = state_manager
        self.dynamic_providers = dynamic_providers or {}

        logger.info("[QuestionGenerator] QuestionGenerator initialized.")

    def generate_question_from_json(self, area: str) -> dict | None:
        questions = self.questions_by_area.get(area, {}).get("fragen", [])
        if not questions:
            logger.warning(
                f"[QuestionGenerator] Keine statischen Fragen für '{area}'.")
            return None

        frage = random.choice(questions)
        logger.info(
            f"[QuestionGenerator] Statische Frage gewählt für '{area}': {frage.get('frage', '-')}")
        return frage

    def generate_dynamic_question(self, area: str) -> dict | None:
        provider = self.dynamic_providers.get(area)
        if not provider:
            logger.warning(
                f"[QuestionGenerator] Kein Provider registriert für '{area}'.")
            return None

        try:
            frage = provider.generate()
            if not frage:
                logger.warning(
                    f"[QuestionGenerator] Keine dynamische Frage generiert für '{area}'.")
                return None

            logger.info(
                f"[QuestionGenerator] Dynamische Frage gewählt für '{area}': {frage.get('frage', '-')}")
            return frage
        except Exception as e:
            logger.error(
                f"[QuestionGenerator] Fehler beim Erzeugen dynamischer Frage für '{area}': {e}", exc_info=True)
            return None
