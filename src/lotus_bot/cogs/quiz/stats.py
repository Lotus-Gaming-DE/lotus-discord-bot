import json
import os
import asyncio

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


class QuizStats:
    """Persistiert die Anzahl richtiger Antworten pro Nutzer."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._lock = asyncio.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.filepath):
            logger.info(f"[QuizStats] Datei nicht gefunden: {self.filepath}")
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # pragma: no cover - log error
            logger.error(f"[QuizStats] Fehler beim Laden: {e}", exc_info=True)
            return {}

    async def _save(self) -> None:
        async with self._lock:
            try:
                os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=4, ensure_ascii=False)
            except Exception as e:  # pragma: no cover - log error
                logger.error(f"[QuizStats] Fehler beim Speichern: {e}", exc_info=True)

    async def increment(self, user_id: int, delta: int = 1) -> int:
        uid = str(user_id)
        self.data[uid] = self.data.get(uid, 0) + delta
        await self._save()
        logger.debug(f"[QuizStats] {uid} -> {self.data[uid]}")
        return self.data[uid]

    def get(self, user_id: int) -> int:
        return self.data.get(str(user_id), 0)
