from discord.ext import commands

from .cog import ForeverCog
from .cog import setup as _setup_cog


async def setup(bot: commands.Bot) -> None:
    await _setup_cog(bot)
    from .slash_commands import forever_group

    bot.tree.add_command(forever_group, guild=bot.main_guild)


__all__ = ["ForeverCog", "setup"]
