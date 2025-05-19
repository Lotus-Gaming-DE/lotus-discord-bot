from .cog import TourneyCog

async def setup(bot):
    await bot.add_cog(TourneyCog(bot))
