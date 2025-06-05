from discord.ext import commands

from log_setup import get_logger

from .cog import QuizCog
from .slash_commands import quiz_group



logger = get_logger(__name__)


async def setup(bot: commands.Bot):
    """Set up the quiz cog and slash commands."""
    logger.info("[QuizInit] Initialisierung startet...")

    quiz_cog = QuizCog(bot)
    await bot.add_cog(quiz_cog, override=True)
    bot.tree.add_command(quiz_group, guild=bot.main_guild)

    logger.info(
        "[QuizInit] Cog und Slash-Command-Gruppe erfolgreich registriert.")
