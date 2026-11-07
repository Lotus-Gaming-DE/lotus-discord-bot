"""Meldet der Website lotusgaming.de, wie viele Leute gerade im Voice sind.

Es wird nur eine einzige Zahl übertragen: die Anzahl der Menschen (keine Bots)
in allen Sprach- und Stage-Kanälen außer dem AFK-Kanal. Keine Namen, keine IDs.
"""

from __future__ import annotations

import asyncio
import os

import aiohttp
import discord
from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

logger = get_logger(__name__)

DEFAULT_URL = "https://lotusgaming.de/api/voice"
INTERVAL_SECONDS = 5 * 60


def count_voice(guild: discord.Guild) -> int:
    """Zählt Menschen in allen Sprach-/Stage-Kanälen, ohne AFK-Kanal und Bots."""
    afk_id = guild.afk_channel.id if guild.afk_channel else None
    channels = list(guild.voice_channels) + list(guild.stage_channels)
    return sum(
        1
        for channel in channels
        if channel.id != afk_id
        for member in channel.members
        if not member.bot
    )


class WebsiteCog(ManagedTaskCog):
    def __init__(
        self,
        bot: commands.Bot,
        token: str,
        url: str = DEFAULT_URL,
        interval: float = INTERVAL_SECONDS,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.token = token
        self.url = url
        self.interval = interval
        self.create_task(self._loop())

    async def report(self, count: int) -> bool:
        """Schickt die Zahl an die Website. Gibt True bei Erfolg zurück."""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.url,
                    json={"count": count},
                    headers={"Authorization": f"Bearer {self.token}"},
                ) as resp:
                    if resp.status != 200:
                        logger.warning("[WebsiteCog] Website antwortet %s", resp.status)
                        return False
                    return True
        except Exception as exc:  # Netzwerkfehler dürfen den Bot nie stören
            logger.warning("[WebsiteCog] Melden fehlgeschlagen: %s", exc)
            return False

    async def report_once(self) -> bool:
        guild = self.bot.get_guild(self.bot.main_guild_id)
        if guild is None:
            return False
        return await self.report(count_voice(guild))

    async def _loop(self) -> None:
        await self.bot.wait_until_ready()
        while True:
            await self.report_once()
            await asyncio.sleep(self.interval)


async def setup(bot: commands.Bot) -> None:
    token = os.getenv("WEBSITE_VOICE_TOKEN")
    if not token:
        logger.info("[WebsiteCog] WEBSITE_VOICE_TOKEN fehlt – Voice-Meldung aus.")
        return
    url = os.getenv("WEBSITE_VOICE_URL", DEFAULT_URL)
    await bot.add_cog(WebsiteCog(bot, token, url))
    logger.info("[WebsiteCog] Cog registriert.")
