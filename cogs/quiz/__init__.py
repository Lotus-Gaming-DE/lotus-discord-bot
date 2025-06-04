import discord
from discord.ext import commands

from log_setup import get_logger

from .cog import QuizCog
from .slash_commands import quiz_group
from .question_generator import QuestionGenerator
from .question_manager import QuestionManager
from .question_state import QuestionStateManager
from .question_closer import QuestionCloser
from .message_tracker import MessageTracker
from .utils import get_available_areas
from bot import QUESTION_STATE_PATH

logger = get_logger(__name__)


async def setup(bot: commands.Bot):
    logger.info("[QuizInit] Initialisierung startet...")

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
        questions_by_area=bot.quiz_data["questions"],
        state_manager=state_manager,
        dynamic_providers=dynamic_providers,
    )

    manager = QuestionManager(bot, generator, state_manager, tracker)
    closer = QuestionCloser(bot, state_manager)

    bot.add_cog(manager)
    bot.add_cog(closer)
    bot.tree.add_command(quiz_group, guild=bot.main_guild)

    logger.info(
        "[QuizInit] Cog und Slash-Command-Gruppe erfolgreich registriert.")
