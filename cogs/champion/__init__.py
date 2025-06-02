# cogs/champion/__init__.py

import os
import logging
import discord

# ChampionCog enthält ab jetzt auch alle Slash‐Befehle
from .cog import ChampionCog, champion_group

logger = logging.getLogger(__name__)  # cogs.champion.__init__

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)


async def setup(bot: discord.ext.commands.Bot):
    try:
        # 1) Lade ChampionCog (Daten‐Logik + Slash‐Befehle)
        await bot.add_cog(ChampionCog(bot))

        # 2) Registriere die gesamte /champion‐Gruppe (inkl. aller Unterbefehle) nur für unsere Guild
        bot.tree.add_command(
            champion_group,
            guild=discord.Object(id=MAIN_SERVER_ID)
        )

        logger.info(
            "[ChampionCog] Cog und Slash‐Command‐Gruppe erfolgreich registriert.")
    except Exception as e:
        logger.error(f"[ChampionCog] Fehler beim Setup: {e}", exc_info=True)
