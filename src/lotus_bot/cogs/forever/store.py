"""Eigener Stand des Bots zu den Forever-Gilden (SQLite).

Gespeichert wird nur, was Punkte und Meldungen brauchen: Ausgangsstand je
verbundenem Char, welche Punkte schon vergeben sind, die zuletzt gesehene
Gildenliste (für Austritte), die Meldungen in #wow-logs (für Button und Ping)
und wer den Discord verlassen hat. Verschwindet ein Char aus Lotus Link oder
aus den Lotus-Gilden, wird sein Stand gelöscht.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import aiosqlite

from .registry import GuildMember


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
                CREATE TABLE IF NOT EXISTS roster (
                    guild_slug TEXT NOT NULL,
                    blizzard_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    rank INTEGER NOT NULL,
                    class_key TEXT,
                    first_seen_at TEXT NOT NULL,
                    PRIMARY KEY (guild_slug, blizzard_id)
                );
                CREATE TABLE IF NOT EXISTS notices (
                    message_id INTEGER PRIMARY KEY,
                    kind TEXT NOT NULL,
                    guild_slug TEXT NOT NULL,
                    label TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    pinged_at TEXT,
                    done_by INTEGER,
                    done_at TEXT
                );
                CREATE TABLE IF NOT EXISTS departed (
                    discord_user_id INTEGER PRIMARY KEY,
                    noted_at TEXT NOT NULL
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

    # ------------------------------------------------------------ roster

    async def roster(self, guild_slug: str) -> dict[int, tuple[GuildMember, str]]:
        """Zuletzt gesehene Gildenliste: Blizzard-ID → (Eintrag, gelistet seit)."""
        db = await self._conn()
        cur = await db.execute(
            "SELECT blizzard_id, name, level, rank, class_key, first_seen_at"
            " FROM roster WHERE guild_slug = ?",
            (guild_slug,),
        )
        return {
            row[0]: (
                GuildMember(guild_slug, row[0], row[1], row[2], row[3], row[4]),
                row[5],
            )
            for row in await cur.fetchall()
        }

    async def replace_roster(
        self, guild_slug: str, members: list[GuildMember], now: str
    ) -> None:
        """Speichert die neue Liste. „Gelistet seit“ bleibt für Bekannte erhalten."""
        async with self._lock:
            db = await self._conn()
            keep = [m.blizzard_id for m in members]
            await db.execute(
                "DELETE FROM roster WHERE guild_slug = ? AND blizzard_id NOT IN"
                f" ({','.join('?' * len(keep)) or 'NULL'})",
                (guild_slug, *keep),
            )
            await db.executemany(
                """
                INSERT INTO roster (guild_slug, blizzard_id, name, level, rank,
                                    class_key, first_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_slug, blizzard_id) DO UPDATE SET
                    name = excluded.name,
                    level = excluded.level,
                    rank = excluded.rank,
                    class_key = excluded.class_key
                """,
                [
                    (
                        guild_slug,
                        m.blizzard_id,
                        m.name,
                        m.level,
                        m.rank,
                        m.class_key,
                        now,
                    )
                    for m in members
                ],
            )
            await db.commit()

    # ----------------------------------------------------------- notices

    async def add_notice(
        self, message_id: int, kind: str, guild_slug: str, label: str, now: str
    ) -> None:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "INSERT OR REPLACE INTO notices (message_id, kind, guild_slug, label,"
                " created_at) VALUES (?, ?, ?, ?, ?)",
                (message_id, kind, guild_slug, label, now),
            )
            await db.commit()

    async def notice(self, message_id: int) -> dict | None:
        db = await self._conn()
        cur = await db.execute(
            "SELECT kind, guild_slug, label, done_by FROM notices WHERE message_id = ?",
            (message_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return {
            "kind": row[0],
            "guild_slug": row[1],
            "label": row[2],
            "done_by": row[3],
        }

    async def mark_done(self, message_id: int, user_id: int, now: str) -> bool:
        """``False``, wenn schon jemand anderes schneller war."""
        async with self._lock:
            db = await self._conn()
            cur = await db.execute(
                "UPDATE notices SET done_by = ?, done_at = ?"
                " WHERE message_id = ? AND done_by IS NULL",
                (user_id, now, message_id),
            )
            await db.commit()
            return cur.rowcount == 1

    async def unpinged(self, guild_slug: str) -> list[tuple[int, str, str]]:
        """Offene Meldungen, für die noch nicht gepingt wurde: (ID, Art, Name)."""
        db = await self._conn()
        cur = await db.execute(
            "SELECT message_id, kind, label FROM notices WHERE guild_slug = ?"
            " AND pinged_at IS NULL AND done_by IS NULL ORDER BY created_at, message_id",
            (guild_slug,),
        )
        return [tuple(row) for row in await cur.fetchall()]

    async def open_count(self, guild_slug: str) -> int:
        db = await self._conn()
        cur = await db.execute(
            "SELECT COUNT(*) FROM notices WHERE guild_slug = ? AND done_by IS NULL",
            (guild_slug,),
        )
        return (await cur.fetchone())[0]

    async def mark_pinged(self, message_ids: list[int], now: str) -> None:
        async with self._lock:
            db = await self._conn()
            await db.executemany(
                "UPDATE notices SET pinged_at = ? WHERE message_id = ?",
                [(now, mid) for mid in message_ids],
            )
            await db.commit()

    # ---------------------------------------------------------- departed

    async def departed(self) -> set[int]:
        db = await self._conn()
        cur = await db.execute("SELECT discord_user_id FROM departed")
        return {row[0] for row in await cur.fetchall()}

    async def mark_departed(self, user_id: int, now: str) -> bool:
        """``False``, wenn der Austritt schon gemeldet ist."""
        async with self._lock:
            db = await self._conn()
            cur = await db.execute(
                "INSERT OR IGNORE INTO departed (discord_user_id, noted_at) VALUES (?, ?)",
                (user_id, now),
            )
            await db.commit()
            return cur.rowcount == 1

    async def clear_departed(self, user_id: int) -> None:
        async with self._lock:
            db = await self._conn()
            await db.execute(
                "DELETE FROM departed WHERE discord_user_id = ?", (user_id,)
            )
            await db.commit()
