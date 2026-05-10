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
    is_ghost: bool = False


@dataclass
class CharacterClaim:
    character_key: str
    character_name: str
    realm_slug: str
    discord_user_id: int
    status: str
    claimed_at: str
    verified_at: str | None
    verified_by: int | None
    review_message_id: int | None


@dataclass
class CharacterProfession:
    character_key: str
    character_name: str
    realm_slug: str
    discord_user_id: int
    profession_id: str
    skill_level: int
    specialization: str | None
    updated_at: str


@dataclass
class CharacterKnownRecipe:
    character_key: str
    character_name: str
    realm_slug: str
    discord_user_id: int
    spell_id: str
    profession_id: str
    learned_at: str


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
                is_ghost INTEGER NOT NULL DEFAULT 0,
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
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS death_events (
                character_key TEXT PRIMARY KEY,
                recorded_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS character_claims (
                character_key TEXT PRIMARY KEY,
                character_name TEXT NOT NULL,
                realm_slug TEXT NOT NULL,
                discord_user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                claimed_at TEXT NOT NULL,
                verified_at TEXT,
                verified_by INTEGER,
                review_message_id INTEGER
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS character_professions (
                character_key TEXT NOT NULL,
                profession_id TEXT NOT NULL,
                skill_level INTEGER NOT NULL,
                specialization TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(character_key, profession_id)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS character_known_recipes (
                character_key TEXT NOT NULL,
                spell_id TEXT NOT NULL,
                profession_id TEXT NOT NULL,
                learned_at TEXT NOT NULL,
                PRIMARY KEY(character_key, spell_id)
            )
            """
        )
        await self._ensure_column(
            "roster_snapshot", "is_ghost", "INTEGER NOT NULL DEFAULT 0"
        )
        await db.commit()
        self._init_done = True
        logger.info("[WoWData] SQLite database initialized.")

    async def _ensure_column(self, table: str, column: str, definition: str) -> None:
        db = await self._get_db()
        cur = await db.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in await cur.fetchall()}
        if column not in columns:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

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
                   race_id, faction, guild_rank, is_ghost
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
                is_ghost=bool(row[9]),
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
                    race_id, faction, guild_rank, is_ghost, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(member.is_ghost),
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

    async def death_exists(self, character_key: str) -> bool:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            "SELECT 1 FROM death_events WHERE character_key = ?",
            (character_key,),
        )
        return await cur.fetchone() is not None

    async def record_death(self, character_key: str) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            """
            INSERT OR IGNORE INTO death_events(character_key, recorded_at)
            VALUES (?, ?)
            """,
            (character_key, datetime.utcnow().isoformat()),
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

    async def find_roster_member_by_name(self, name: str) -> RosterMember | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT character_key, character_id, name, realm_slug, level, class_id,
                   race_id, faction, guild_rank, is_ghost
              FROM roster_snapshot
             WHERE lower(name) = lower(?)
             LIMIT 1
            """,
            (name.strip(),),
        )
        row = await cur.fetchone()
        if not row:
            return None
        return RosterMember(
            character_key=row[0],
            character_id=row[1],
            name=row[2],
            realm_slug=row[3],
            level=row[4],
            class_id=row[5],
            race_id=row[6],
            faction=row[7] or "",
            guild_rank=row[8],
            is_ghost=bool(row[9]),
        )

    async def get_claim(self, character_key: str) -> CharacterClaim | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT character_key, character_name, realm_slug, discord_user_id, status,
                   claimed_at, verified_at, verified_by, review_message_id
              FROM character_claims
             WHERE character_key = ?
            """,
            (character_key,),
        )
        row = await cur.fetchone()
        return _claim_from_row(row) if row else None

    async def get_claim_by_name(self, name: str) -> CharacterClaim | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT character_key, character_name, realm_slug, discord_user_id, status,
                   claimed_at, verified_at, verified_by, review_message_id
              FROM character_claims
             WHERE lower(character_name) = lower(?)
             LIMIT 1
            """,
            (name.strip(),),
        )
        row = await cur.fetchone()
        return _claim_from_row(row) if row else None

    async def create_claim(
        self, member: RosterMember, discord_user_id: int
    ) -> tuple[CharacterClaim, bool]:
        await self.init_db()
        existing = await self.get_claim(member.character_key)
        if existing:
            return existing, False

        db = await self._get_db()
        now = datetime.utcnow().isoformat()
        await db.execute(
            """
            INSERT INTO character_claims(
                character_key, character_name, realm_slug, discord_user_id, status,
                claimed_at, verified_at, verified_by, review_message_id
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
            """,
            (
                member.character_key,
                member.name,
                member.realm_slug,
                discord_user_id,
                "unverified",
                now,
            ),
        )
        await db.commit()
        claim = await self.get_claim(member.character_key)
        if claim is None:  # pragma: no cover - defensive
            raise RuntimeError("Claim creation failed")
        return claim, True

    async def set_claim_review_message(
        self, character_key: str, review_message_id: int
    ) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            """
            UPDATE character_claims
               SET review_message_id = ?
             WHERE character_key = ?
            """,
            (review_message_id, character_key),
        )
        await db.commit()

    async def verify_claim(self, character_key: str, reviewer_id: int) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            """
            UPDATE character_claims
               SET status = 'verified', verified_at = ?, verified_by = ?
             WHERE character_key = ?
            """,
            (datetime.utcnow().isoformat(), reviewer_id, character_key),
        )
        await db.commit()

    async def get_claim_by_review_message(
        self, review_message_id: int
    ) -> CharacterClaim | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT character_key, character_name, realm_slug, discord_user_id, status,
                   claimed_at, verified_at, verified_by, review_message_id
              FROM character_claims
             WHERE review_message_id = ?
            """,
            (review_message_id,),
        )
        row = await cur.fetchone()
        return _claim_from_row(row) if row else None

    async def remove_claim(self, character_key: str) -> None:
        await self.init_db()
        db = await self._get_db()
        await db.execute(
            "DELETE FROM character_claims WHERE character_key = ?",
            (character_key,),
        )
        await db.commit()

    async def release_claim(self, character_key: str, discord_user_id: int) -> bool:
        claim = await self.get_claim(character_key)
        if not claim or claim.discord_user_id != discord_user_id:
            return False
        await self.remove_claim(character_key)
        return True

    async def claims_for_user(self, discord_user_id: int) -> list[CharacterClaim]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT character_key, character_name, realm_slug, discord_user_id, status,
                   claimed_at, verified_at, verified_by, review_message_id
              FROM character_claims
             WHERE discord_user_id = ?
             ORDER BY lower(character_name)
            """,
            (discord_user_id,),
        )
        rows = await cur.fetchall()
        return [_claim_from_row(row) for row in rows]

    async def list_claims(self, status: str = "all") -> list[CharacterClaim]:
        await self.init_db()
        db = await self._get_db()
        query = """
            SELECT character_key, character_name, realm_slug, discord_user_id, status,
                   claimed_at, verified_at, verified_by, review_message_id
              FROM character_claims
        """
        params: tuple[str, ...] = ()
        if status != "all":
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY lower(character_name)"
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [_claim_from_row(row) for row in rows]

    async def set_character_profession(
        self,
        claim: CharacterClaim,
        profession_id: str,
        skill_level: int,
        specialization: str | None = None,
    ) -> CharacterProfession:
        if skill_level < 1 or skill_level > 300:
            raise ValueError("skill_level must be between 1 and 300")
        await self.init_db()
        db = await self._get_db()
        now = datetime.utcnow().isoformat()
        cleaned_specialization = (
            specialization.strip()
            if specialization and specialization.strip()
            else None
        )
        await db.execute(
            """
            INSERT INTO character_professions(
                character_key, profession_id, skill_level, specialization, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(character_key, profession_id)
            DO UPDATE SET
                skill_level = excluded.skill_level,
                specialization = excluded.specialization,
                updated_at = excluded.updated_at
            """,
            (
                claim.character_key,
                profession_id,
                skill_level,
                cleaned_specialization,
                now,
            ),
        )
        await db.commit()
        profession = await self.get_character_profession(
            claim.character_key, profession_id
        )
        if profession is None:  # pragma: no cover - defensive
            raise RuntimeError("Profession update failed")
        return profession

    async def get_character_profession(
        self, character_key: str, profession_id: str
    ) -> CharacterProfession | None:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT c.character_key, c.character_name, c.realm_slug, c.discord_user_id,
                   p.profession_id, p.skill_level, p.specialization, p.updated_at
              FROM character_professions p
              JOIN character_claims c ON c.character_key = p.character_key
             WHERE p.character_key = ? AND p.profession_id = ?
            """,
            (character_key, profession_id),
        )
        row = await cur.fetchone()
        return _profession_from_row(row) if row else None

    async def remove_character_profession(
        self, character_key: str, profession_id: str
    ) -> bool:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            DELETE FROM character_professions
             WHERE character_key = ? AND profession_id = ?
            """,
            (character_key, profession_id),
        )
        await db.commit()
        return cur.rowcount > 0

    async def professions_for_user(
        self, discord_user_id: int
    ) -> list[CharacterProfession]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT c.character_key, c.character_name, c.realm_slug, c.discord_user_id,
                   p.profession_id, p.skill_level, p.specialization, p.updated_at
              FROM character_professions p
              JOIN character_claims c ON c.character_key = p.character_key
             WHERE c.discord_user_id = ?
             ORDER BY lower(c.character_name), p.profession_id
            """,
            (discord_user_id,),
        )
        rows = await cur.fetchall()
        return [_profession_from_row(row) for row in rows]

    async def list_professions(
        self, profession_id: str | None = None
    ) -> list[CharacterProfession]:
        await self.init_db()
        db = await self._get_db()
        query = """
            SELECT c.character_key, c.character_name, c.realm_slug, c.discord_user_id,
                   p.profession_id, p.skill_level, p.specialization, p.updated_at
              FROM character_professions p
              JOIN character_claims c ON c.character_key = p.character_key
        """
        params: tuple[str, ...] = ()
        if profession_id:
            query += " WHERE p.profession_id = ?"
            params = (profession_id,)
        query += (
            " ORDER BY p.profession_id, p.skill_level DESC, lower(c.character_name)"
        )
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [_profession_from_row(row) for row in rows]

    async def professions_for_character(
        self, character_key: str
    ) -> list[CharacterProfession]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT c.character_key, c.character_name, c.realm_slug, c.discord_user_id,
                   p.profession_id, p.skill_level, p.specialization, p.updated_at
              FROM character_professions p
              JOIN character_claims c ON c.character_key = p.character_key
             WHERE p.character_key = ?
             ORDER BY p.profession_id
            """,
            (character_key,),
        )
        rows = await cur.fetchall()
        return [_profession_from_row(row) for row in rows]

    async def find_crafters(
        self, profession_id: str, minimum_skill: int
    ) -> list[CharacterProfession]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT c.character_key, c.character_name, c.realm_slug, c.discord_user_id,
                   p.profession_id, p.skill_level, p.specialization, p.updated_at
              FROM character_professions p
              JOIN character_claims c ON c.character_key = p.character_key
             WHERE p.profession_id = ? AND p.skill_level >= ?
             ORDER BY p.skill_level DESC, lower(c.character_name)
            """,
            (profession_id, minimum_skill),
        )
        rows = await cur.fetchall()
        return [_profession_from_row(row) for row in rows]

    async def add_known_recipes(
        self,
        character_key: str,
        profession_id: str,
        spell_ids: list[str],
    ) -> int:
        if not spell_ids:
            return 0
        await self.init_db()
        db = await self._get_db()
        now = datetime.utcnow().isoformat()
        before = db.total_changes
        await db.executemany(
            """
            INSERT OR IGNORE INTO character_known_recipes(
                character_key, spell_id, profession_id, learned_at
            ) VALUES (?, ?, ?, ?)
            """,
            [(character_key, spell_id, profession_id, now) for spell_id in spell_ids],
        )
        await db.commit()
        return db.total_changes - before

    async def remove_known_recipe(self, character_key: str, spell_id: str) -> bool:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            DELETE FROM character_known_recipes
             WHERE character_key = ? AND spell_id = ?
            """,
            (character_key, spell_id),
        )
        await db.commit()
        return cur.rowcount > 0

    async def known_recipe_spell_ids(self, character_key: str) -> set[str]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT spell_id
              FROM character_known_recipes
             WHERE character_key = ?
            """,
            (character_key,),
        )
        rows = await cur.fetchall()
        return {str(row[0]) for row in rows}

    async def known_recipes_for_character(
        self, character_key: str
    ) -> list[CharacterKnownRecipe]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT c.character_key, c.character_name, c.realm_slug, c.discord_user_id,
                   r.spell_id, r.profession_id, r.learned_at
              FROM character_known_recipes r
              JOIN character_claims c ON c.character_key = r.character_key
             WHERE r.character_key = ?
             ORDER BY r.profession_id, r.spell_id
            """,
            (character_key,),
        )
        rows = await cur.fetchall()
        return [_known_recipe_from_row(row) for row in rows]

    async def find_crafters_with_known_recipe(
        self,
        profession_id: str,
        minimum_skill: int,
        spell_id: str,
    ) -> list[CharacterProfession]:
        await self.init_db()
        db = await self._get_db()
        cur = await db.execute(
            """
            SELECT c.character_key, c.character_name, c.realm_slug, c.discord_user_id,
                   p.profession_id, p.skill_level, p.specialization, p.updated_at
              FROM character_professions p
              JOIN character_claims c ON c.character_key = p.character_key
              JOIN character_known_recipes r
                ON r.character_key = p.character_key
               AND r.spell_id = ?
             WHERE p.profession_id = ? AND p.skill_level >= ?
             ORDER BY p.skill_level DESC, lower(c.character_name)
            """,
            (spell_id, profession_id, minimum_skill),
        )
        rows = await cur.fetchall()
        return [_profession_from_row(row) for row in rows]


def _claim_from_row(row: tuple[Any, ...]) -> CharacterClaim:
    return CharacterClaim(
        character_key=row[0],
        character_name=row[1],
        realm_slug=row[2],
        discord_user_id=row[3],
        status=row[4],
        claimed_at=row[5],
        verified_at=row[6],
        verified_by=row[7],
        review_message_id=row[8],
    )


def _profession_from_row(row: tuple[Any, ...]) -> CharacterProfession:
    return CharacterProfession(
        character_key=row[0],
        character_name=row[1],
        realm_slug=row[2],
        discord_user_id=row[3],
        profession_id=row[4],
        skill_level=row[5],
        specialization=row[6],
        updated_at=row[7],
    )


def _known_recipe_from_row(row: tuple[Any, ...]) -> CharacterKnownRecipe:
    return CharacterKnownRecipe(
        character_key=row[0],
        character_name=row[1],
        realm_slug=row[2],
        discord_user_id=row[3],
        spell_id=row[4],
        profession_id=row[5],
        learned_at=row[6],
    )


def parse_roster_member(raw: dict[str, Any]) -> RosterMember | None:
    """Convert a Battle.net roster entry into a stable local record."""
    character = raw.get("character") or {}
    name = character.get("name")
    realm_slug = (character.get("realm") or {}).get("slug")
    level = character.get("level")
    if not name or not realm_slug or level is None:
        return None

    character_id = character.get("id")
    is_ghost = bool(character.get("is_ghost") or raw.get("is_ghost"))
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
        is_ghost=is_ghost,
    )
