from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.setup_helpers import register_cog_and_group

from .cog import WoWCog

logger = get_logger(__name__)


async def setup(bot: commands.Bot):
    """Registriert Cog und Slash-Befehle für WoW Classic Hardcore."""
    try:
        from .slash_commands import wow_group

        await register_cog_and_group(bot, WoWCog, wow_group)
        logger.info("[WoWCog] Cog and slash command group registered successfully.")
    except Exception as e:
        logger.error(f"[WoWCog] Error during setup: {e}", exc_info=True)
        raise
