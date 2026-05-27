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
    # Minimum time a posted question stays open for answers, regardless of
    # how late in the window it was actually posted (activity gating can
    # delay a post until near window_end).
    answer_duration: datetime.timedelta = datetime.timedelta(minutes=5)
    language: str = "de"
    active: bool = False
    activity_threshold: int = 10
    question_state: Optional[QuestionStateManager] = None
    question_generator: Optional[QuestionGenerator] = None
