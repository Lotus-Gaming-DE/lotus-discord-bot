from discord.ext import commands

from lotus_bot.log_setup import get_logger

from .cog import QuizCog
from .slash_commands import quiz_group
from lotus_bot.utils.setup_helpers import register_cog_and_group


logger = get_logger(__name__)


async def setup(bot: commands.Bot):
    """Setzt das Quiz-Cog auf und registriert die Slash-Befehle."""
    logger.info("[QuizInit] Initialisierung startet...")

    await register_cog_and_group(bot, QuizCog, quiz_group)

    logger.info("[QuizInit] Cog und Slash-Command-Gruppe erfolgreich registriert.")
