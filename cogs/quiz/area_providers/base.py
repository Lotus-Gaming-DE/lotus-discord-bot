# cogs/quiz/area_providers/base.py

from abc import ABC, abstractmethod
from typing import List, Dict


class DynamicQuestionProvider(ABC):
    @abstractmethod
    def generate_questions(self, count: int) -> List[Dict]:
        """Generiert dynamisch eine bestimmte Anzahl an Fragen"""
        pass
