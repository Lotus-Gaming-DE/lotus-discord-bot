import discord
import os
from .cog import QuizCog
from .slash_commands import quiz_group

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot):
    await bot.add_cog(QuizCog(bot))
    bot.tree.add_command(quiz_group, guild=discord.Object(id=MAIN_SERVER_ID))
