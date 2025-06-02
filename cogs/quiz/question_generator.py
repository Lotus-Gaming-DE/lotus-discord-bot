import random
import logging
from .utils import create_permutations_list

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, questions_by_area, state_manager, dynamic_providers=None):
        self.questions_by_area = questions_by_area
        self.state = state_manager
        self.dynamic_providers = dynamic_providers or {}
        logger.info("QuestionGenerator initialized.")

    def generate_question_from_json(self, area):
        area_questions = self.questions_by_area.get(area)
        if not area_questions:
            logger.error(
                f"[QuestionGenerator] Area '{area}' not found in loaded questions.")
            return None

        category = random.choice(list(area_questions.keys()))
        category_questions = area_questions[category]
        asked = self.state.get_asked_questions(area)
        remaining = [q for q in category_questions if q["id"] not in asked]

        if not remaining:
            self.state.reset_asked_questions(area)
            remaining = category_questions.copy()
            logger.info(
                f"[QuestionGenerator] Alle Fragen für Bereich '{area}' wurden gestellt. Setze Historie zurück.")

        question_data = random.choice(remaining)
        self.state.mark_question_as_asked(area, question_data["id"])

        logger.info(
            f"[QuestionGenerator] Generated question for area '{area}', category '{category}': {question_data['frage']}"
        )
        return {
            "frage": question_data["frage"],
            "antwort": create_permutations_list([question_data["antwort"]]),
            "category": category,
            "id": question_data["id"],
        }

    def generate_dynamic_question(self, area):
        provider = self.dynamic_providers.get(area)
        if not provider:
            logger.warning(
                f"[QuestionGenerator] No dynamic provider registered for area '{area}'.")
            return None
        return provider.generate()
