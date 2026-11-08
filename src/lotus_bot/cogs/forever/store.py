"""Eigener Stand des Bots zu den Forever-Gilden (SQLite).

Gespeichert wird nur, was die Punkte brauchen: Ausgangsstand je verbundenem
Char und welche Punkte schon vergeben sind. Verschwindet ein Char aus Lotus
Link oder aus den Lotus-Gilden, wird sein Stand gelöscht.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import aiosqlite


@dataclass(frozen=True)
class Tracked:
    character_id: int
    discord_user_id: int
    guild_slug: str
    baseline_level: int


class ForeverStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def _conn(self) -> aiosqlite.Connection:
        if self._db is None:
            if os.path.dirname(self.path):
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._db = await aiosqlite.connect(self.path)
            await self._db.executescript("""
                CREATE TABLE IF NOT EXISTS tracked (
                    character_id INTEGER PRIMARY KEY,
                    discord_user_id INTEGER NOT NULL,
                    guild_slug TEXT NOT NULL,
                    baseline_level INTEGER NOT NULL,
                    first_seen_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS awards (
                    kind TEXT NOT NULL,
                    award_key TEXT NOT NULL,
                    awarded_at TEXT NOT NULL,
                    PRIMARY KEY (kind, award_key)
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """)
            await self._db.commit()
        return self._db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def tracked(self) -> dict[int, Tracked]:
        db = await self._conn()
        cur = await db.execute(
            "SELECT character_id, discord_user_id, guild_slug, baseline_level FROM tracked"
        )
        return {row[0]: Tracked(*row) for row in await cur.fetchall()}

    async def track(self, tracked: Tracked, now: str) -> None:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                """
                INSERT INTO tracked (character_id, discord_user_id, guild_slug,
                                     baseline_level, first_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(character_id) DO UPDATE SET
                    discord_user_id = excluded.discord_user_id,
                    guild_slug = excluded.guild_slug
                """,
                (
                    tracked.character_id,
                    tracked.discord_user_id,
                    tracked.guild_slug,
                    tracked.baseline_level,
                    now,
                ),
            )
            await db.commit()

    async def untrack(self, character_id: int) -> None:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "DELETE FROM tracked WHERE character_id = ?", (character_id,)
            )
            await db.commit()

    async def claim_award(self, kind: str, key: str, now: str) -> bool:
        """Reserviert eine Vergabe. ``False``, wenn sie schon vergeben ist."""
        async with self._lock:
            db = await self._conn()
            cur = await db.execute(
                "INSERT OR IGNORE INTO awards (kind, award_key, awarded_at) VALUES (?, ?, ?)",
                (kind, key, now),
            )
            await db.commit()
            return cur.rowcount == 1

    async def release_award(self, kind: str, key: str) -> None:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "DELETE FROM awards WHERE kind = ? AND award_key = ?", (kind, key)
            )
            await db.commit()

    async def get_setting(self, key: str) -> str | None:
        db = await self._conn()
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await db.commit()
