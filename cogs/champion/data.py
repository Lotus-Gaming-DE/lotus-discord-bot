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

    async def _get_db(self) -> aiosqlite.Connection:
        if self.db is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.db = await aiosqlite.connect(self.db_path)
            await self.db.execute("PRAGMA journal_mode=WAL")
        return self.db

    async def init_db(self):
        """Legt Tabellen an, falls sie noch nicht existieren."""
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
            "CREATE INDEX IF NOT EXISTS idx_points_total ON points(total)"
        )
        await db.commit()
        self._init_done = True

        logger.info("[ChampionData] SQLite‐Datenbank initialisiert.")

    async def close(self) -> None:
        """Close the database connection."""
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

    async def get_leaderboard(self, limit: int = 10, offset: int = 0) -> list[tuple[str, int]]:
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
