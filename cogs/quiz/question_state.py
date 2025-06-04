# cogs/quiz/question_state.py

import json
import os
from log_setup import get_logger
from typing import Optional

logger = get_logger(__name__)


class QuestionStateManager:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.state = self._load_state()

    def _load_state(self) -> dict:
        if not os.path.exists(self.filepath):
            logger.info(
                f"[QuestionState] Datei nicht gefunden: {self.filepath}")
            return {"active": {}, "history": {}}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                logger.info(f"[QuestionState] Lade Datei: {self.filepath}")
                return json.load(f)
        except Exception as e:
            logger.error(
                f"[QuestionState] Fehler beim Laden: {e}", exc_info=True)
            return {"active": {}, "history": {}}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4, ensure_ascii=False)
            logger.debug("[QuestionState] Zustand gespeichert.")
        except Exception as e:
            logger.error(
                f"[QuestionState] Fehler beim Speichern: {e}", exc_info=True)

    # ── Aktive Fragen ─────────────────────────────────────────────

    def set_active_question(self, area: str, question: dict):
        self.state["active"][area] = question
        logger.info(
            f"[QuestionState] Neue aktive Frage in '{area}' gespeichert.")
        self._save_state()

    def get_active_question(self, area: str) -> Optional[dict]:
        return self.state.get("active", {}).get(area)

    def clear_active_question(self, area: str):
        if area in self.state.get("active", {}):
            self.state["active"].pop(area, None)
            logger.info(
                f"[QuestionState] Aktive Frage in '{area}' wurde entfernt.")
            self._save_state()

    # ── Historie ───────────────────────────────────────────────────

    def mark_question_as_asked(self, area: str, question_id: int):
        self.state.setdefault("history", {}).setdefault(area, [])
        if question_id not in self.state["history"][area]:
            self.state["history"][area].append(question_id)
            logger.info(
                f"[QuestionState] Frage-ID {question_id} in '{area}' als gestellt markiert.")
            self._save_state()

    def get_asked_questions(self, area: str) -> list[int]:
        return self.state.get("history", {}).get(area, [])

    def reset_asked_questions(self, area: str):
        self.state.setdefault("history", {})[area] = []
        logger.info(f"[QuestionState] Historie in '{area}' zurückgesetzt.")
        self._save_state()

    # ── Fragefilterung ────────────────────────────────────────────

    def filter_unasked_questions(self, area: str, questions: list[dict]) -> list[dict]:
        """
        Gibt nur Fragen zurück, die noch nicht gestellt wurden (basierend auf ID).
        """
        asked_ids = set(self.get_asked_questions(area))
        return [q for q in questions if q.get("id") not in asked_ids]
