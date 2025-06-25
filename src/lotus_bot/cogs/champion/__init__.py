from discord.ext import commands

from lotus_bot.log_setup import get_logger

from .cog import ChampionCog
from lotus_bot.utils.setup_helpers import register_cog_and_group

logger = get_logger(__name__)


async def setup(bot: commands.Bot):
    """Registriert Cog und Slash-Befehle für das Champion-System."""
    try:
        from .slash_commands import champion_group, syncroles

        await register_cog_and_group(bot, ChampionCog, champion_group)
        bot.tree.add_command(syncroles, guild=bot.main_guild)

        logger.info(
            "[ChampionCog] Cog and slash command group registered successfully."
        )
    except Exception as e:
        logger.error(f"[ChampionCog] Error during setup: {e}", exc_info=True)
