"""Meldet der Website lotusgaming.de die Discord-Zahlen.

Übertragen werden drei Zahlen: Menschen (keine Bots) in allen Sprach- und
Stage-Kanälen außer dem AFK-Kanal, Mitglieder gesamt und Mitglieder online.
Discord drosselt Abfragen von Cloudflare aus, deshalb liefert der Bot auch
Mitglieder- und Online-Zahl.

Dazu kommen Spieler-Gruppen für die Aktivitätsquote der Forever-Gilden: welche
Chars (aus Lotus Link) zum selben Spieler gehören. Übertragen werden nur
Kurzschlüssel der Charakter-IDs, keine Namen und keine Discord-IDs.
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
MAX_GROUPS = 5000
MAX_GROUP_SIZE = 50
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


def char_key(character_id: int) -> str:
    """Kurzschlüssel einer Charakter-ID, gleich wie charKey() der Website (FNV-1a, base36)."""
    h = 0x811C9DC5
    for ch in str(character_id):
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        h, r = divmod(h, 36)
        out = digits[r] + out
        if h == 0:
            return out


def player_groups(snapshot) -> list[list[str]]:
    """Chars je Spieler (Discord-Konto), die in einer unserer Gildenlisten stehen.

    Nur Spieler mit mindestens zwei Chars; ein einzelner Char zählt auf der
    Website ohnehin als eigener Spieler.
    """
    if snapshot is None:
        return []
    in_roster = {m.blizzard_id for m in snapshot.members}
    by_user: dict[int, set[str]] = {}
    for char in snapshot.linked:
        if char.blizzard_id in in_roster:
            by_user.setdefault(char.discord_user_id, set()).add(
                char_key(char.blizzard_id)
            )
    groups = sorted(
        sorted(keys)[:MAX_GROUP_SIZE] for keys in by_user.values() if len(keys) >= 2
    )
    return groups[:MAX_GROUPS]


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

    async def report(
        self,
        count: int,
        members: int | None = None,
        online: int | None = None,
        groups: list[list[str]] | None = None,
    ) -> bool:
        """Schickt die Zahlen an die Website. Gibt True bei Erfolg zurück."""
        payload: dict[str, object] = {"count": count}
        if members is not None:
            payload["members"] = members
        if online is not None:
            payload["online"] = online
        if groups:
            payload["groups"] = groups
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.url,
                    json=payload,
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
        members, online = await self.member_counts(guild)
        forever = self.bot.get_cog("ForeverCog")
        groups = player_groups(getattr(forever, "_last_snapshot", None))
        return await self.report(count_voice(guild), members, online, groups)

    async def member_counts(
        self, guild: discord.Guild
    ) -> tuple[int | None, int | None]:
        """Mitglieder gesamt und online (Discords Näherungswerte, ohne Presence-Intent)."""
        try:
            full = await self.bot.fetch_guild(guild.id, with_counts=True)
            return (
                full.approximate_member_count or guild.member_count,
                full.approximate_presence_count,
            )
        except Exception as exc:  # Abfrage darf die Voice-Meldung nie verhindern
            logger.warning("[WebsiteCog] Mitgliederzahlen nicht abrufbar: %s", exc)
            return guild.member_count, None

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
