import os
import json
from pathlib import Path
import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv

from log_setup import setup_logging, get_logger
from cogs.quiz.question_state import QuestionStateManager
from cogs.quiz.question_generator import QuestionGenerator

# Lade Umgebungsvariablen
load_dotenv()

# Logging-Konfiguration
setup_logging()
logger = get_logger("bot")

# Discord-Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

QUIZ_CONFIG_PATH = "data/pers/quiz/areas.json"
QUESTION_STATE_PATH = "data/pers/quiz/question_state.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_quiz_config(bot: commands.Bot):
    """Lädt Quiz-Areas aus ``QUIZ_CONFIG_PATH`` und bereitet sie vor."""
    bot.quiz_data = {}

    cfg_file = Path(QUIZ_CONFIG_PATH)
    if not cfg_file.exists():
        logger.warning(f"[bot] Quiz-Konfigurationsdatei nicht gefunden: {cfg_file}")
        return

    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            areas = json.load(f)
    except Exception as e:
        logger.error(f"[bot] Fehler beim Laden der Quiz-Konfiguration: {e}")
        return

    state = QuestionStateManager(QUESTION_STATE_PATH)

    for area, cfg in areas.items():
        time_window = datetime.timedelta(minutes=cfg.get("window_timer", 15))
        language = cfg.get("language", "de")

        dynamic_providers = {}
        try:
            module = __import__(
                f"cogs.quiz.area_providers.{area}", fromlist=["get_provider"]
            )
            dynamic_providers[area] = module.get_provider(bot, language=language)
        except Exception as e:
            logger.info(f"[bot] Kein dynamischer Provider für '{area}': {e}")

        generator = QuestionGenerator(
            bot.data.get("quiz", {}).get("questions", {}),
            state_manager=state,
            dynamic_providers=dynamic_providers,
        )

        bot.quiz_data[area] = {
            "channel_id": cfg.get("channel_id"),
            "time_window": time_window,
            "language": language,
            "active": cfg.get("active", False),
            "activity_threshold": cfg.get("activity_threshold", 10),
            "question_state": state,
            "question_generator": generator,
        }

    logger.info(f"[bot] Quiz-Konfiguration geladen: {list(bot.quiz_data.keys())}")


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="§",  # Wird nicht genutzt, Pflichtfeld
            intents=intents,
            sync_commands=False
        )
        guild_id = os.getenv("server_id")
        if not guild_id:
            logger.error("Environment variable 'server_id' is not set.")
            exit(1)
        self.main_guild_id = int(guild_id)
        self.main_guild = discord.Object(id=self.main_guild_id)
        self.data = {}
        # Provide a default attribute so cogs relying on ``quiz_data`` don't fail
        # if no configuration was loaded yet.
        self.quiz_data = {}

    async def setup_hook(self):
        # Optional: Commands leeren für Guild (verhindert Ghost-Kommandos bei Updates)
        self.tree.clear_commands(guild=self.main_guild)

        # Emoji-Export (wird nach jedem Start durchgeführt)
        await self._export_emojis()

        # Quiz-Fragen in allen Sprachen laden
        quiz_questions = {}
        quiz_languages = []
        quiz_dir = Path("data/quiz")
        for f in quiz_dir.glob("questions_*.json"):
            lang = f.stem.split("_")[1]
            quiz_questions[lang] = load_json(f)
            quiz_languages.append(lang)

        # WCR-Daten zentral laden
        wcr_data = {
            "units": load_json("data/wcr/units.json"),
            "pictures": load_json("data/wcr/pictures.json"),
            "locals": {
                "de": load_json("data/wcr/locals/de.json"),
                "en": load_json("data/wcr/locals/en.json"),
            },
        }

        # Champion-Rollen laden
        champion_roles = load_json("data/champion/roles.json")

        # Alle zentralen Daten bündeln, inkl. Emojis!
        self.data = {
            "emojis": self._load_emojis_from_file(),
            "quiz": {
                "questions": quiz_questions,
                "languages": quiz_languages,
            },
            "wcr": wcr_data,
            "champion": {
                "roles": champion_roles,
            },
        }

        logger.info(f"[bot] Zentrale Daten geladen: {list(self.data.keys())}")

        # Quiz-Konfiguration laden
        load_quiz_config(self)

        # Cogs importieren & registrieren
        from cogs import quiz, wcr, champion

        await quiz.setup(self)
        await wcr.setup(self)
        await champion.setup(self)

        await self.tree.sync(guild=self.main_guild)

    async def on_ready(self):
        logger.info(
            f"Bot ist bereit! Eingeloggt als {self.user} (ID: {self.user.id})")

    async def _export_emojis(self):
        """Exportiert alle Server-Emojis in eine JSON-Datei."""
        emojis = {e.name: str(e) for e in self.emojis}
        with open("data/emojis.json", "w", encoding="utf-8") as f:
            json.dump(emojis, f, ensure_ascii=False, indent=2)
        logger.info(f"{len(emojis)} Emojis exportiert.")

    def _load_emojis_from_file(self):
        """Lädt Emojis aus JSON-Datei."""
        emoji_file = Path("data/emojis.json")
        if not emoji_file.exists():
            return {}
        with open(emoji_file, "r", encoding="utf-8") as f:
            return json.load(f)


if __name__ == "__main__":
    token = os.getenv("bot_key")
    if not token:
        logger.error("Environment variable 'bot_key' is not set.")
        exit(1)

    bot = MyBot()
    bot.run(token)
