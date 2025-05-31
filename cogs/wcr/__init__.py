# cogs/wcr/__init__.py

import os
import discord
import logging

from .cog import WCRCog
from .slash_commands import wcr_group

logger = logging.getLogger(__name__)  # z.B. "cogs.wcr.__init__"

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        await bot.add_cog(WCRCog(bot))
        bot.tree.add_command(
            wcr_group,
            guild=discord.Object(id=MAIN_SERVER_ID)
        )
        logger.info(
            "[WCRCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[WCRCog] Fehler beim Setup: {e}", exc_info=True)
