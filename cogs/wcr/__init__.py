import discord
import os
from .cog import WCRCog
from .slash_commands import wcr_group

MAIN_SERVER_ID = int(os.getenv('server_id'))


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
    bot.tree.add_command(wcr_group, guild=discord.Object(id=MAIN_SERVER_ID))
