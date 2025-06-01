# cogs/champion/__init__.py

import os
import discord
import logging

from .cog import ChampionCog
from .slash_commands import ChampionCommands, champion_group

logger = logging.getLogger(__name__)  # cogs.champion.__init__

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        # 1) Lade den Champion-Cog (Daten/DB/Role-Logik)
        await bot.add_cog(ChampionCog(bot))

        # 2) Lade den ChampionCommands-Cog (Slash-Command-Handler für /champion …)
        await bot.add_cog(ChampionCommands(bot))

        # 3) Registriere die gesamte /champion-Gruppe in der Tree-Registry (nur für unsere Gilde)
        #    Dadurch erscheinen im Backend alle Subcommands (give, remove, set, info, history, leaderboard).
        bot.tree.add_command(
            champion_group,
            guild=discord.Object(id=MAIN_SERVER_ID)
        )

        logger.info(
            "[ChampionCog] Cog und Slash-Command-Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[ChampionCog] Fehler beim Setup: {e}", exc_info=True)
