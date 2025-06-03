import os
import discord
import logging
import importlib
import json
import datetime
from pathlib import Path

from .cog import QuizCog
from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .slash_commands import quiz_group
from .question_state import QuestionStateManager

logger = logging.getLogger(__name__)

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)

AREA_CONFIG_PATH = Path("data/pers/quiz/areas.json")


def load_area_config() -> dict:
    if not AREA_CONFIG_PATH.exists():
        logger.warning("[QuizInit] areas.json nicht gefunden.")
        return {}
    with AREA_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_dynamic_provider(area_name: str):
    try:
        module_path = f"cogs.quiz.area_providers.{area_name}"
        module = importlib.import_module(module_path)
        return module.get_provider()
    except Exception as e:
        logger.warning(
            f"[QuizInit] Kein dynamischer Provider für '{area_name}': {e}")
        return None


async def setup(bot: discord.ext.commands.Bot):
    try:
        loader = DataLoader()
        questions_by_area = loader.questions_by_area
        area_config = load_area_config()

        bot.quiz_data = {}
        for area, cfg in area_config.items():
            try:
                channel_id = int(cfg["channel_id"])
                time_window = datetime.timedelta(
                    minutes=int(cfg.get("window_timer", 15)))
                max_dynamic = int(cfg.get("max_dynamic_questions", 5))
                lang = cfg.get("language", "de")
                active = cfg.get("active", False)

                loader.set_language(lang)
                area_questions = {area: questions_by_area.get(area, {})}
                state = QuestionStateManager(
                    f"data/pers/quiz/state_{area}.json")
                provider = load_dynamic_provider(area)

                generator = QuestionGenerator(
                    questions_by_area=area_questions,
                    state_manager=state,
                    dynamic_providers={area: provider} if provider else {}
                )

                bot.quiz_data[area] = {
                    "channel_id": channel_id,
                    "data_loader": loader,
                    "question_generator": generator,
                    "question_state": state,
                    "language": lang,
                    "time_window": time_window,
                    "active": active,
                    "max_dynamic_questions": max_dynamic
                }
            except Exception as e:
                logger.error(
                    f"[QuizInit] Fehler bei Area '{area}': {e}", exc_info=True)

        await bot.add_cog(QuizCog(bot))
        bot.tree.add_command(
            quiz_group, guild=discord.Object(id=MAIN_SERVER_ID))
        logger.info(
            "[QuizInit] Cog und Slash-Command-Gruppe erfolgreich registriert.")

    except Exception as e:
        logger.error(f"[QuizInit] Fehler beim Setup: {e}", exc_info=True)
