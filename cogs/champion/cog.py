# cogs/champion/cog.py

import os
import discord
import logging
import aiosqlite
import json
from datetime import datetime
from typing import Optional

from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)  # cogs.champion.cog

# ──────────────────────────────────────────────────────────────────────────────
# Zuerst brauchen wir die Datenklasse für SQLite:


class ChampionData:
    """
    Verwal­tet eine SQLite‐Datenbank, speichert Gesamt‐Punkte und Historie.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_done = False

    async def init_db(self):
        """
        Legt beim ersten Aufruf die nötigen Tabellen AUSSCHLIESSLICH
        dann an, wenn sie noch nicht existieren.
        """
        if self._init_done:
            return
        self._init_done = True

        # Verzeichnis sicherstellen (Railway‐Volume liegt unter /app/data/champion)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            # Tabelle für Gesamtpunkte
            await db.execute("""
                CREATE TABLE IF NOT EXISTS points (
                    user_id TEXT PRIMARY KEY,
                    total INTEGER NOT NULL
                );
            """)
            # Tabelle für History (jede Änderung dokumentieren)
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
        Gibt die aktuelle Gesamtpunktzahl eines Users zurück (oder 0, falls nicht vorhanden).
        """
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT total FROM points WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            return row[0] if row else 0

    async def add_delta(self, user_id: str, delta: int, reason: str) -> int:
        """
        Addiert (oder subtrahiert) delta zur Gesamtpunktzahl eines Users
        und speichert das Ereignis in der History. Gibt anschließend die neue Gesamtpunktzahl zurück.
        """
        await self.init_db()
        now = datetime.utcnow().isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            # 1) Alten Gesamtwert lesen
            cur = await db.execute("SELECT total FROM points WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
            current_total = row[0] if row else 0

            # 2) Neuen Gesamtwert berechnen
            new_total = current_total + delta
            if row:
                # Benutzer existiert: Update
                await db.execute("UPDATE points SET total = ? WHERE user_id = ?", (new_total, user_id))
            else:
                # Neuer Benutzer: Insert
                await db.execute("INSERT INTO points(user_id, total) VALUES (?, ?)", (user_id, new_total))

            # 3) Historieneintrag
            await db.execute(
                "INSERT INTO history(user_id, delta, reason, date) VALUES (?, ?, ?, ?)",
                (user_id, delta, reason, now)
            )

            await db.commit()

        logger.info(
            f"[ChampionData] {user_id} Punkte geändert um {delta} ({reason}). Neuer Gesamtwert: {new_total}.")
        return new_total

    async def get_history(self, user_id: str, limit: int = 10) -> list[dict]:
        """
        Liefert die letzten `limit` Einträge aus der History‐Tabelle (neueste zuerst).
        """
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT delta, reason, date FROM history WHERE user_id = ? ORDER BY date DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cur.fetchall()
        return [{"delta": r[0], "reason": r[1], "date": r[2]} for r in rows]

    async def get_leaderboard(self, limit: int = 10, offset: int = 0) -> list[tuple[str, int]]:
        """
        Liefert eine Liste von (user_id, total) geordnet nach total DESC,
        mit maximal `limit` Einträgen ab `offset`.
        """
        await self.init_db()
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT user_id, total FROM points ORDER BY total DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = await cur.fetchall()
        return [(r[0], r[1]) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Rollen‐Konfiguration laden wir aus roles.json
def load_roles_config() -> list[tuple[str, int]]:
    """
    Liest die Datei 'data/champion/roles.json' ein und gibt
    eine Liste von (Rollenname, Schwellenwert) zurück, absteigend sortiert.
    """
    config_path = "data/champion/roles.json"
    if not os.path.exists(config_path):
        # Fallback-Liste, falls roles.json fehlt
        return [
            ("Ultimate Champion", 750),
            ("Epic Champion", 500),
            ("Renowned Champion", 300),
            ("Seasoned Champion", 150),
            ("Emerging Champion", 50)
        ]
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Sortiere absteigend nach threshold
    sorted_roles = sorted(
        [(entry["name"], entry["threshold"]) for entry in data],
        key=lambda x: -x[1]
    )
    return sorted_roles


# ──────────────────────────────────────────────────────────────────────────────
# Nun definieren wir die Slash‐Gruppe und alle Unterbefehle direkt hier.
SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)

champion_group = app_commands.Group(
    name="champion",
    description="Verwalte Champion-Punkte",
    guild_ids=[MAIN_SERVER_ID]  # *Nur* in dieser Guild registrieren
)


class ChampionCog(commands.Cog):
    """
    Kombinierter Cog: 
    • ChampionData (SQLite) für Punkte und Historie
    • Role‐Logik: weltweite Champion‐Rollen‐Verteilung
    • Alle Slash‐Befehle (/champion give, /champion set, …)
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Pfad zur SQLite-Datei (Railway-Volume: /app/data/champion/points.db)
        db_path = "data/champion/points.db"
        self.data = ChampionData(db_path)

        # Rollen‐Konfiguration einmal laden
        self.roles = load_roles_config()  # List[ (role_name, threshold), ... ]

    def get_current_role(self, score: int) -> Optional[str]:
        """
        Findet anhand des Scores die erste Rolle, bei der score >= threshold ist.
        """
        for role_name, threshold in self.roles:
            if score >= threshold:
                return role_name
        return None

    async def _apply_champion_role(self, user_id_str: str, score: int):
        """
        Vergibt oder entfernt Champion‐Rollen in Discord je nach dem aktuellen Score.
        """
        guild_id = int(os.getenv("server_id"))
        guild = discord.utils.get(self.bot.guilds, id=guild_id)
        if not guild:
            logger.warning("[ChampionCog] Guild nicht gefunden.")
            return

        member = guild.get_member(int(user_id_str))
        if not member:
            logger.info(
                f"[ChampionCog] Member {user_id_str} nicht auf dem Server.")
            return

        target_role_name = self.get_current_role(score)
        if not target_role_name:
            # Unterhalb der untersten Schwelle: keine Rolle vergeben
            return

        current_role_names = [r.name for r in member.roles]
        if target_role_name in current_role_names:
            return  # Rolle ist bereits korrekt gesetzt

        # Entferne alle älteren Champion‐Rollen, falls vorhanden
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
                    f"[ChampionCog] Keine Berechtigung, Rollen von {member.display_name} zu entfernen.")
            except Exception as e:
                logger.error(
                    f"[ChampionCog] Fehler beim Entfernen von Rollen: {e}", exc_info=True)

        # Füge die neue Rolle hinzu
        target_role = discord.utils.get(guild.roles, name=target_role_name)
        if target_role:
            try:
                await member.add_roles(target_role)
                logger.info(
                    f"[ChampionCog] Rolle '{target_role_name}' an {member.display_name} vergeben (Score {score}).")
            except discord.Forbidden:
                logger.warning(
                    f"[ChampionCog] Keine Berechtigung, Rolle '{target_role_name}' hinzuzufügen.")
            except Exception as e:
                logger.error(
                    f"[ChampionCog] Fehler beim Hinzufügen der Rolle: {e}", exc_info=True)
        else:
            logger.warning(
                f"[ChampionCog] Rolle '{target_role_name}' nicht in Discord gefunden.")

    async def update_user_score(self, user_id: int, delta: int, reason: str) -> int:
        """
        Ändert den Punktestand des Users um 'delta' (Positiv oder Negativ) mit Angabe von 'reason'.
        Speichert das in der DB und passt asynchron die Rolle an.
        Gibt die neue Gesamtpunktzahl zurück.
        """
        user_id_str = str(user_id)
        new_total = await self.data.add_delta(user_id_str, delta, reason)

        # Starte asynchrone Role‐Anpassung (ohne auf das Ergebnis zu warten)
        self.bot.loop.create_task(
            self._apply_champion_role(user_id_str, new_total))

        return new_total

    # ──────────────────────────────────────────────────────────────────────────
    # Slash‐Befehle:
    # ──────────────────────────────────────────────────────────────────────────

    @champion_group.command(
        name="give",
        description="Gibt einem User Punkte (nur Mods)"
    )
    @app_commands.describe(
        user="Der Nutzer, dem Punkte gegeben werden",
        punkte="Anzahl der Punkte",
        grund="Begründung"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        punkte: int,
        grund: str
    ):
        """Vergibt eine positive Punkte‐Änderung an den angegebenen User."""
        # Mods‐Check: "Community Mod" oder Administrator
        if not (any(r.name == "Community Mod" for r in interaction.user.roles)
                or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        new_total = await self.update_user_score(user.id, punkte, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} vergibt +{punkte} an {user} ({grund})")
        await interaction.response.send_message(f"✅ {user.mention} hat nun insgesamt {new_total} Punkte.")

    @champion_group.command(
        name="remove",
        description="Entfernt Punkte (nur Mods)"
    )
    @app_commands.describe(
        user="Der Nutzer, von dem Punkte abgezogen werden",
        punkte="Anzahl der Punkte",
        grund="Begründung"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        punkte: int,
        grund: str
    ):
        """Zieht Punkte vom angegebenen User ab."""
        if not (any(r.name == "Community Mod" for r in interaction.user.roles)
                or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        new_total = await self.update_user_score(user.id, -punkte, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} zieht {punkte} von {user} ab ({grund})")
        await interaction.response.send_message(f"⚠️ {user.mention} hat nun insgesamt {new_total} Punkte.")

    @champion_group.command(
        name="set",
        description="Setzt die Punktzahl eines Users (nur Mods)"
    )
    @app_commands.describe(
        user="Der Nutzer, dessen Punktzahl gesetzt wird",
        punkte="Neue Gesamtpunktzahl",
        grund="Begründung"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        punkte: int,
        grund: str
    ):
        """Setzt die Gesamtpunktzahl eines Users auf einen exakten Wert."""
        if not (any(r.name == "Community Mod" for r in interaction.user.roles)
                or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        old_total = await self.data.get_total(str(user.id))
        delta = punkte - old_total
        new_total = await self.update_user_score(user.id, delta, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} setzt {user} von {old_total} auf {punkte} Punkte ({grund})")
        await interaction.response.send_message(f"🔧 {user.mention} wurde auf {new_total} Punkte gesetzt.")

    @champion_group.command(
        name="reset",
        description="Setzt die Punkte eines Nutzers auf 0 (nur Mods)"
    )
    @app_commands.describe(user="Der Nutzer, dessen Punkte zurückgesetzt werden")
    @app_commands.default_permissions(manage_guild=True)
    async def reset(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Setzt die Punktzahl des Users auf 0, falls >0."""
        if not (any(r.name == "Community Mod" for r in interaction.user.roles)
                or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        old_total = await self.data.get_total(str(user.id))
        if old_total <= 0:
            await interaction.response.send_message(f"ℹ️ {user.mention} hat aktuell keine Punkte zum Zurücksetzen.")
            return

        new_total = await self.update_user_score(user.id, -old_total, "Reset durch Mod")
        logger.info(
            f"[ChampionCommands] {interaction.user} setzt {user} zurück (von {old_total} auf 0).")
        await interaction.response.send_message(f"🔄 {user.mention} wurde auf 0 Punkte zurückgesetzt.")

    @champion_group.command(
        name="info",
        description="Zeigt Deine Punktzahl"
    )
    @app_commands.default_permissions(send_messages=True)
    async def info(self, interaction: discord.Interaction):
        """Gibt dem aufrufenden User die aktuelle Gesamtpunktzahl zurück."""
        user_id_str = str(interaction.user.id)
        total = await self.data.get_total(user_id_str)
        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion info auf.")
        await interaction.response.send_message(f"🏅 Du hast aktuell {total} Punkte.")

    @champion_group.command(
        name="history",
        description="Zeigt die Punkte‐Historie eines Spielers"
    )
    @app_commands.describe(user="Der Spieler, dessen Historie angezeigt wird")
    @app_commands.default_permissions(send_messages=True)
    async def history(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Zeigt bis zu 10 letzte Änderungen der Punktzahl eines Users."""
        user_id_str = str(user.id)
        history = await self.data.get_history(user_id_str, limit=10)
        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion history für {user} auf.")

        if not history:
            await interaction.response.send_message(f"📭 {user.display_name} hat noch keine Historie.")
            return

        lines = []
        for entry in history:
            date_str = entry["date"][:10]  # ISO: YYYY-MM-DD
            delta = entry["delta"]
            sign = "+" if delta > 0 else ""
            lines.append(f"📅 {date_str}: {sign}{delta} – {entry['reason']}")

        text = "\n".join(lines)
        await interaction.response.send_message(f"📜 Punkteverlauf von {user.display_name}:\n{text}")

    @champion_group.command(
        name="leaderboard",
        description="Zeigt die Top 10 (Punkte‐Ranking)"
    )
    @app_commands.describe(page="Welche Seite des Leaderboards (10 Einträge pro Seite)")
    @app_commands.default_permissions(send_messages=True)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        page: Optional[int] = 1
    ):
        """
        Zeigt das Leaderboard in Blöcken von 10 Einträgen an.
        Parameter 'page' (1-basierter Index) bestimmt den Offset.
        """
        if page < 1:
            page = 1
        limit = 10
        offset = (page - 1) * limit
        top = await self.data.get_leaderboard(limit=limit, offset=offset)

        if not top:
            await interaction.response.send_message("🤷 Keine Einträge im Leaderboard.")
            return

        entries = []
        for idx, (user_id_str, total) in enumerate(top, start=offset + 1):
            member = interaction.guild.get_member(int(user_id_str))
            name = member.display_name if member else f"Unbekannt ({user_id_str})"
            entries.append(f"{idx}. {name} – {total} Punkte")

        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion leaderboard Page {page} auf.")
        text = "\n".join(entries)
        await interaction.response.send_message(f"🏆 **Top {offset+1}–{offset+len(top)}**:\n{text}")


# ──────────────────────────────────────────────────────────────────────────────
# Am Ende kein extra setup() für den Slash‐Cog – der wird in __init__.py automatisch aufgerufen.
# ChampionCog ist ein Cog, der beim Hinzufügen alle oben definierten /champion‐Unterbefehle registriert.
