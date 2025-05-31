import os
import json
import logging
from pathlib import Path

import discord
from discord.ext import commands

print(os.getenv('bot_key'))

# ─── Logging configuration ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s:%(name)s: %(message)s"
)
logger = logging.getLogger("bot")

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
            sync_commands=False  # wir syncen nur Guild-Commands
        )

        # load guild id from environment
        guild_id = os.getenv("server_id")
        if not guild_id:
            logger.error("Environment variable 'server_id' is not set.")
            exit(1)
        self.main_guild = discord.Object(id=int(guild_id))

    async def setup_hook(self):
        # 1) export emojis
        await self._export_emojis()

        # 2) load all Cogs unter cogs/ (rekursiv), inkl. __init__.py
        for path in Path("./cogs").rglob("*.py"):
            module = ".".join(path.with_suffix("").parts)
            try:
                await self.load_extension(module)
                logger.info(f"[bot] Extension loaded: {module}")
            except Exception as e:
                logger.error(
                    f"[bot] Failed to load extension {module}: {e}", exc_info=True)

        # 3) sync guild-specific slash commands
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
                data = {}
                for emoji in guild.emojis:
                    data[emoji.name] = {
                        "id": emoji.id,
                        "animated": emoji.animated,
                        "syntax": f"{'<a:' if emoji.animated else '<:'}{emoji.name}:{emoji.id}>"
                    }
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
        logger.info(f"[bot] Bot is online as {self.user}")

    async def on_message(self, message):
        if message.author.bot:
            return
        await self.process_commands(message)


# ─── entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    token = os.getenv("bot_key")
    if not token:
        logger.error("Environment variable 'bot_key' is not set.")
        exit(1)

    bot = MyBot()
    bot.run(token)
