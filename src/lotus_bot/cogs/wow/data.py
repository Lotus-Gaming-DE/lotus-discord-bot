import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiosqlite

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


@dataclass
class RosterMember:
    character_key: str
    character_id: int | None
    name: str
    realm_slug: str
    level: int
    class_id: int | None
    race_id: int | None
    faction: str
    guild_rank: int | None


class WoWData:
    """SQLite storage for WoW guild settings, snapshots, and milestones."""

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
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS roster_snapshot (
                character_key TEXT PRIMARY KEY,
                character_id INTEGER,
                name TEXT NOT NULL,
                realm_slug TEXT NOT NULL,
                level INTEGER NOT NULL,
                class_id INTEGER,
                race_id INTEGER,
                faction TEXT,
                guild_rank INTEGER,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS milestone_events (
                character_key TEXT NOT NULL,
                level INTEGER NOT NULL,
                announced_at TEXT NOT NULL,
                PRIMARY KEY(character_key, level)
            )
            """
        )
        await db.commit()
        self._init_done = True
        logger.info("[WoWData] SQLite database initialized.")

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
            self._init_done = False

    async def get_setting(self, key: str) -> str | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await db.commit()

    async def get_snapshot(self) -> dict[str, RosterMember]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT character_key, character_id, name, realm_slug, level, class_id,
                   race_id, faction, guild_rank
              FROM roster_snapshot
            """
        )
        rows = await cur.fetchall()
        return {
            row[0]: RosterMember(
                character_key=row[0],
                character_id=row[1],
                name=row[2],
                realm_slug=row[3],
                level=row[4],
                class_id=row[5],
                race_id=row[6],
                faction=row[7] or "",
                guild_rank=row[8],
            )
            for row in rows
        }

    async def replace_snapshot(self, members: list[RosterMember]) -> None:
        await self.init_db()
        db = await self._get_db()
        now = datetime.utcnow().isoformat()
        await db.execute("DELETE FROM roster_snapshot")
        for member in members:
            await db.execute(
                """
                INSERT INTO roster_snapshot(
                    character_key, character_id, name, realm_slug, level, class_id,
                    race_id, faction, guild_rank, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member.character_key,
                    member.character_id,
                    member.name,
                    member.realm_slug,
                    member.level,
                    member.class_id,
                    member.race_id,
                    member.faction,
                    member.guild_rank,
                    now,
                ),
            )
        await db.commit()

    async def milestone_exists(self, character_key: str, level: int) -> bool:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT 1 FROM milestone_events WHERE character_key = ? AND level = ?",
            (character_key, level),
        )
        return await cur.fetchone() is not None

    async def record_milestone(self, character_key: str, level: int) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            """
            INSERT OR IGNORE INTO milestone_events(character_key, level, announced_at)
            VALUES (?, ?, ?)
            """,
            (character_key, level, datetime.utcnow().isoformat()),
        )
        await db.commit()

    async def member_count(self) -> int:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("SELECT COUNT(*) FROM roster_snapshot")
        row = await cur.fetchone()
        return row[0] if row else 0

    async def last_scan_at(self) -> str | None:
        return await self.get_setting("last_scan_at")

    async def mark_scanned(self) -> None:
        await self.set_setting("last_scan_at", datetime.utcnow().isoformat())


def parse_roster_member(raw: dict[str, Any]) -> RosterMember | None:
    """Convert a Battle.net roster entry into a stable local record."""
    character = raw.get("character") or {}
    name = character.get("name")
    realm_slug = (character.get("realm") or {}).get("slug")
    level = character.get("level")
    if not name or not realm_slug or level is None:
        return None

    character_id = character.get("id")
    character_key = (
        f"id:{character_id}"
        if character_id is not None
        else f"realm:{realm_slug}:name:{str(name).lower()}"
    )

    return RosterMember(
        character_key=character_key,
        character_id=character_id,
        name=str(name),
        realm_slug=str(realm_slug),
        level=int(level),
        class_id=(character.get("playable_class") or {}).get("id"),
        race_id=(character.get("playable_race") or {}).get("id"),
        faction=(character.get("faction") or {}).get("type") or "",
        guild_rank=raw.get("rank"),
    )
