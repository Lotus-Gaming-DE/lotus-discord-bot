# cogs/wcr/__init__.py
from .cog import WCRCog


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
