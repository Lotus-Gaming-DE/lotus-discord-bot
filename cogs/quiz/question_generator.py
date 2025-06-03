import logging
import random
from typing import Dict, Any

from .question_state import QuestionStateManager
from .area_providers.base import DynamicQuestionProvider

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, questions_by_area: Dict[str, dict], state_manager: QuestionStateManager,
                 dynamic_providers: Dict[str, DynamicQuestionProvider]):
        self.questions_by_area = questions_by_area
        self.state_manager = state_manager
        self.dynamic_providers = dynamic_providers
        logger.info("[QuestionGenerator] QuestionGenerator initialized.")

    def generate(self, area: str = None) -> Dict[str, Any] | None:
        if not area:
            logger.warning("[QuestionGenerator] Keine Area angegeben.")
            return None

        if area in self.dynamic_providers:
            provider = self.dynamic_providers[area]
            questions = [provider.generate() for _ in range(5)]
            questions = [q for q in questions if q]
            logger.debug(
                f"[QuestionGenerator] Dynamisch generierte Fragen für '{area}': {len(questions)}")
        else:
            questions = self.questions_by_area.get("de", {}).get(area, [])
            logger.debug(
                f"[QuestionGenerator] Statische Fragen für '{area}': {len(questions)}")

        unasked = self.state_manager.filter_unasked_questions(area, questions)
        if not unasked:
            logger.info(
                f"[QuestionGenerator] Alle Fragen für '{area}' wurden bereits gestellt.")
            return None

        question = random.choice(unasked)
        self.state_manager.mark_question_as_asked(area, question)
        logger.info(
            f"[QuestionGenerator] Neue Frage für '{area}': {question.get('frage')}")
        return question
