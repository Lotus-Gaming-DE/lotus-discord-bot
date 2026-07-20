"""SQLite storage for the WoW-Duo (level-partner) feature.

Separate database file from :class:`WoWData` so the duo feature owns its own
schema and migrations, but same on-disk directory. Structure and idioms mirror
``WoWData``: lazy connection, WAL journal, idempotent :meth:`init_db`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiosqlite

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


@dataclass
class DuoSignup:
    discord_user_id: int
    character_key: str
    character_name: str
    realm_slug: str
    time_windows: str
    note: str | None
    post_id: int | None
    created_at: str
    kind: str = "char"  # 'char' (real claimed char) | 'reroll' (roll fresh together)
    self_found: bool = False
    prefs: str = ""  # encoded PLAY_TAGS
    intensity: str | None = None  # INTENSITY key


@dataclass
class DuoTeam:
    team_id: int
    name: str
    thread_id: int | None
    status: str
    created_at: str


@dataclass
class DuoTeamMember:
    team_id: int
    discord_user_id: int
    character_key: str
    character_name: str


class DuoData:
    """SQLite storage for duo signups and teams."""

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
        # One open signup per CHARACTER (PK on character_key) — a player can
        # search with several alts at once. ``post_id`` is the public forum
        # "Sucht Partner" post so we can find the signup back from a button
        # click and delete the post on match.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS duo_signups (
                character_key TEXT PRIMARY KEY,
                discord_user_id INTEGER NOT NULL,
                character_name TEXT NOT NULL,
                realm_slug TEXT NOT NULL,
                time_windows TEXT NOT NULL,
                note TEXT,
                post_id INTEGER,
                created_at TEXT NOT NULL
            )
            """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS duo_teams (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                thread_id INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS duo_team_members (
                team_id INTEGER NOT NULL,
                discord_user_id INTEGER NOT NULL,
                character_key TEXT NOT NULL,
                character_name TEXT NOT NULL,
                PRIMARY KEY(team_id, discord_user_id)
            )
            """)
        # Dedup guard so a duo level-milestone bonus is awarded exactly once
        # per (team, level), even if a scan re-runs.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS duo_milestone_events (
                team_id INTEGER NOT NULL,
                level INTEGER NOT NULL,
                awarded_at TEXT NOT NULL,
                PRIMARY KEY(team_id, level)
            )
            """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS duo_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)
        await self._migrate_signups_pk(db)
        # Additive columns added after the first release. Idempotent — same
        # pattern as WoWData._ensure_column.
        await self._ensure_column(
            db, "duo_signups", "kind", "TEXT NOT NULL DEFAULT 'char'"
        )
        await self._ensure_column(
            db, "duo_signups", "self_found", "INTEGER NOT NULL DEFAULT 0"
        )
        await self._ensure_column(db, "duo_signups", "prefs", "TEXT")
        await self._ensure_column(db, "duo_signups", "intensity", "TEXT")
        await db.commit()
        self._init_done = True
        logger.info("[DuoData] SQLite database initialized.")

    @staticmethod
    async def _ensure_column(
        db: aiosqlite.Connection, table: str, column: str, definition: str
    ) -> None:
        cur = await db.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in await cur.fetchall()}
        if column not in columns:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def _migrate_signups_pk(self, db: aiosqlite.Connection) -> None:
        """Rebuild ``duo_signups`` with a character_key PK if it predates it.

        The first release keyed signups on ``discord_user_id`` (one search per
        player). Multiple alts need one search per character, so the PK moved
        to ``character_key``. ``CREATE TABLE IF NOT EXISTS`` above is a no-op on
        an existing old table, so we detect the old primary key here and copy
        the rows across.
        """
        cur = await db.execute("PRAGMA table_info(duo_signups)")
        cols = await cur.fetchall()
        pk_cols = [c[1] for c in cols if c[5]]
        if not cols or pk_cols == ["character_key"]:
            return
        await db.execute("ALTER TABLE duo_signups RENAME TO duo_signups_old")
        await db.execute("""
            CREATE TABLE duo_signups (
                character_key TEXT PRIMARY KEY,
                discord_user_id INTEGER NOT NULL,
                character_name TEXT NOT NULL,
                realm_slug TEXT NOT NULL,
                time_windows TEXT NOT NULL,
                note TEXT,
                post_id INTEGER,
                created_at TEXT NOT NULL
            )
            """)
        await db.execute("""
            INSERT OR IGNORE INTO duo_signups (
                character_key, discord_user_id, character_name, realm_slug,
                time_windows, note, post_id, created_at
            )
            SELECT character_key, discord_user_id, character_name, realm_slug,
                   time_windows, note, post_id, created_at
              FROM duo_signups_old
            """)
        await db.execute("DROP TABLE duo_signups_old")
        logger.info("[DuoData] duo_signups auf character_key-PK migriert.")

    async def get_setting(self, key: str) -> str | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("SELECT value FROM duo_settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            """
            INSERT INTO duo_settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await db.commit()

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
            self._init_done = False

    # ---- signups ----

    async def upsert_signup(
        self,
        discord_user_id: int,
        character_key: str,
        character_name: str,
        realm_slug: str,
        time_windows: str,
        note: str | None,
        *,
        kind: str = "char",
        self_found: bool = False,
        prefs: str = "",
        intensity: str | None = None,
    ) -> DuoSignup:
        """Create or replace the open signup for a single character.

        ``post_id`` is reset to NULL — the caller creates the forum post
        afterwards and records its id via :meth:`set_signup_post`.
        """
        await self.init_db()
        db = await self._get_db()
        now = datetime.utcnow().isoformat()
        await db.execute(
            """
            INSERT INTO duo_signups(
                character_key, discord_user_id, character_name, realm_slug,
                time_windows, note, post_id, created_at,
                kind, self_found, prefs, intensity
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
            ON CONFLICT(character_key) DO UPDATE SET
                discord_user_id = excluded.discord_user_id,
                character_name = excluded.character_name,
                realm_slug = excluded.realm_slug,
                time_windows = excluded.time_windows,
                note = excluded.note,
                post_id = NULL,
                created_at = excluded.created_at,
                kind = excluded.kind,
                self_found = excluded.self_found,
                prefs = excluded.prefs,
                intensity = excluded.intensity
            """,
            (
                character_key,
                discord_user_id,
                character_name,
                realm_slug,
                time_windows,
                (note or None),
                now,
                kind,
                int(bool(self_found)),
                (prefs or None),
                intensity,
            ),
        )
        await db.commit()
        signup = await self.get_signup(character_key)
        if signup is None:  # pragma: no cover - defensive
            raise RuntimeError("Signup creation failed")
        return signup

    async def set_signup_post(self, character_key: str, post_id: int) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            "UPDATE duo_signups SET post_id = ? WHERE character_key = ?",
            (post_id, character_key),
        )
        await db.commit()

    async def get_signup(self, character_key: str) -> DuoSignup | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT discord_user_id, character_key, character_name, realm_slug,
                   time_windows, note, post_id, created_at,
                   kind, self_found, prefs, intensity
              FROM duo_signups WHERE character_key = ?
            """,
            (character_key,),
        )
        row = await cur.fetchone()
        return _signup_from_row(row) if row else None

    async def get_signup_by_post(self, post_id: int) -> DuoSignup | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT discord_user_id, character_key, character_name, realm_slug,
                   time_windows, note, post_id, created_at,
                   kind, self_found, prefs, intensity
              FROM duo_signups WHERE post_id = ?
            """,
            (post_id,),
        )
        row = await cur.fetchone()
        return _signup_from_row(row) if row else None

    async def remove_signup(self, character_key: str) -> bool:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "DELETE FROM duo_signups WHERE character_key = ?",
            (character_key,),
        )
        await db.commit()
        return cur.rowcount > 0

    async def signups_for_user(self, discord_user_id: int) -> list[DuoSignup]:
        """All open signups belonging to a player (one per searching alt)."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT discord_user_id, character_key, character_name, realm_slug,
                   time_windows, note, post_id, created_at,
                   kind, self_found, prefs, intensity
              FROM duo_signups WHERE discord_user_id = ?
             ORDER BY created_at
            """,
            (discord_user_id,),
        )
        rows = await cur.fetchall()
        return [_signup_from_row(row) for row in rows]

    async def list_signups(self, exclude_user_id: int | None = None) -> list[DuoSignup]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("""
            SELECT discord_user_id, character_key, character_name, realm_slug,
                   time_windows, note, post_id, created_at,
                   kind, self_found, prefs, intensity
              FROM duo_signups
             ORDER BY created_at
            """)
        rows = await cur.fetchall()
        signups = [_signup_from_row(row) for row in rows]
        if exclude_user_id is not None:
            signups = [s for s in signups if s.discord_user_id != exclude_user_id]
        return signups

    async def signup_count(self) -> int:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("SELECT COUNT(*) FROM duo_signups")
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def stale_signups(self, cutoff_iso: str) -> list[DuoSignup]:
        """Open signups created before ``cutoff_iso`` (for auto-expiry)."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT discord_user_id, character_key, character_name, realm_slug,
                   time_windows, note, post_id, created_at,
                   kind, self_found, prefs, intensity
              FROM duo_signups
             WHERE created_at < ?
             ORDER BY created_at
            """,
            (cutoff_iso,),
        )
        rows = await cur.fetchall()
        return [_signup_from_row(row) for row in rows]

    # ---- teams ----

    async def create_team(
        self,
        name: str,
        thread_id: int | None,
        members: list[tuple[int, str, str]],
    ) -> DuoTeam:
        """Create an active team with its members.

        ``members`` items are ``(discord_user_id, character_key, character_name)``.
        """
        await self.init_db()
        db = await self._get_db()
        now = datetime.utcnow().isoformat()
        cur = await db.execute(
            """
            INSERT INTO duo_teams(name, thread_id, status, created_at)
            VALUES (?, ?, 'active', ?)
            """,
            (name, thread_id, now),
        )
        team_id = cur.lastrowid
        for user_id, character_key, character_name in members:
            await db.execute(
                """
                INSERT INTO duo_team_members(
                    team_id, discord_user_id, character_key, character_name
                ) VALUES (?, ?, ?, ?)
                """,
                (team_id, user_id, character_key, character_name),
            )
        await db.commit()
        team = await self.get_team(int(team_id))
        if team is None:  # pragma: no cover - defensive
            raise RuntimeError("Team creation failed")
        return team

    async def set_team_thread(self, team_id: int, thread_id: int) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            "UPDATE duo_teams SET thread_id = ? WHERE team_id = ?",
            (thread_id, team_id),
        )
        await db.commit()

    async def get_team(self, team_id: int) -> DuoTeam | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT team_id, name, thread_id, status, created_at
              FROM duo_teams WHERE team_id = ?
            """,
            (team_id,),
        )
        row = await cur.fetchone()
        return _team_from_row(row) if row else None

    async def get_team_by_thread(self, thread_id: int) -> DuoTeam | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT team_id, name, thread_id, status, created_at
              FROM duo_teams WHERE thread_id = ?
            """,
            (thread_id,),
        )
        row = await cur.fetchone()
        return _team_from_row(row) if row else None

    async def active_team_for_user(self, discord_user_id: int) -> DuoTeam | None:
        """The active (or mourning) team the user currently belongs to."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT t.team_id, t.name, t.thread_id, t.status, t.created_at
              FROM duo_teams t
              JOIN duo_team_members m ON m.team_id = t.team_id
             WHERE m.discord_user_id = ? AND t.status != 'disbanded'
             ORDER BY t.created_at DESC
             LIMIT 1
            """,
            (discord_user_id,),
        )
        row = await cur.fetchone()
        return _team_from_row(row) if row else None

    async def active_teams_for_user(self, discord_user_id: int) -> list[DuoTeam]:
        """All active/mourning teams a player belongs to (one per alt)."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT t.team_id, t.name, t.thread_id, t.status, t.created_at
              FROM duo_teams t
              JOIN duo_team_members m ON m.team_id = t.team_id
             WHERE m.discord_user_id = ? AND t.status != 'disbanded'
             ORDER BY t.created_at
            """,
            (discord_user_id,),
        )
        rows = await cur.fetchall()
        return [_team_from_row(row) for row in rows]

    async def active_team_by_character(self, character_key: str) -> DuoTeam | None:
        """The active/mourning team a given character currently plays in."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT t.team_id, t.name, t.thread_id, t.status, t.created_at
              FROM duo_teams t
              JOIN duo_team_members m ON m.team_id = t.team_id
             WHERE m.character_key = ? AND t.status != 'disbanded'
             ORDER BY t.created_at DESC
             LIMIT 1
            """,
            (character_key,),
        )
        row = await cur.fetchone()
        return _team_from_row(row) if row else None

    async def team_members(self, team_id: int) -> list[DuoTeamMember]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT team_id, discord_user_id, character_key, character_name
              FROM duo_team_members WHERE team_id = ?
             ORDER BY discord_user_id
            """,
            (team_id,),
        )
        rows = await cur.fetchall()
        return [_member_from_row(row) for row in rows]

    async def set_team_status(self, team_id: int, status: str) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            "UPDATE duo_teams SET status = ? WHERE team_id = ?",
            (status, team_id),
        )
        await db.commit()

    async def set_team_name(self, team_id: int, name: str) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            "UPDATE duo_teams SET name = ? WHERE team_id = ?",
            (name, team_id),
        )
        await db.commit()

    async def swap_member_character(
        self,
        team_id: int,
        discord_user_id: int,
        character_key: str,
        character_name: str,
    ) -> None:
        """Point a team member at a freshly-dedicated character (HC revive)."""
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            """
            UPDATE duo_team_members
               SET character_key = ?, character_name = ?
             WHERE team_id = ? AND discord_user_id = ?
            """,
            (character_key, character_name, team_id, discord_user_id),
        )
        await db.commit()

    async def disband_team(self, team_id: int) -> None:
        """Mark a team disbanded (rows kept for history)."""
        await self.set_team_status(team_id, "disbanded")

    async def used_team_names(self) -> set[str]:
        """All non-disbanded team names, to avoid handing out a duplicate."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("SELECT name FROM duo_teams WHERE status != 'disbanded'")
        rows = await cur.fetchall()
        return {str(row[0]) for row in rows}

    async def active_teams(self) -> list[DuoTeam]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute("""
            SELECT team_id, name, thread_id, status, created_at
              FROM duo_teams WHERE status != 'disbanded'
             ORDER BY created_at
            """)
        rows = await cur.fetchall()
        return [_team_from_row(row) for row in rows]

    # ---- duo milestone dedup ----

    async def duo_milestone_exists(self, team_id: int, level: int) -> bool:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT 1 FROM duo_milestone_events WHERE team_id = ? AND level = ?",
            (team_id, int(level)),
        )
        return await cur.fetchone() is not None

    async def record_duo_milestone(self, team_id: int, level: int) -> bool:
        """Reserve the duo-milestone slot; ``True`` only on the first call."""
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            INSERT OR IGNORE INTO duo_milestone_events(team_id, level, awarded_at)
            VALUES (?, ?, ?)
            """,
            (team_id, int(level), datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cur.rowcount > 0


def _signup_from_row(row: tuple[Any, ...]) -> DuoSignup:
    return DuoSignup(
        discord_user_id=row[0],
        character_key=row[1],
        character_name=row[2],
        realm_slug=row[3],
        time_windows=row[4],
        note=row[5],
        post_id=row[6],
        created_at=row[7],
        kind=row[8] if len(row) > 8 and row[8] else "char",
        self_found=bool(row[9]) if len(row) > 9 else False,
        prefs=(row[10] or "") if len(row) > 10 else "",
        intensity=row[11] if len(row) > 11 else None,
    )


def _team_from_row(row: tuple[Any, ...]) -> DuoTeam:
    return DuoTeam(
        team_id=row[0],
        name=row[1],
        thread_id=row[2],
        status=row[3],
        created_at=row[4],
    )


def _member_from_row(row: tuple[Any, ...]) -> DuoTeamMember:
    return DuoTeamMember(
        team_id=row[0],
        discord_user_id=row[1],
        character_key=row[2],
        character_name=row[3],
    )
