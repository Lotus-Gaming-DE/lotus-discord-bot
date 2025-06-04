import discord
import logging

from .cog import ChampionCog
from .slash_commands import champion_group

logger = logging.getLogger(__name__)


async def setup(bot: discord.ext.commands.Bot):
    try:
        # 1) Haupt-Cog: Champion-Daten und Rolle-Logik
        await bot.add_cog(ChampionCog(bot))

        # 2) Slash-Gruppe /champion in den Command-Tree einfügen
        bot.tree.add_command(
            champion_group,
            guild=bot.main_guild
        )

        logger.info(
            "[ChampionCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[ChampionCog] Fehler beim Setup: {e}", exc_info=True)
