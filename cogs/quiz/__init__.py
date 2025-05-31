import logging
from discord.ext import commands
from .cog import QuizCog
from .slash_commands import QuizCommands

logger = logging.getLogger(__name__)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuizCog(bot))
    await bot.add_cog(QuizCommands(bot))
    logger.info(
        "[QuizCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
