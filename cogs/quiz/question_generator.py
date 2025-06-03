import logging
import random
from typing import Dict, Any

from .question_state import QuestionStateManager
from .area_providers.base import DynamicQuestionProvider

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, questions_by_area: Dict[str, list], state_manager: QuestionStateManager,
                 dynamic_providers: Dict[str, DynamicQuestionProvider]):
        self.questions_by_area = questions_by_area
        self.state_manager = state_manager
        self.dynamic_providers = dynamic_providers
        logger.info("[QuestionGenerator] QuestionGenerator initialized.")

    def generate(self, area: str = None) -> Dict[str, Any] | None:
        """
        Liefert eine neue Frage, entweder aus statischem Fragenpool oder dynamisch erzeugt.
        area: Name der Area (z. B. "wcr")
        """
        if not area:
            logger.warning("[QuestionGenerator] Keine Area angegeben.")
            return None

        # Dynamischer Provider vorhanden?
        if area in self.dynamic_providers:
            provider = self.dynamic_providers[area]
            max_q = getattr(provider, "max_questions", 5)
            questions = provider.generate_questions(max_q)
            logger.debug(
                f"[QuestionGenerator] Dynamisch generierte Fragen für '{area}': {len(questions)}")

            if not isinstance(questions, list):
                logger.warning(
                    f"[QuestionGenerator] Unerwarteter Fragentyp in '{area}': {type(questions)}")
                return None
        else:
            # Statische Fragen aus Pool
            questions = self.questions_by_area.get(area, [])
            logger.debug(
                f"[QuestionGenerator] Statische Fragen für '{area}': {len(questions)}")

            if not isinstance(questions, list):
                logger.warning(
                    f"[QuestionGenerator] Unerwarteter Fragentyp in '{area}': {type(questions)}")
                return None

        # Bereits gestellte Fragen ausfiltern
        unasked = self.state_manager.filter_unasked_questions(area, questions)
        if not unasked:
            logger.info(
                f"[QuestionGenerator] Alle Fragen für '{area}' wurden bereits gestellt.")
            return None

        question = random.choice(unasked)
        self.state_manager.mark_question_as_asked(area, question)
        logger.info(
            f"[QuestionGenerator] Neue Frage für '{area}': {question.get('question')}")
        return question
