import random
from typing import Dict, Any

from lotus_bot.log_setup import get_logger

from .question_state import QuestionStateManager
from .area_providers.base import DynamicQuestionProvider, question_matches_context

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
        self,
        area: str | None = None,
        language: str = "de",
        max_attempts: int = 20,
        context: str = "scheduled",
    ) -> Dict[str, Any] | None:
        """Generate a new question for ``area`` in the given ``language``.

        ``max_attempts`` steuert, wie oft bei dynamischen Quellen erneut versucht
        wird, bis eine noch nicht gestellte Frage gefunden wurde.
        """
        if not area:
            logger.warning("[QuestionGenerator] No area specified.")
            return None

        if area in self.dynamic_providers:
            provider = self.dynamic_providers[area]
            question = None
            attempts = 0
            asked = set(self.state_manager.get_asked_questions(area))

            while attempts < max_attempts:
                q = self._provider_generate(provider, context)
                attempts += 1
                if not q:
                    break
                if not question_matches_context(q, context):
                    continue
                qid = q.get("id")
                if qid in asked:
                    logger.debug(
                        f"[QuestionGenerator] Frage {qid} bereits gestellt, neuer Versuch"
                    )
                    continue
                question = q
                break

            if not question and attempts >= max_attempts:
                logger.info(
                    f"[QuestionGenerator] No new question after {attempts} attempts. Shortening history."
                )
                await self.state_manager.reset_asked_questions(area)
                asked.clear()
                q = self._provider_generate(provider, context)
                if q:
                    question = q

            if question:
                questions = [question]
            else:
                questions = self._provider_generate_all_types(provider, context)
            logger.debug(
                f"[QuestionGenerator] Dynamische Frage für '{area}': {len(questions)}"
            )
        else:
            questions = self.questions_by_area.get(language, {}).get(area, [])
            questions = [q for q in questions if question_matches_context(q, context)]
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

    def _provider_generate(
        self, provider: DynamicQuestionProvider, context: str
    ) -> Dict[str, Any] | None:
        try:
            return provider.generate(context=context)
        except TypeError:
            return provider.generate()

    def _provider_generate_all_types(
        self, provider: DynamicQuestionProvider, context: str
    ) -> list[Dict[str, Any]]:
        try:
            return provider.generate_all_types(context=context)
        except TypeError:
            questions = provider.generate_all_types()
            return [q for q in questions if question_matches_context(q, context)]
