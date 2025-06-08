import aiosqlite
import os

from log_setup import get_logger

logger = get_logger(__name__)


class DuelStats:
    """Speichert Siege und Niederlagen pro Nutzer."""

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

    async def init_db(self) -> None:
        if self._init_done:
            return
        db = await self._get_db()
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS stats (
                user_id TEXT PRIMARY KEY,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        await db.commit()
        self._init_done = True
        logger.info("[DuelStats] SQLite-Datenbank initialisiert.")

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
            self._init_done = False

    async def record_result(self, winner_id: int, loser_id: int) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            "INSERT INTO stats(user_id, wins, losses) VALUES(?, 1, 0) "
            "ON CONFLICT(user_id) DO UPDATE SET wins = wins + 1",
            (str(winner_id),),
        )
        await db.execute(
            "INSERT INTO stats(user_id, wins, losses) VALUES(?, 0, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET losses = losses + 1",
            (str(loser_id),),
        )
        await db.commit()
        logger.debug(
            f"[DuelStats] Ergebnis gespeichert: Gewinner {winner_id}, Verlierer {loser_id}"
        )

    async def get_stats(self, user_id: int) -> tuple[int, int]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT wins, losses FROM stats WHERE user_id = ?",
            (str(user_id),),
        )
        row = await cur.fetchone()
        return (row[0], row[1]) if row else (0, 0)

    async def get_leaderboard(self, limit: int = 10) -> list[tuple[str, int, int]]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT user_id, wins, losses FROM stats ORDER BY wins DESC LIMIT ?",
            (limit,),
        )
        rows = await cur.fetchall()
        return [(r[0], r[1], r[2]) for r in rows]
