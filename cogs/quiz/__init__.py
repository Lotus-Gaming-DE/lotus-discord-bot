# cogs/quiz/__init__.py

import os
import discord
import logging

from .cog import QuizCog
from .slash_commands import quiz_group
from .question_generator import QuestionGenerator
from .wcr_question_provider import WCRQuestionProvider

logger = logging.getLogger(__name__)

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        # Daten aus bot.data extrahieren
        quiz_cfg = bot.data.get("quiz", {})
        data_loader = quiz_cfg["data_loader"]
        questions_by_area = quiz_cfg["questions_by_area"]

        # Asked questions-Tracking aus dem Loader
        asked_questions = data_loader.load_asked_questions()

        # Dynamische Fragetypen registrieren
        dynamic_providers = {
            "wcr": WCRQuestionProvider(
                units=bot.data["wcr"]["units"],
                locals_data=bot.data["wcr"]["languages"],
                language="de"
            )
        }

        # Generator instanziieren und einhängen
        generator = QuestionGenerator(
            questions_by_area=questions_by_area,
            asked_questions=asked_questions,
            dynamic_providers=dynamic_providers
        )

        # quiz_data mit allen Infos für jede Area vorbereiten
        bot.quiz_data = {
            "wcr": {
                "channel_id": int(os.getenv("quiz_c_wcr")),
                "question_generator": generator,
                "data_loader": data_loader
            },
            # Weitere Areas wie "d4", "ptcgp" etc. später hier ergänzen
        }

        await bot.add_cog(QuizCog(bot))
        bot.tree.add_command(
            quiz_group, guild=discord.Object(id=MAIN_SERVER_ID))
        logger.info(
            "[QuizCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")

    except Exception as e:
        logger.error(f"[QuizCog] Fehler beim Setup: {e}", exc_info=True)
