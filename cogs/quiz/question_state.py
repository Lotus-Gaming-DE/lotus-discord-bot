# cogs/quiz/question_state.py

import json
import os
import datetime
import asyncio
from dataclasses import dataclass
from typing import Optional

from log_setup import get_logger

logger = get_logger(__name__)


@dataclass
class QuestionInfo:
    """Typed representation of a stored quiz question."""

    message_id: int
    end_time: datetime.datetime
    answers: list[str]
    frage: str
    category: str = "–"

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "end_time": self.end_time.isoformat(),
            "answers": self.answers,
            "frage": self.frage,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuestionInfo":
        return cls(
            message_id=data["message_id"],
            end_time=datetime.datetime.fromisoformat(data["end_time"]),
            answers=list(data.get("answers", [])),
            frage=data.get("frage", ""),
            category=data.get("category", "–"),
        )


class QuestionStateManager:
    def __init__(self, filepath: str) -> None:
        """Create a manager for persisting question state at ``filepath``."""
        self.filepath = filepath
        self._lock = asyncio.Lock()
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load the state file if it exists, otherwise return defaults."""
        if not os.path.exists(self.filepath):
            logger.info(f"[QuestionState] Datei nicht gefunden: {self.filepath}")
            return {"active": {}, "history": {}, "schedules": {}}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                logger.info(f"[QuestionState] Lade Datei: {self.filepath}")
                data = json.load(f)
                # add missing keys for backward compatibility
                data.setdefault("schedules", {})
                return data
        except Exception as e:
            logger.error(f"[QuestionState] Fehler beim Laden: {e}", exc_info=True)
            return {"active": {}, "history": {}, "schedules": {}}

    async def _save_state(self) -> None:
        """Persist the current state to disk."""
        async with self._lock:
            try:
                os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=4, ensure_ascii=False)
                logger.debug("[QuestionState] Zustand gespeichert.")
            except Exception as e:
                logger.error(
                    f"[QuestionState] Fehler beim Speichern: {e}",
                    exc_info=True,
                )

    # ── Aktive Fragen ─────────────────────────────────────────────

    async def set_active_question(self, area: str, question: QuestionInfo) -> None:
        """Remember the currently active question for an area."""
        self.state["active"][area] = question.to_dict()
        logger.info(f"[QuestionState] Neue aktive Frage in '{area}' gespeichert.")
        await self._save_state()

    def get_active_question(self, area: str) -> Optional[QuestionInfo]:
        """Return the active question for ``area`` if one exists."""
        data = self.state.get("active", {}).get(area)
        return QuestionInfo.from_dict(data) if data else None

    async def clear_active_question(self, area: str) -> None:
        """Remove the active question for ``area`` from the state."""
        if area in self.state.get("active", {}):
            self.state["active"].pop(area, None)
            logger.info(f"[QuestionState] Aktive Frage in '{area}' wurde entfernt.")
            await self._save_state()

    # ── Historie ───────────────────────────────────────────────────

    async def mark_question_as_asked(self, area: str, question_id: int) -> None:
        """Add ``question_id`` to the history of ``area``."""
        self.state.setdefault("history", {}).setdefault(area, [])
        if question_id not in self.state["history"][area]:
            self.state["history"][area].append(question_id)
            logger.info(
                f"[QuestionState] Frage-ID {question_id} in '{area}' als gestellt markiert."
            )
            await self._save_state()

    def get_asked_questions(self, area: str) -> list[int]:
        """Return a list of question IDs already asked in ``area``."""
        return self.state.get("history", {}).get(area, [])

    async def reset_asked_questions(self, area: str) -> None:
        """Clear the question history for ``area``."""
        self.state.setdefault("history", {})[area] = []
        logger.info(f"[QuestionState] Historie in '{area}' zurückgesetzt.")
        await self._save_state()

    # ── Fragefilterung ────────────────────────────────────────────

    def filter_unasked_questions(self, area: str, questions: list[dict]) -> list[dict]:
        """
        Gibt nur Fragen zurück, die noch nicht gestellt wurden (basierend auf ID).
        """
        asked_ids = set(self.get_asked_questions(area))
        return [q for q in questions if q.get("id") not in asked_ids]

    # ── Scheduler-Daten ──────────────────────────────────────────

    async def set_schedule(
        self, area: str, post_time: datetime.datetime, window_end: datetime.datetime
    ) -> None:
        """Persist the next ``post_time`` and ``window_end`` for ``area``."""
        self.state.setdefault("schedules", {})[area] = {
            "post_time": post_time.isoformat(),
            "window_end": window_end.isoformat(),
        }
        logger.debug(
            f"[QuestionState] Nächste Planung für '{area}' gespeichert: {post_time}"
        )
        await self._save_state()

    def get_schedule(
        self, area: str
    ) -> Optional[tuple[datetime.datetime, datetime.datetime]]:
        """Return saved ``post_time`` and ``window_end`` for ``area`` if present."""
        data = self.state.get("schedules", {}).get(area)
        if not data:
            return None
        try:
            post_time = datetime.datetime.fromisoformat(data["post_time"])
            window_end = datetime.datetime.fromisoformat(data["window_end"])
            return post_time, window_end
        except Exception as e:
            logger.error(
                f"[QuestionState] Fehler beim Lesen des Schedules f\u00fcr '{area}': {e}",
                exc_info=True,
            )
            return None

    async def clear_schedule(self, area: str) -> None:
        """Remove stored schedule info for ``area``."""
        if area in self.state.get("schedules", {}):
            self.state["schedules"].pop(area, None)
            logger.debug(f"[QuestionState] Schedule f\u00fcr '{area}' gel\u00f6scht.")
            await self._save_state()
