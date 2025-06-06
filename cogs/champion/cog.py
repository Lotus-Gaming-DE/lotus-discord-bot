import discord
import asyncio
from discord.ext import commands
from typing import Optional

from log_setup import get_logger, create_logged_task
from .data import ChampionData

logger = get_logger(__name__)


class ChampionCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        """Initialize the cog and load role configuration."""
        self.bot = bot

        db_path = "data/pers/champion/points.db"
        self.data = ChampionData(db_path)

        self.roles = self._load_roles_config()
        self.tasks: list[asyncio.Task] = []

    def _load_roles_config(self) -> list[tuple[str, int]]:
        """Return the role thresholds sorted descending."""
        role_entries = self.bot.data.get("champion", {}).get("roles", [])
        sorted_roles = sorted(
            [(entry["name"], entry["threshold"]) for entry in role_entries],
            key=lambda x: -x[1],
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

        task = create_logged_task(
            self._apply_champion_role(user_id_str, new_total), logger
        )
        self.tasks.append(task)

        def _remove_finished(t: asyncio.Task) -> None:
            if t in self.tasks:
                self.tasks.remove(t)

        task.add_done_callback(_remove_finished)

        return new_total

    async def _apply_champion_role(self, user_id_str: str, score: int) -> None:
        """Assign the correct champion role based on the score."""
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

        target_role_name = self.get_current_role(score)

        current_role_names = [r.name for r in member.roles]

        roles_to_remove = []
        for role_name, _ in self.roles:
            if role_name in current_role_names and role_name != target_role_name:
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
                    f"[ChampionCog] Fehler beim Entfernen von Rollen: {e}",
                    exc_info=True,
                )

        if not target_role_name or target_role_name in current_role_names:
            return

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
                    f"[ChampionCog] Fehler beim Hinzufügen der Rolle: {e}",
                    exc_info=True,
                )
        else:
            logger.warning(
                f"[ChampionCog] Rolle '{target_role_name}' existiert nicht in Discord."
            )

    def cog_unload(self):
        for task in self.tasks:
            task.cancel()
        create_logged_task(self.data.close(), logger)
