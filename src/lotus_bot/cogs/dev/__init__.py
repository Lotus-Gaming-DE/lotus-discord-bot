from __future__ import annotations

import discord.ext.commands as commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.setup_helpers import register_cog_and_group

from .cog import DevCog

logger = get_logger(__name__)


async def setup(bot: commands.Bot) -> None:
    """Registriert DevCog und /dev Slash-Command-Gruppe."""
    try:
        from .slash_commands import dev_group

        await register_cog_and_group(bot, DevCog, dev_group)
        logger.info("[DevCog] Cog und Slash-Commands registriert.")
    except Exception as exc:
        logger.error("[DevCog] Fehler beim Setup: %s", exc, exc_info=True)
