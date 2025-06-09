import random
from typing import Dict, Any

from log_setup import get_logger

from .question_state import QuestionStateManager
from .area_providers.base import DynamicQuestionProvider

logger = get_logger(__name__)


class QuestionGenerator:
    def __init__(
        self,
        questions_by_area: Dict[str, dict],
        state_manager: QuestionStateManager,
        dynamic_providers: Dict[str, DynamicQuestionProvider],
    ) -> None:
        """Initialize a generator with static and dynamic question sources."""
        self.questions_by_area = questions_by_area
        self.state_manager = state_manager
        self.dynamic_providers = dynamic_providers
        logger.info("[QuestionGenerator] QuestionGenerator initialized.")

    def get_dynamic_provider(self, area: str) -> DynamicQuestionProvider | None:
        """Return the dynamic provider for ``area`` if available."""
        return self.dynamic_providers.get(area)

    async def generate(
        self, area: str | None = None, language: str = "de"
    ) -> Dict[str, Any] | None:
        """Generate a new question for ``area`` in the given ``language``."""
        if not area:
            logger.warning("[QuestionGenerator] Keine Area angegeben.")
            return None

        if area in self.dynamic_providers:
            provider = self.dynamic_providers[area]
            question = None
            for _ in range(5):
                q = provider.generate()
                if not q:
                    break
                qid = q.get("id")
                if qid in self.state_manager.get_asked_questions(area):
                    logger.debug(
                        f"[QuestionGenerator] Frage {qid} bereits gestellt, neuer Versuch"
                    )
                    continue
                question = q
                break

            if question:
                questions = [question]
            else:
                questions = provider.generate_all_types()
            logger.debug(
                f"[QuestionGenerator] Dynamische Frage für '{area}': {len(questions)}"
            )
        else:
            questions = self.questions_by_area.get(language, {}).get(area, [])
            logger.debug(
                f"[QuestionGenerator] Statische Fragen für '{area}': {len(questions)}"
            )

        unasked = self.state_manager.filter_unasked_questions(area, questions)
        if not unasked:
            logger.info(
                f"[QuestionGenerator] Alle Fragen für '{area}' wurden bereits gestellt."
            )
            return None

        question = random.choice(unasked)
        # store only the question ID in history to avoid unhashable entries
        question_id = question.get("id")
        if question_id is not None:
            await self.state_manager.mark_question_as_asked(area, question_id)
        else:
            logger.warning(
                f"[QuestionGenerator] Frage ohne ID in '{area}' kann nicht in der Historie gespeichert werden."
            )
        logger.info(
            f"[QuestionGenerator] Neue Frage für '{area}': {question.get('frage')}"
        )
        return question
