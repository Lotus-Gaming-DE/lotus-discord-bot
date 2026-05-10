# cogs/quiz/area_providers/base.py

from abc import ABC, abstractmethod
from typing import Dict, Optional, List

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


def question_matches_context(question: dict, context: str = "scheduled") -> bool:
    """Return whether ``question`` should be used in the given quiz context."""
    contexts = question.get("contexts")
    if contexts and context not in contexts:
        return False

    difficulty = question.get("difficulty", "medium")
    if context == "scheduled" and difficulty == "easy":
        return False

    return True


class DynamicQuestionProvider(ABC):
    """Base class for providers generating dynamic quiz questions."""

    question_generators: List[str] = []

    @abstractmethod
    def generate(self, context: str = "scheduled") -> Optional[Dict]:
        """Generiert eine einzelne Frage."""
        pass

    def generate_all_types(self, context: str = "scheduled") -> list[Dict]:
        """Return one question for every registered type if available."""
        questions = []
        for name in self.question_generators:
            func = getattr(self, name, None)
            if callable(func):
                q = func()
                if q and question_matches_context(q, context):
                    questions.append(q)
        return questions
