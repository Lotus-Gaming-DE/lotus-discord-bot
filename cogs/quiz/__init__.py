# cogs/quiz/__init__.py
from .cog import QuizCog


async def setup(bot):
    await bot.add_cog(QuizCog(bot))
