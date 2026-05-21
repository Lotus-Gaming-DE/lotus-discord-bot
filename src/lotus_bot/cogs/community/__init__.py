from .cog import CommunityCog


async def setup(bot) -> None:
    await bot.add_cog(CommunityCog(bot))
