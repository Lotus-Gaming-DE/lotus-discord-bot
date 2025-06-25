# cogs/wcr/__init__.py

import discord

from lotus_bot.log_setup import get_logger

from .cog import WCRCog
from lotus_bot.utils.setup_helpers import register_cog_and_group

logger = get_logger(__name__)  # z.B. "cogs.wcr.__init__"


async def setup(bot: discord.ext.commands.Bot):
    """Registriert Cog und Slash-Befehle für WCR."""
    try:
        from .slash_commands import wcr_group

        await register_cog_and_group(bot, WCRCog, wcr_group)
        logger.info("[WCRCog] Cog and slash command group registered successfully.")
    except Exception as e:
        logger.error(f"[WCRCog] Error during setup: {e}", exc_info=True)
        raise
