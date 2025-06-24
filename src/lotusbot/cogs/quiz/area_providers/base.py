# cogs/quiz/area_providers/base.py

from abc import ABC, abstractmethod
from typing import Dict, Optional, List

from lotusbot.log_setup import get_logger

logger = get_logger(__name__)


class DynamicQuestionProvider(ABC):
    """Base class for providers generating dynamic quiz questions."""

    question_generators: List[str] = []

    @abstractmethod
    def generate(self) -> Optional[Dict]:
        """Generiert eine einzelne Frage."""
        pass

    def generate_all_types(self) -> list[Dict]:
        """Return one question for every registered type if available."""
        questions = []
        for name in self.question_generators:
            func = getattr(self, name, None)
            if callable(func):
                q = func()
                if q:
                    questions.append(q)
        return questions
