from __future__ import annotations

import discord.ext.commands as commands

from lotus_bot.log_setup import get_logger

from .cog import BackupCog

logger = get_logger(__name__)


async def setup(bot: commands.Bot) -> None:
    """Registriert die BackupCog (keine eigene Slash-Gruppe, siehe /wow backup)."""
    try:
        await bot.add_cog(BackupCog(bot))
        logger.info("[BackupCog] Cog registriert.")
    except Exception as exc:
        logger.error("[BackupCog] Fehler beim Setup: %s", exc, exc_info=True)
