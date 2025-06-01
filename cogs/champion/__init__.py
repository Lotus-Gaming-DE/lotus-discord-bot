import os
import discord
import logging
from .cog import ChampionCog

logger = logging.getLogger(__name__)  # cogs.champion.__init__

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        await bot.add_cog(ChampionCog(bot))
        logger.info("[ChampionCog] Cog erfolgreich geladen.")
    except Exception as e:
        logger.error(f"[ChampionCog] Fehler beim Setup: {e}", exc_info=True)
