from discord import app_commands
from discord.ext import commands


async def register_cog_and_group(
    bot: commands.Bot, cog_cls: type[commands.Cog], slash_group: app_commands.Group
) -> None:
    """Fügt ein Cog hinzu und registriert eine Slash-Command-Gruppe für die Haupt-Guild."""
    await bot.add_cog(cog_cls(bot))
    bot.tree.add_command(slash_group, guild=bot.main_guild)
