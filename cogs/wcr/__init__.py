import discord
import os
from .cog import WCRCog
from .slash_commands import wcr_group

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
    bot.tree.add_command(wcr_group, guild=discord.Object(id=MAIN_SERVER_ID))
