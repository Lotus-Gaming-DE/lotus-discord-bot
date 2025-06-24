import discord
import asyncio
from dataclasses import dataclass
from discord.ext import commands
from typing import Optional, List
import os

from log_setup import get_logger
from utils.managed_cog import ManagedTaskCog
from .data import ChampionData

logger = get_logger(__name__)


@dataclass
class ChampionRole:
    id: int
    name: str
    threshold: int


class ChampionCog(ManagedTaskCog):
    def __init__(self, bot: commands.Bot) -> None:
        """Initialisiert das Cog und lädt die Rollenkonfiguration.

        Der Pfad zur Punkte-Datenbank kann \u00fcber die Environment-Variable
        ``CHAMPION_DB_PATH`` angepasst werden.
        """
        super().__init__()
        self.bot = bot

        db_path = os.getenv("CHAMPION_DB_PATH", "data/pers/champion/points.db")
        self.data = ChampionData(db_path)

        self.roles: List[ChampionRole] = self._load_roles_config()

        self.create_task(self.sync_all_roles())

        self.update_queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self.worker_task = self.create_task(self._worker())

    def _load_roles_config(self) -> list[ChampionRole]:
        """Gibt die Rollenschwellen absteigend sortiert zurück."""
        role_entries = self.bot.data.get("champion", {}).get("roles", [])
        roles = [
            ChampionRole(
                id=int(entry.get("id", 0)),
                name=entry["name"],
                threshold=entry["threshold"],
            )
            for entry in role_entries
        ]
        roles.sort(key=lambda r: -r.threshold)
        return roles

    def get_current_role(self, score: int) -> Optional[ChampionRole]:
        """Ermittelt die höchste Rolle, für die ein Nutzer genug Punkte hat."""
        for role in self.roles:
            if score >= role.threshold:
                return role
        return None

    async def update_user_score(self, user_id: int, delta: int, reason: str) -> int:
        """Wendet eine Punktänderung an und passt die Rolle des Mitglieds an."""
        user_id_str = str(user_id)
        new_total = await self.data.add_delta(user_id_str, delta, reason)

        await self.update_queue.put((user_id_str, new_total))

        return new_total

    async def sync_all_roles(self) -> None:
        """Synchronisiert die Champion-Rollen aller gespeicherten Nutzer."""
        user_ids = await self.data.get_all_user_ids()
        for user_id_str in user_ids:
            total = await self.data.get_total(user_id_str)
            await self._apply_champion_role(user_id_str, total)

    async def _worker(self) -> None:
        """Verarbeitet Punktänderungen aus der Warteschlange nacheinander."""
        while True:
            user_id_str, total = await self.update_queue.get()
            try:
                await self._apply_champion_role(user_id_str, total)
            finally:
                self.update_queue.task_done()

    async def _apply_champion_role(self, user_id_str: str, score: int) -> None:
        """Vergibt anhand der Punkte die passende Champion-Rolle."""
        # Zugriff auf Guild NUR noch über self.bot.main_guild (Zentral, wie in bot.py gesetzt)
        guild = self.bot.main_guild
        if not isinstance(guild, discord.Guild):
            logger.warning("[ChampionCog] Guild nicht gefunden.")
            return

        member = guild.get_member(int(user_id_str))
        try:
            if member is None:
                member = await guild.fetch_member(int(user_id_str))
        except discord.NotFound:
            logger.info(
                f"[ChampionCog] Member {user_id_str} nicht gefunden (vermutlich nicht mehr im Server)."
            )
            return
        except discord.HTTPException as e:
            logger.error(
                f"[ChampionCog] Fehler beim Laden von Member {user_id_str}: {e}",
                exc_info=True,
            )
            return

        target_role = self.get_current_role(score)

        current_role_ids = [r.id for r in member.roles]

        roles_to_remove = []
        for role in self.roles:
            if role.id in current_role_ids and role != target_role:
                role_obj = guild.get_role(role.id)
                if role_obj is None:
                    role_obj = discord.utils.get(guild.roles, name=role.name)
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
                    f"[ChampionCog] Fehler beim Entfernen von Rollen: {e}",
                    exc_info=True,
                )

        if not target_role or target_role.id in current_role_ids:
            return

        target_role_obj = guild.get_role(target_role.id)
        if target_role_obj is None:
            target_role_obj = discord.utils.get(guild.roles, name=target_role.name)
        if target_role_obj:
            try:
                await member.add_roles(target_role_obj)
                logger.info(
                    f"[ChampionCog] Rolle '{target_role.name}' an {member.display_name} vergeben (Score {score})."
                )
            except discord.Forbidden:
                logger.warning(
                    f"[ChampionCog] Keine Berechtigung, Rolle '{target_role.name}' hinzuzufügen."
                )
            except Exception as e:
                logger.error(
                    f"[ChampionCog] Fehler beim Hinzufügen der Rolle: {e}",
                    exc_info=True,
                )
        else:
            logger.warning(
                f"[ChampionCog] Rolle '{target_role.name}' existiert nicht in Discord."
            )

    def cog_unload(self):
        """Beendet Tasks und schließt die Datenbankverbindung."""
        super().cog_unload()
        # Datenbank sauber schließen, damit keine offenen Tasks bleiben
        self.create_task(self.data.close())
