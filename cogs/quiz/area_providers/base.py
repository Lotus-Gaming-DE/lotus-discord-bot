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
