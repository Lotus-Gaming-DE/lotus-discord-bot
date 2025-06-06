import discord

from log_setup import get_logger

from .cog import ChampionCog

logger = get_logger(__name__)


async def setup(bot: discord.ext.commands.Bot):
    """Register cog and slash command group for the champion system."""
    try:
        from .slash_commands import champion_group, syncroles

        # 1) Haupt-Cog: Champion-Daten und Rolle-Logik
        await bot.add_cog(ChampionCog(bot))

        # 2) Slash-Gruppe /champion in den Command-Tree einfügen
        bot.tree.add_command(champion_group, guild=bot.main_guild)
        bot.tree.add_command(syncroles, guild=bot.main_guild)

        logger.info(
            "[ChampionCog] Cog und Slash-Command-Gruppe erfolgreich registriert."
        )
    except Exception as e:
        logger.error(f"[ChampionCog] Fehler beim Setup: {e}", exc_info=True)
