import random
from typing import Dict, Any

from log_setup import get_logger

from .question_state import QuestionStateManager
from .area_providers.base import DynamicQuestionProvider

logger = get_logger(__name__)


class QuestionGenerator:
    def __init__(self, questions_by_area: Dict[str, dict], state_manager: QuestionStateManager,
                 dynamic_providers: Dict[str, DynamicQuestionProvider]):
        self.questions_by_area = questions_by_area
        self.state_manager = state_manager
        self.dynamic_providers = dynamic_providers
        logger.info("[QuestionGenerator] QuestionGenerator initialized.")

    def generate(self, area: str = None, language: str = "de") -> Dict[str, Any] | None:
        if not area:
            logger.warning("[QuestionGenerator] Keine Area angegeben.")
            return None

        if area in self.dynamic_providers:
            provider = self.dynamic_providers[area]
            question = provider.generate()
            questions = [question] if question else []
            logger.debug(
                f"[QuestionGenerator] Dynamische Frage für '{area}': {len(questions)}")
        else:
            questions = self.questions_by_area.get(language, {}).get(area, [])
            if isinstance(questions, dict):
                flat = []
                for category, qs in questions.items():
                    for q in qs:
                        if isinstance(q, dict):
                            q = q.copy()
                            q.setdefault("category", category)
                        flat.append(q)
                questions = flat
            logger.debug(
                f"[QuestionGenerator] Statische Fragen für '{area}': {len(questions)}")

        unasked = self.state_manager.filter_unasked_questions(area, questions)
        if not unasked:
            logger.info(
                f"[QuestionGenerator] Alle Fragen für '{area}' wurden bereits gestellt.")
            return None

        question = random.choice(unasked)
        # store only the question ID in history to avoid unhashable entries
        question_id = question.get("id")
        if question_id is not None:
            self.state_manager.mark_question_as_asked(area, question_id)
        else:
            logger.warning(
                f"[QuestionGenerator] Frage ohne ID in '{area}' kann nicht in der Historie gespeichert werden."
            )
        logger.info(
            f"[QuestionGenerator] Neue Frage für '{area}': {question.get('frage')}")
        return question
