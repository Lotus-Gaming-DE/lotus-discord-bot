import os
import json
import logging
from pathlib import Path

import discord
from discord.ext import commands

# ─── Logging configuration ────────────────────────────────────────────────
# - „%(name)s“ gibt den Logger‐Namen (also __name__ des Moduls) aus.
# - Wir drosseln discord.py‐Logs auf WARNING, damit INFO‐Spamming unterbleibt.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s"
)
# Nur WARN und ERROR von discord selbst, damit wir nicht von dessen internen INFO-Zeilen erschlagen werden:
logging.getLogger("discord").setLevel(logging.WARNING)

logger = logging.getLogger("bot")  # Für alle bot.py‐Meldungen

# ─── Intents ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# ─── Bot class ────────────────────────────────────────────────────────────


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="§",
            intents=intents,
            sync_commands=False  # wir syncen nur Guild‐Commands
        )

        # Guild‐ID aus Umgebungsvariable laden
        guild_id = os.getenv("server_id")
        if not guild_id:
            logger.error("Environment variable 'server_id' is not set.")
            exit(1)

        # self.main_guild braucht nur eine einfache Discord.Object‐Referenz, um Guild‐Commands zu syncen
        self.main_guild = discord.Object(id=int(guild_id))

    async def setup_hook(self):
        # 1) Emojis exportieren (optional, wenn Du in data/emojis.json benötigst)
        await self._export_emojis()

        # 2) Alle Cogs unter cogs/ (rekursiv) laden
        for path in Path("./cogs").rglob("*.py"):
            # z.B. path = "cogs/champion/cog.py" → module = "cogs.champion.cog"
            module = ".".join(path.with_suffix("").parts)

            try:
                await self.load_extension(module)
                logger.info(f"[bot] Extension loaded: {module}")
            except Exception as e:
                logger.error(
                    f"[bot] Failed to load extension {module}: {e}", exc_info=True)

        # 3) Sync Guild‐spezifische Slash Commands
        try:
            await self.tree.sync(guild=self.main_guild)
            logger.info(
                f"[bot] Slash commands synced for guild {self.main_guild.id}")
        except Exception as e:
            logger.error(
                f"[bot] Failed to sync slash commands: {e}", exc_info=True)

    async def _export_emojis(self):
        """
        Exportiert alle Emojis aus der angegebenen Guild in data/emojis.json.
        Nützlich, wenn Du später in den Cogs Emoji‐Syntax brauchst.
        """
        guild_id = self.main_guild.id
        try:
            guild = self.get_guild(guild_id) or await self.fetch_guild(guild_id)
            if guild:
                data = {}
                for emoji in guild.emojis:
                    data[emoji.name] = {
                        "id": emoji.id,
                        "animated": emoji.animated,
                        "syntax": f"{'<a:' if emoji.animated else '<:'}{emoji.name}:{emoji.id}>"
                    }

                # Ordner anlegen, falls noch nicht vorhanden
                Path("data").mkdir(exist_ok=True)
                with open("data/emojis.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

                logger.info(f"[bot] Emojis saved to 'data/emojis.json'")
            else:
                logger.warning(
                    f"[bot] Main guild with ID {guild_id} not found.")
        except Exception as e:
            logger.error(f"[bot] Error exporting emojis: {e}", exc_info=True)

    async def on_ready(self):
        logger.info(f"[bot] Bot is online as {self.user} (ID: {self.user.id})")

    async def on_message(self, message):
        # Bot‐Nachrichten ignorieren
        if message.author.bot:
            return

        # Befehle / Cogs „on_message“ sicherstellen
        await self.process_commands(message)


# ─── Entry Point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Bot‐Token aus Umgebungsvariable laden
    token = os.getenv("bot_key")
    if not token:
        logger.error("Environment variable 'bot_key' is not set.")
        exit(1)

    # Instanz initialisieren und starten
    bot = MyBot()
    bot.run(token)
