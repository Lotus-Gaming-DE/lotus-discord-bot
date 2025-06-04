import discord
from discord.ext import commands

from log_setup import get_logger

from .cog import QuizCog
from .slash_commands import quiz_group
from .question_state import QuestionStateManager
from .question_generator import QuestionGenerator
from .utils import get_available_areas


logger = get_logger(__name__)


async def setup(bot: commands.Bot):
    """Set up the quiz cog and slash commands."""
    logger.info("[QuizInit] Initialisierung startet...")

    from bot import QUESTION_STATE_PATH

    areas = get_available_areas()
    state_manager = QuestionStateManager(QUESTION_STATE_PATH)
    dynamic_providers = {}

    for area in areas:
        try:
            module = __import__(
                f"cogs.quiz.area_providers.{area}", fromlist=["get_provider"])
            dynamic_providers[area] = module.get_provider(bot, language="de")
        except ModuleNotFoundError as e:
            logger.warning(
                f"[QuizInit] Kein dynamischer Provider für '{area}': {e}")

    generator = QuestionGenerator(
        questions_by_area=bot.quiz_data.get("questions", {}),
        state_manager=state_manager,
        dynamic_providers=dynamic_providers,
    )

    bot.quiz_generator = generator  # expose for potential use

    quiz_cog = QuizCog(bot)
    await bot.add_cog(quiz_cog, override=True)
    bot.tree.add_command(quiz_group, guild=bot.main_guild)

    logger.info(
        "[QuizInit] Cog und Slash-Command-Gruppe erfolgreich registriert.")
