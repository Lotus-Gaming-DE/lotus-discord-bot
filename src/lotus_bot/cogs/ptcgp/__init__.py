import discord

from lotus_bot.log_setup import get_logger

from .cog import PTCGPCog
from lotus_bot.utils.setup_helpers import register_cog_and_group

logger = get_logger(__name__)


async def setup(bot: discord.ext.commands.Bot):
    """Registriert Cog und Slash-Befehle für PTCGP."""
    try:
        from .slash_commands import ptcgp_group

        await register_cog_and_group(bot, PTCGPCog, ptcgp_group)
        logger.info("[PTCGPCog] Cog and slash command group registered successfully.")
    except Exception as e:
        logger.error(f"[PTCGPCog] Error during setup: {e}", exc_info=True)
