# cogs/quiz/__init__.py

import os
import discord
import logging

from .cog import QuizCog
from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .wcr_question_provider import WCRQuestionProvider
from .slash_commands import quiz_group

logger = logging.getLogger(__name__)

# Guild‐ID aus der Umgebung
SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        # ─── DataLoader initialisieren ────────────────────────────────────
        loader = DataLoader()
        loader.set_language("de")
        questions_by_area = loader.questions_by_area
        asked_questions = loader.load_asked_questions()

        # ─── WCR‐Provider anlegen ───────────────────────────────────────────
        wcr_units = bot.data["wcr"]["units"]
        wcr_languages = bot.data["wcr"]["languages"]
        wcr_provider = WCRQuestionProvider(
            units=wcr_units,
            locals_data=wcr_languages,
            language="de"
        )

        # ─── QuestionGenerator erzeugen ────────────────────────────────────
        generator = QuestionGenerator(
            questions_by_area=questions_by_area,
            asked_questions=asked_questions,
            dynamic_providers={"wcr": wcr_provider}
        )

        # ─── bot.quiz_data für alle konfigurierten Areas füllen ────────────
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
                    f"[QuizCog] env var '{env_var}' nicht gesetzt, überspringe area '{area}'"
                )
                continue
            try:
                channel_id = int(cid_str)
            except ValueError:
                logger.error(
                    f"[QuizCog] Ungültige Channel-ID in '{env_var}': {cid_str}"
                )
                continue

            quiz_data[area] = {
                "channel_id": channel_id,
                "data_loader": loader,
                "question_generator": generator
            }

        # Setze bot.quiz_data VOR dem Hinzufügen des QuizCog
        bot.quiz_data = quiz_data

        # ─── QuizCog laden (Scheduler, Frage‐Logik, Button/Modal etc.) ─────
        await bot.add_cog(QuizCog(bot))

        # ─── Slash‐Command‐Gruppe “/quiz” in den Command‐Tree einfügen ─────
        bot.tree.add_command(
            quiz_group,
            guild=discord.Object(id=MAIN_SERVER_ID)
        )

        logger.info(
            "[QuizCog] Cog und Slash‐Command‐Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[QuizCog] Fehler beim Setup: {e}", exc_info=True)
