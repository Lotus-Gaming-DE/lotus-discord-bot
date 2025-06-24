from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from .question_state import QuestionStateManager
from .question_generator import QuestionGenerator


@dataclass
class QuizAreaConfig:
    channel_id: Optional[int] = None
    time_window: datetime.timedelta = datetime.timedelta(minutes=15)
    language: str = "de"
    active: bool = False
    activity_threshold: int = 10
    question_state: Optional[QuestionStateManager] = None
    question_generator: Optional[QuestionGenerator] = None
