# cogs/champion/cog.py

import discord
from discord.ext import commands
import os
import json
import aiosqlite  # Muss in requirements.txt stehen: aiosqlite>=0.18.0
from datetime import datetime
from typing import Optional

import logging
logger = logging.getLogger(__name__)  # z. B. "cogs.champion.cog"


class ChampionData:
    """
    Verwaltet die SQLite-Datenbank für Champion-Punkte und Historie.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_done = False

    async def init_db(self):
        """
        Legt Tabellen an, falls sie noch nicht existieren.
        Wird nur einmal pro Lauf ausgeführt.
        """
        if self._init_done:
            return
        self._init_done = True

        # Sicherstellen, dass der Ordner existiert
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            # Tabelle "points": speichert user_id + Gesamt-Punkte
            await db.execute("""
                CREATE TABLE IF NOT EXISTS points (
                    user_id TEXT PRIMARY KEY,
                    total INTEGER NOT NULL
                );
            """)
            # Tabelle "history": jede Änderung (delta, reason, timestamp)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    date TEXT NOT NULL
                );
            """)
            await db.commit()

        logger.info("[ChampionData] SQLite‐Datenbank initialisiert.")

    async def get_total(self, user_id: str) -> int:
        """
        Liefert die aktuelle Gesamtpunktzahl eines Users (oder 0, wenn neu).
        """
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT total FROM points WHERE user_id = ?", (user_id,)
            )
            row = await cur.fetchone()
            return row[0] if row else 0

    async def add_delta(self, user_id: str, delta: int, reason: str) -> int:
        """
        Addiert (oder subtrahiert) delta zur Punktzahl des Users
        und speichert das Ereignis in "history". Gibt die neue Total zurück.
        """
        await self.init_db()
        now = datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            # 1) Alten Gesamtwert lesen (falls vorhanden)
            cur = await db.execute(
                "SELECT total FROM points WHERE user_id = ?", (user_id,)
            )
            row = await cur.fetchone()
            current_total = row[0] if row else 0

            # 2) Neuen Gesamtwert berechnen
            new_total = current_total + delta
            if row:
                # Update existierender Nutzer
                await db.execute(
                    "UPDATE points SET total = ? WHERE user_id = ?",
                    (new_total, user_id)
                )
            else:
                # Neuer Nutzer einfügen
                await db.execute(
                    "INSERT INTO points(user_id, total) VALUES (?, ?)",
                    (user_id, new_total)
                )

            # 3) Historieneintrag hinzufügen
            await db.execute(
                "INSERT INTO history(user_id, delta, reason, date) VALUES (?, ?, ?, ?)",
                (user_id, delta, reason, now)
            )

            await db.commit()

        logger.info(
            f"[ChampionData] {user_id} Punkte geändert um {delta} ({reason}). Neuer Total: {new_total}."
        )
        return new_total

    async def get_history(self, user_id: str, limit: int = 10) -> list[dict]:
        """
        Liefert die letzten 'limit' History‐Einträge (neueste zuerst).
        """
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
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
        """
        Liefert eine Liste von (user_id, total), sortiert nach total DESC,
        maximal 'limit' Einträge beginnend bei 'offset'.
        """
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
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


class ChampionCog(commands.Cog):
    """
    Kernelement: Lädt Rollen-Konfiguration und verwaltet Punktänderungen.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Pfad zur SQLite-Datei (Railway-Volume ist auf /app/data/champion gemountet)
        db_path = "data/champion/points.db"
        self.data = ChampionData(db_path)

        # Rollen‐Konfiguration aus roles.json
        self.roles = self._load_roles_config()

    def _load_roles_config(self) -> list[tuple[str, int]]:
        """
        Liest data/champion/roles.json ein und sortiert nach threshold absteigend.
        Falls roles.json fehlt, fallback zu einer festen Liste.
        """
        config_path = "data/champion/roles.json"
        if not os.path.exists(config_path):
            # Fallback-Liste
            return [
                ("Ultimate Champion", 750),
                ("Epic Champion", 500),
                ("Renowned Champion", 300),
                ("Seasoned Champion", 150),
                ("Emerging Champion", 50)
            ]

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sorted_roles = sorted(
            [(entry["name"], entry["threshold"]) for entry in data],
            key=lambda x: -x[1]
        )
        return sorted_roles

    def get_current_role(self, score: int) -> Optional[str]:
        """
        Welche Rolle passt zur Punktzahl 'score'?
        Gibt den ersten Rollenname zurück, bei dem score >= threshold.
        """
        for role_name, threshold in self.roles:
            if score >= threshold:
                return role_name
        return None

    async def update_user_score(self, user_id: int, delta: int, reason: str) -> int:
        """
        Ändert die Punktzahl des Users um 'delta', speichert in DB
        und startet asynchron Rollenvergabe.
        Gibt neue Gesamtpunktzahl zurück.
        """
        user_id_str = str(user_id)
        new_total = await self.data.add_delta(user_id_str, delta, reason)

        # Asynchron Rollenupdate auslösen (ohne await)
        self.bot.loop.create_task(
            self._apply_champion_role(user_id_str, new_total)
        )

        return new_total

    async def _apply_champion_role(self, user_id_str: str, score: int):
        """
        Vergibt bzw. entfernt Champion-Rollen in Discord, basierend auf 'score'.
        """
        guild_id = int(os.getenv("server_id"))
        guild = discord.utils.get(self.bot.guilds, id=guild_id)
        if not guild:
            logger.warning("[ChampionCog] Guild nicht gefunden.")
            return

        member = guild.get_member(int(user_id_str))
        if not member:
            logger.info(f"[ChampionCog] Member {user_id_str} nicht im Server.")
            return

        # Zielrolle ermitteln
        target_role_name = self.get_current_role(score)
        if not target_role_name:
            # Unterhalb unterster Schwelle: keine Rolle
            return

        current_role_names = [r.name for r in member.roles]
        if target_role_name in current_role_names:
            return  # User hat bereits die richtige Rolle

        # Alte Champion-Rollen entfernen, falls vorhanden
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

        # Neue Rolle hinzufügen
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
