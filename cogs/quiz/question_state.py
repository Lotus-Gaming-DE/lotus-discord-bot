import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class QuestionStateManager:
    """
    Verwaltet persistente Speicherung von aktiven Fragen und Frage-Historie.
    """

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
        self._save_state()

    def get_active_question(self, area: str) -> Optional[dict]:
        return self.state.get("active", {}).get(area)

    def clear_active_question(self, area: str):
        if area in self.state.get("active", {}):
            self.state["active"].pop(area, None)
            self._save_state()

    # ── Historie ───────────────────────────────────────────────────

    def mark_question_as_asked(self, area: str, question_id: int):
        self.state.setdefault("history", {}).setdefault(area, [])
        if question_id not in self.state["history"][area]:
            self.state["history"][area].append(question_id)
            self._save_state()

    def get_asked_questions(self, area: str) -> list[int]:
        return self.state.get("history", {}).get(area, [])

    def reset_asked_questions(self, area: str):
        self.state.setdefault("history", {})[area] = []
        self._save_state()
