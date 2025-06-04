import discord
from discord.ext import commands

from log_setup import get_logger

from .cog import QuizCog
from .slash_commands import quiz_group

logger = get_logger(__name__)


async def setup(bot: commands.Bot):
    logger.info("[QuizInit] Initialisierung startet...")

    try:
        await bot.add_cog(QuizCog(bot))
        bot.tree.add_command(quiz_group, guild=bot.main_guild)
        logger.info(
            "[QuizInit] Cog und Slash-Command-Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[QuizInit] Fehler beim Setup: {e}", exc_info=True)
