# cogs/quiz/area_providers/base.py

from abc import ABC, abstractmethod
from typing import Dict, Optional

from log_setup import get_logger

logger = get_logger(__name__)


class DynamicQuestionProvider(ABC):
    @abstractmethod
    def generate(self) -> Optional[Dict]:
        """Generiert eine einzelne Frage."""
        pass

    def generate_all_types(self) -> list[Dict]:
        """Return one question for every generic type if available."""
        questions = []
        for attr in dir(self):
            if attr.startswith("generate_type_"):
                func = getattr(self, attr)
                if callable(func):
                    q = func()
                    if q:
                        questions.append(q)
        return questions
