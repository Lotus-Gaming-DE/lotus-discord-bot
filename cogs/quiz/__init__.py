from .cog import QuizCog
from .slash_commands import QuizCommands


async def setup(bot):
    quiz_cog = QuizCog(bot)
    await bot.add_cog(quiz_cog)
    await bot.add_cog(QuizCommands(bot, quiz_cog))
