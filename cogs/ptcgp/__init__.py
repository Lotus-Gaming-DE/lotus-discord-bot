import discord

from log_setup import get_logger

from .cog import PTCGPCog

logger = get_logger(__name__)


async def setup(bot: discord.ext.commands.Bot):
    """Register the PTCGP cog and its slash commands."""
    try:
        from .slash_commands import ptcgp_group

        await bot.add_cog(PTCGPCog(bot))
        bot.tree.add_command(ptcgp_group, guild=bot.main_guild)
        logger.info("[PTCGPCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[PTCGPCog] Fehler beim Setup: {e}", exc_info=True)
