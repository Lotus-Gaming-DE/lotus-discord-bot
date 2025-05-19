from .cog import TourneyCog

"""
    blub
    """


async def setup(bot):
    await bot.add_cog(TourneyCog(bot))
