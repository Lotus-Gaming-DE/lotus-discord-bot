from __future__ import annotations

from discord.ext import commands

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


class DevCog(commands.Cog):
    """Entwickler-Hilfsbefehle — nur für den Server-Owner."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
