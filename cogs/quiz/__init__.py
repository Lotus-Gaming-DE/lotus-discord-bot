import discord

from log_setup import get_logger

from .cog import QuizCog
from .slash_commands import quiz_group

logger = get_logger(__name__)


async def setup(bot: discord.ext.commands.Bot):
    try:
        await bot.add_cog(QuizCog(bot))
        bot.tree.add_command(quiz_group, guild=bot.main_guild)
        logger.info("[QuizCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[QuizCog] Fehler beim Setup: {e}", exc_info=True)
