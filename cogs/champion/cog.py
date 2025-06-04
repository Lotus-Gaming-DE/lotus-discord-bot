import discord
from discord.ext import commands
import aiosqlite
from datetime import datetime
from typing import Optional
import os  # Wird nur für os.makedirs in ChampionData gebraucht

from log_setup import get_logger, create_logged_task

logger = get_logger(__name__)


class ChampionData:
    """
    Verwaltet die SQLite-Datenbank für Champion-Punkte und Historie.
    """

    def __init__(self, db_path: str) -> None:
        """Create a new database helper for the given path."""
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None
        self._init_done = False

    async def init_db(self):
        """Stellt die Datenbankverbindung her und legt Tabellen an."""
        if self.db is None:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self.db = await aiosqlite.connect(self.db_path)

        if self._init_done:
            return
        self._init_done = True

        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS points (
                user_id TEXT PRIMARY KEY,
                total INTEGER NOT NULL
            );
            """
        )
        await self.db.execute(
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
        await self.db.commit()

        logger.info("[ChampionData] SQLite‐Datenbank initialisiert.")

    async def close(self):
        """Schließt die gehaltene Datenbankverbindung."""
        if self.db is not None:
            await self.db.close()
            self.db = None
            self._init_done = False

    async def get_total(self, user_id: str) -> int:
        """Return the current score for a user."""
        await self.init_db()
        cur = await self.db.execute(
            "SELECT total FROM points WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else 0

    async def add_delta(self, user_id: str, delta: int, reason: str) -> int:
        """Change a user's score by ``delta`` and store a history entry."""
        await self.init_db()
        now = datetime.utcnow().isoformat()

        cur = await self.db.execute(
            "SELECT total FROM points WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        current_total = row[0] if row else 0

        new_total = current_total + delta
        if row:
            await self.db.execute(
                "UPDATE points SET total = ? WHERE user_id = ?",
                (new_total, user_id)
            )
        else:
            await self.db.execute(
                "INSERT INTO points(user_id, total) VALUES (?, ?)",
                (user_id, new_total)
            )

        await self.db.execute(
            "INSERT INTO history(user_id, delta, reason, date) VALUES (?, ?, ?, ?)",
            (user_id, delta, reason, now)
        )

        await self.db.commit()

        logger.info(
            f"[ChampionData] {user_id} Punkte geändert um {delta} ({reason}). Neuer Total: {new_total}."
        )
        return new_total

    async def get_history(self, user_id: str, limit: int = 10) -> list[dict]:
        """Return the most recent score changes for a user."""
        await self.init_db()
        cur = await self.db.execute(
            """
            SELECT delta, reason, date
              FROM history
             WHERE user_id = ?
             ORDER BY date DESC
             LIMIT ?
            """,
            (user_id, limit)
        )
        rows = await cur.fetchall()

        return [{"delta": r[0], "reason": r[1], "date": r[2]} for r in rows]

    async def get_leaderboard(self, limit: int = 10, offset: int = 0) -> list[tuple[str, int]]:
        """Return a list of users sorted by score."""
        await self.init_db()
        cur = await self.db.execute(
            """
            SELECT user_id, total
              FROM points
             ORDER BY total DESC
             LIMIT ? OFFSET ?
            """,
            (limit, offset)
        )
        rows = await cur.fetchall()

        return [(r[0], r[1]) for r in rows]

    async def get_rank(self, user_id: str) -> Optional[tuple[int, int]]:
        """Return ``(rank, score)`` for the given user or ``None`` if unknown."""
        await self.init_db()
        cur = await self.db.execute(
            "SELECT total FROM points WHERE user_id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        total = row[0]

        cur = await self.db.execute(
            "SELECT COUNT(*) FROM points WHERE total > ?",
            (total,),
        )
        count_row = await cur.fetchone()
        rank = count_row[0] + 1

        return rank, total


class ChampionCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the cog and load role configuration."""
        self.bot = bot

        db_path = "data/pers/champion/points.db"
        self.data = ChampionData(db_path)

        self.roles = self._load_roles_config()

    def _load_roles_config(self) -> list[tuple[str, int]]:
        """Return the role thresholds sorted descending."""
        role_entries = self.bot.data.get("champion", {}).get("roles", [])
        sorted_roles = sorted(
            [(entry["name"], entry["threshold"]) for entry in role_entries],
            key=lambda x: -x[1]
        )
        return sorted_roles

    def get_current_role(self, score: int) -> Optional[str]:
        """Return the highest role name a user qualifies for."""
        for role_name, threshold in self.roles:
            if score >= threshold:
                return role_name
        return None

    async def update_user_score(self, user_id: int, delta: int, reason: str) -> int:
        """Apply a score change and update the member's role."""
        user_id_str = str(user_id)
        new_total = await self.data.add_delta(user_id_str, delta, reason)

        create_logged_task(
            self._apply_champion_role(user_id_str, new_total), logger
        )

        return new_total

    async def _apply_champion_role(self, user_id_str: str, score: int) -> None:
        """Assign the correct champion role based on the score."""
        # Zugriff auf Guild NUR noch über self.bot.main_guild (Zentral, wie in bot.py gesetzt)
        guild = discord.utils.get(self.bot.guilds, id=self.bot.main_guild.id)
        if not guild:
            logger.warning("[ChampionCog] Guild nicht gefunden.")
            return

        try:
            member = await guild.fetch_member(int(user_id_str))
        except discord.NotFound:
            logger.info(
                f"[ChampionCog] Member {user_id_str} nicht gefunden (vermutlich nicht mehr im Server).")
            return
        except discord.HTTPException as e:
            logger.error(
                f"[ChampionCog] Fehler beim Laden von Member {user_id_str}: {e}", exc_info=True)
            return

        target_role_name = self.get_current_role(score)
        if not target_role_name:
            return

        current_role_names = [r.name for r in member.roles]
        if target_role_name in current_role_names:
            return

        roles_to_remove = []
        for role_name, _ in self.roles:
            if role_name in current_role_names:
                role_obj = discord.utils.get(guild.roles, name=role_name)
                if role_obj:
                    roles_to_remove.append(role_obj)

        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove)
            except discord.Forbidden:
                logger.warning(
                    f"[ChampionCog] Keine Berechtigung, Rollen von {member.display_name} zu entfernen."
                )
            except Exception as e:
                logger.error(
                    f"[ChampionCog] Fehler beim Entfernen von Rollen: {e}", exc_info=True)

        target_role = discord.utils.get(guild.roles, name=target_role_name)
        if target_role:
            try:
                await member.add_roles(target_role)
                logger.info(
                    f"[ChampionCog] Rolle '{target_role_name}' an {member.display_name} vergeben (Score {score})."
                )
            except discord.Forbidden:
                logger.warning(
                    f"[ChampionCog] Keine Berechtigung, Rolle '{target_role_name}' hinzuzufügen."
                )
            except Exception as e:
                logger.error(
                    f"[ChampionCog] Fehler beim Hinzufügen der Rolle: {e}", exc_info=True)
        else:
            logger.warning(
                f"[ChampionCog] Rolle '{target_role_name}' existiert nicht in Discord."
            )
