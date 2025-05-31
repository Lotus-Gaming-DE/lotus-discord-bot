import discord
import os
import logging
from discord.ext import commands

from .cog import QuizCog
from .slash_commands import QuizCommands

logger = logging.getLogger(__name__)

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
GUILD_ID = int(SERVER_ID)


async def setup(bot: commands.Bot):
    await bot.add_cog(QuizCog(bot))

    quiz_group = QuizCommands(bot)
    await bot.add_cog(quiz_group)
    bot.tree.add_command(quiz_group, guild=discord.Object(id=GUILD_ID))

    logger.info(
        "[QuizCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
