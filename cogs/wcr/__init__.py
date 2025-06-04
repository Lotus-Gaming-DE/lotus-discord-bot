# cogs/wcr/__init__.py

import discord

from log_setup import get_logger

from .cog import WCRCog

logger = get_logger(__name__)  # z.B. "cogs.wcr.__init__"


async def setup(bot: discord.ext.commands.Bot):
    try:
        from .slash_commands import wcr_group
        await bot.add_cog(WCRCog(bot))
        bot.tree.add_command(wcr_group, guild=bot.main_guild)
        logger.info("[WCRCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[WCRCog] Fehler beim Setup: {e}", exc_info=True)
