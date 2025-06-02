import os
import discord
import logging

from .cog import QuizCog
from .slash_commands import quiz_group

logger = logging.getLogger(__name__)

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        # 1) Haupt‐Cog laden (Scheduler, Frage‐Logik, Button/Modal‐Handler etc.)
        await bot.add_cog(QuizCog(bot))

        # 2) Slash‐Gruppe “/quiz” in den Command‐Tree einfügen (nur in dieser Guild)
        bot.tree.add_command(
            quiz_group,
            guild=discord.Object(id=MAIN_SERVER_ID)
        )

        logger.info(
            "[QuizCog] Cog und Slash‐Command‐Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[QuizCog] Fehler beim Setup: {e}", exc_info=True)
