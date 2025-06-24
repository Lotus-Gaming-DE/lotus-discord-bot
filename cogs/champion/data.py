import asyncio
import aiosqlite
from datetime import datetime
from typing import Optional
import os

from log_setup import get_logger

logger = get_logger(__name__)


class ChampionData:
    """Verwaltet die SQLite-Datenbank für Champion-Punkte und Historie."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None
        self._init_done = False
        self._lock = asyncio.Lock()

    async def _get_db(self) -> aiosqlite.Connection:
        if self.db is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.db = await aiosqlite.connect(self.db_path)
            await self.db.execute("PRAGMA journal_mode=WAL")
        return self.db

    async def init_db(self):
        """Legt Tabellen an, falls sie noch nicht existieren."""
        async with self._lock:
            if self._init_done:
                return
            db = await self._get_db()
            await db.execute(
                """
            CREATE TABLE IF NOT EXISTS points (
                user_id TEXT PRIMARY KEY,
                total INTEGER NOT NULL
            );
            """
            )
            await db.execute(
                """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT NOT NULL,
                date TEXT NOT NULL
            );
            """
            )
            await db.execute(
                """
            CREATE TABLE IF NOT EXISTS duel_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                result TEXT NOT NULL,
                date TEXT NOT NULL
            );
            """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_points_total ON points(total)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_duel_user ON duel_history(user_id)"
            )
            await db.commit()
            self._init_done = True

        logger.info("[ChampionData] SQLite‐Datenbank initialisiert.")

    async def close(self) -> None:
        """Schließt die Datenbankverbindung."""
        if self.db is not None:
            await self.db.close()
            self.db = None
            self._init_done = False

    async def get_total(self, user_id: str) -> int:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT total FROM points WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        return row[0] if row else 0

    async def add_delta(self, user_id: str, delta: int, reason: str) -> int:
        await self.init_db()
        async with self._lock:
            now = datetime.utcnow().isoformat()

            db = await self._get_db()
            cur = await db.execute(
                "SELECT total FROM points WHERE user_id = ?",
                (user_id,),
            )
            row = await cur.fetchone()
            current_total = row[0] if row else 0

            new_total = current_total + delta
            if row:
                await db.execute(
                    "UPDATE points SET total = ? WHERE user_id = ?",
                    (new_total, user_id),
                )
            else:
                await db.execute(
                    "INSERT INTO points(user_id, total) VALUES (?, ?)",
                    (user_id, new_total),
                )

            await db.execute(
                "INSERT INTO history(user_id, delta, reason, date) VALUES (?, ?, ?, ?)",
                (user_id, delta, reason, now),
            )

            await db.commit()

        logger.info(
            f"[ChampionData] {user_id} Punkte geändert um {delta} ({reason}). Neuer Total: {new_total}."
        )
        return new_total

    async def get_history(self, user_id: str, limit: int = 10) -> list[dict]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT delta, reason, date
              FROM history
             WHERE user_id = ?
             ORDER BY date DESC
             LIMIT ?
            """,
            (user_id, limit),
        )
        rows = await cur.fetchall()

        return [{"delta": r[0], "reason": r[1], "date": r[2]} for r in rows]

    async def get_leaderboard(
        self, limit: int = 10, offset: int = 0
    ) -> list[tuple[str, int]]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT user_id, total
              FROM points
             ORDER BY total DESC
             LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = await cur.fetchall()

        return [(r[0], r[1]) for r in rows]

    async def get_rank(self, user_id: str) -> Optional[tuple[int, int]]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT total FROM points WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        total = row[0]

        cur = await db.execute(
            "SELECT COUNT(*) FROM points WHERE total > ?",
            (total,),
        )
        count_row = await cur.fetchone()
        rank = count_row[0] + 1

        return rank, total

    async def delete_user(self, user_id: str) -> None:
        """Entfernt alle Daten von ``user_id`` aus der Datenbank."""
        await self.init_db()
        async with self._lock:
            db = await self._get_db()
            await db.execute("DELETE FROM points WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
            await db.commit()
        logger.info(f"[ChampionData] Eintrag {user_id} entfernt.")

    async def get_all_user_ids(self) -> list[str]:
        """Liefert eine Liste aller gespeicherten Nutzer-IDs."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("SELECT user_id FROM points")
        rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def record_duel_result(self, user_id: str, result: str) -> None:
        """Fügt einen Duell-Eintrag für ``user_id`` hinzu.

        Parameters
        ----------
        user_id:
            ID des Spielers als String.
        result:
            "win", "loss" oder "tie".
        """
        await self.init_db()
        async with self._lock:
            if result not in {"win", "loss", "tie"}:
                raise ValueError("invalid result")
            now = datetime.utcnow().isoformat()
            db = await self._get_db()
            await db.execute(
                "INSERT INTO duel_history(user_id, result, date) VALUES (?, ?, ?)",
                (user_id, result, now),
            )
            await db.commit()

    async def get_duel_stats(self, user_id: str) -> dict:
        """Gibt Sieg‑, Niederlagen‑ und Unentschieden‑Zahlen zurück."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT result, COUNT(*) FROM duel_history WHERE user_id = ? GROUP BY result",
            (user_id,),
        )
        rows = await cur.fetchall()
        stats = {"win": 0, "loss": 0, "tie": 0}
        for res, cnt in rows:
            stats[res] = cnt
        return stats

    async def get_duel_leaderboard(
        self, limit: int = 10
    ) -> list[tuple[str, int, int, int]]:
        """Liefert ein Leaderboard nach Siegen sortiert."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT user_id,
                   SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE WHEN result='tie' THEN 1 ELSE 0 END) AS ties
              FROM duel_history
             GROUP BY user_id
             ORDER BY wins DESC
             LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        return [(r[0], r[1], r[2], r[3]) for r in rows]
