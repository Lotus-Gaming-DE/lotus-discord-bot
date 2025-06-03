# bot.py

import os
import json
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.quiz.data_loader import DataLoader
from cogs.wcr.utils import load_wcr_data

# Lade Umgebungsvariablen
load_dotenv()

# Logging-Konfiguration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s"
)
logging.getLogger("discord").setLevel(logging.WARNING)
logger = logging.getLogger("bot")

# Discord-Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="§",  # Wird nicht genutzt, aber Pflichtfeld
            intents=intents,
            sync_commands=False
        )

        guild_id = os.getenv("server_id")
        if not guild_id:
            logger.error("Environment variable 'server_id' is not set.")
            exit(1)
        self.main_guild = discord.Object(id=int(guild_id))

        # Gemeinsamer Datenspeicher
        self.data = {}
        self.shared_data_loader = DataLoader()

    async def setup_hook(self):
        self.tree.clear_commands(guild=self.main_guild)

        await self._export_emojis()

        # Gemeinsame Datenstruktur befüllen
        quiz_questions, quiz_languages = self.shared_data_loader.load_all_languages()
        self.data = {
            "emojis": self._load_emojis_from_file(),
            "quiz": {
                "questions": quiz_questions,
                "languages": quiz_languages,
                "data_loader": self.shared_data_loader
            },
            "wcr": load_wcr_data()
        }

        logger.info(
            f"[bot] Gemeinsame Daten geladen: {list(self.data.keys())}")

        # Cogs laden
        for path in Path("./cogs").rglob("__init__.py"):
            module = ".".join(path.with_suffix("").parts)
            try:
                await self.load_extension(module)
                logger.info(f"[bot] Extension loaded: {module}")
            except Exception as e:
                logger.error(
                    f"[bot] Failed to load extension {module}: {e}", exc_info=True)

        # Slash-Befehle synchronisieren
        try:
            await self.tree.sync(guild=self.main_guild)
            logger.info(
                f"[bot] Slash commands synced for guild {self.main_guild.id}")
        except Exception as e:
            logger.error(
                f"[bot] Failed to sync slash commands: {e}", exc_info=True)

    async def _export_emojis(self):
        guild_id = self.main_guild.id
        try:
            guild = self.get_guild(guild_id) or await self.fetch_guild(guild_id)
            if guild:
                data = {
                    emoji.name: {
                        "id": emoji.id,
                        "animated": emoji.animated,
                        "syntax": f"{'<a:' if emoji.animated else '<:'}{emoji.name}:{emoji.id}>"
                    }
                    for emoji in guild.emojis
                }
                Path("data").mkdir(exist_ok=True)
                with open("data/emojis.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                logger.info("[bot] Emojis saved to 'data/emojis.json'")
            else:
                logger.warning(
                    f"[bot] Main guild with ID {guild_id} not found.")
        except Exception as e:
            logger.error(f"[bot] Error exporting emojis: {e}", exc_info=True)

    def _load_emojis_from_file(self) -> dict:
        try:
            with open("data/emojis.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(
                f"[bot] Error loading emojis from file: {e}", exc_info=True)
            return {}

    async def on_ready(self):
        logger.info(f"[bot] Bot is online as {self.user} (ID: {self.user.id})")

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)


if __name__ == "__main__":
    token = os.getenv("bot_key")
    if not token:
        logger.error("Environment variable 'bot_key' is not set.")
        exit(1)

    bot = MyBot()
    bot.run(token)
