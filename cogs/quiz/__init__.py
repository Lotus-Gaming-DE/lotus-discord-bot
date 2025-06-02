import os
import discord
import logging

from .cog import QuizCog
from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .wcr_question_provider import WCRQuestionProvider
from .slash_commands import quiz_group
from .question_state import QuestionStateManager

logger = logging.getLogger(__name__)

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        loader = bot.data["quiz"]["data_loader"]
        loader.set_language("de")

        questions_by_area = loader.questions_by_area
        state_manager = QuestionStateManager(
            "data/pers/quiz/question_state.json")

        # WCR-spezifischer Fragentyp
        wcr_provider = WCRQuestionProvider(
            units=bot.data["wcr"]["units"],
            locals_data=bot.data["wcr"]["languages"],
            language="de"
        )

        # Generator
        generator = QuestionGenerator(
            questions_by_area=questions_by_area,
            state_manager=state_manager,
            dynamic_providers={"wcr": wcr_provider}
        )

        quiz_data = {}
        env_areas = {
            "wcr": "quiz_c_wcr",
            "d4": "quiz_c_d4",
            "ptcgp": "quiz_c_ptcgp"
        }
        for area, env_var in env_areas.items():
            cid_str = os.getenv(env_var)
            if not cid_str:
                logger.warning(
                    f"[QuizCog] env var '{env_var}' nicht gesetzt, überspringe '{area}'")
                continue

            try:
                cid = int(cid_str)
            except ValueError:
                logger.error(
                    f"[QuizCog] Ungültige Channel-ID in '{env_var}': {cid_str}")
                continue

            quiz_data[area] = {
                "channel_id": cid,
                "data_loader": loader,
                "question_generator": generator,
                "question_state": state_manager
            }

        bot.quiz_data = quiz_data

        await bot.add_cog(QuizCog(bot))
        bot.tree.add_command(
            quiz_group, guild=discord.Object(id=MAIN_SERVER_ID))
        logger.info(
            "[QuizCog] Cog und Slash‐Command‐Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[QuizCog] Fehler beim Setup: {e}", exc_info=True)
