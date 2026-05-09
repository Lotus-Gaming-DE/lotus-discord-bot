from __future__ import annotations

import asyncio
from dataclasses import dataclass

import discord
from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

from .api import DEFAULT_LOCALE, DEFAULT_NAMESPACE, fetch_guild_roster
from .data import RosterMember, WoWData, parse_roster_member

logger = get_logger(__name__)

DEFAULT_REALM_SLUG = "soulseeker"
DEFAULT_GUILD_SLUG = "black-lotus"
DEFAULT_GUILD_NAME = "Black Lotus"
DEFAULT_POLL_INTERVAL = 3 * 60 * 60
MILESTONE_LEVELS = {30, 40, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60}


@dataclass
class Milestone:
    member: RosterMember
    level: int


@dataclass
class ScanResult:
    member_count: int
    milestones: list[Milestone]
    posted: int = 0


class WoWCog(ManagedTaskCog):
    """Track Black Lotus WoW Classic Hardcore milestones."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        self.data = WoWData("data/pers/wow/wow.db")
        self.realm_slug = DEFAULT_REALM_SLUG
        self.guild_slug = DEFAULT_GUILD_SLUG
        self.guild_name = DEFAULT_GUILD_NAME
        self.namespace = DEFAULT_NAMESPACE
        self.locale = DEFAULT_LOCALE
        self.poll_interval = DEFAULT_POLL_INTERVAL
        self._scan_lock = asyncio.Lock()
        self._track_task = self.create_task
        self._track_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while True:
            try:
                channel_id = await self.data.get_setting("announcement_channel_id")
                if channel_id:
                    await self.scan(post=True, persist=True)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("[WoWCog] Polling failed: %s", exc, exc_info=True)
            await asyncio.sleep(self.poll_interval)

    async def set_announcement_channel(self, channel_id: int) -> None:
        await self.data.set_setting("announcement_channel_id", str(channel_id))

    async def get_announcement_channel_id(self) -> int | None:
        value = await self.data.get_setting("announcement_channel_id")
        return int(value) if value else None

    async def fetch_roster(self) -> list[RosterMember]:
        raw_members = await fetch_guild_roster(
            self.realm_slug,
            self.guild_slug,
            namespace=self.namespace,
            locale=self.locale,
        )
        members = [parse_roster_member(raw) for raw in raw_members]
        return [member for member in members if member is not None]

    async def scan(self, *, post: bool = True, persist: bool = True) -> ScanResult:
        """Fetch the roster, detect milestones, optionally post and persist them."""
        async with self._scan_lock:
            previous = await self.data.get_snapshot()
            current = await self.fetch_roster()
            milestones = await self._detect_milestones(previous, current)
            posted = 0

            if post and milestones:
                posted = await self._post_milestones(milestones)
                for milestone in milestones[:posted]:
                    await self.data.record_milestone(
                        milestone.member.character_key, milestone.level
                    )

            if persist:
                await self.data.replace_snapshot(current)
                await self.data.mark_scanned()

            return ScanResult(
                member_count=len(current), milestones=milestones, posted=posted
            )

    async def _detect_milestones(
        self,
        previous: dict[str, RosterMember],
        current: list[RosterMember],
    ) -> list[Milestone]:
        milestones: list[Milestone] = []
        for member in current:
            old = previous.get(member.character_key)
            if not old or member.level <= old.level:
                continue
            for level in sorted(MILESTONE_LEVELS):
                if old.level < level <= member.level and not await self.data.milestone_exists(
                    member.character_key, level
                ):
                    milestones.append(Milestone(member=member, level=level))
        return milestones

    async def _post_milestones(self, milestones: list[Milestone]) -> int:
        channel_id = await self.get_announcement_channel_id()
        if channel_id is None:
            logger.warning("[WoWCog] No announcement channel configured.")
            return 0
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning("[WoWCog] Announcement channel %s not found.", channel_id)
            return 0

        posted = 0
        for milestone in milestones:
            await channel.send(self.format_milestone(milestone))
            posted += 1
        return posted

    def format_milestone(self, milestone: Milestone) -> str:
        return (
            f"{milestone.member.name} hat Level {milestone.level} erreicht. "
            f"{self.guild_name} gratuliert herzlich!"
        )

    async def status(self) -> dict[str, object]:
        channel_id = await self.get_announcement_channel_id()
        return {
            "guild": self.guild_name,
            "realm": self.realm_slug,
            "channel_id": channel_id,
            "last_scan_at": await self.data.last_scan_at(),
            "member_count": await self.data.member_count(),
            "poll_interval": self.poll_interval,
        }

    def cog_unload(self) -> None:
        super().cog_unload()
        self.create_task(self.data.close())
