import discord
from discord.ext import commands

from log_setup import get_logger

from .cog import QuizCog
from .slash_commands import quiz_group
        await bot.add_cog(QuizCog(bot), override=True)
from .question_manager import QuestionManager
from .question_state import QuestionStateManager
from .question_closer import QuestionCloser
from .message_tracker import MessageTracker
from .utils import get_available_areas


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
    from bot import QUESTION_STATE_PATH

    from .slash_commands import quiz_group

    areas = get_available_areas()
    state_manager = QuestionStateManager(QUESTION_STATE_PATH)
    tracker = MessageTracker(bot)
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
    await bot.add_cog(quiz_cog)
    bot.tree.add_command(quiz_group, guild=bot.main_guild)

    logger.info(
        "[QuizInit] Cog und Slash-Command-Gruppe erfolgreich registriert.")