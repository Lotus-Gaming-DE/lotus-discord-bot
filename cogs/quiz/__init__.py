import os
from discord.ext import commands
from .cog import QuizCog
from .slash_commands import QuizCommands


async def setup(bot: commands.Bot):
    # Quiz-Logic-Cog
    await bot.add_cog(QuizCog(bot))
    # Slash-Commands-Cog (GroupCog kümmert sich um die Registrierung)
    await bot.add_cog(QuizCommands(bot))
