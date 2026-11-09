"""WoW Forever: Battle.net-Claims, Offi-Meldungen und Champion-Punkte.

Alle zehn Minuten liest der Bot aus Lotus Link, wer welchen Char per Battle.net
verbunden hat, und die Gildenlisten von Silent, Crimson und Golden Lotus.

* Neue Verbindung → Meldung in #wow-logs, damit die Offiziere den Rang im
  Spiel setzen. Bestätigen muss niemand mehr, der Login beweist den Besitz.
* Täglich um 9 Uhr → Offi-Sync-Report je Gilde (Ränge, die nicht passen).
* Champion-Punkte nur für Fortschritt nach dem Verbinden: Stufen-Meilensteine
  über dem Ausgangsstand und Dungeon-Runs auf diesem Server, die nach dem Start
  dieses Systems stattgefunden haben. Twinks zählen voll.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

from .logic import (
    GUILDS,
    GUILDS_BY_SLUG,
    LEVEL_MILESTONE_POINTS,
    RUN_ORGANIZER_POINTS,
    RUN_POINTS,
    build_report,
    link_notice,
    lotus_guild_of,
    milestones_reached,
    report_sections,
)
from .registry import PgRegistry, Registry, Snapshot
from .store import ForeverStore, Tracked

logger = get_logger(__name__)

SYNC_INTERVAL = 10 * 60
REPORT_HOUR = 9
BERLIN = ZoneInfo("Europe/Berlin")
# #wow-logs, derselbe Kanal wie die Claim-Meldungen von Black Lotus.
DEFAULT_LOG_CHANNEL_ID = 1544601948169314324
RUNS_SINCE_KEY = "runs_since"
LAST_REPORT_KEY = "last_report_date"
NO_PINGS = discord.AllowedMentions.none()


class ForeverCog(ManagedTaskCog):
    def __init__(
        self,
        bot: commands.Bot,
        registry: Registry,
        store: ForeverStore,
        *,
        start_loop: bool = True,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.registry = registry
        self.store = store
        self._sync_lock = asyncio.Lock()
        if start_loop:
            self.create_task(self._loop())

    # ------------------------------------------------------------------ loop

    async def _loop(self) -> None:
        await self.bot.wait_until_ready()
        while True:
            try:
                snapshot = await self.sync()
                if snapshot is not None and await self._report_due():
                    await self.post_report(snapshot)
            except Exception as exc:  # eine Runde darf den Bot nie stören
                logger.warning("[ForeverCog] Abgleich fehlgeschlagen: %s", exc)
            await asyncio.sleep(SYNC_INTERVAL)

    async def _report_due(self, now: datetime | None = None) -> bool:
        local = (now or datetime.now(timezone.utc)).astimezone(BERLIN)
        if local.hour < REPORT_HOUR:
            return False
        return await self.store.get_setting(LAST_REPORT_KEY) != local.date().isoformat()

    # ------------------------------------------------------------------ sync

    async def sync(self, now: datetime | None = None) -> Snapshot | None:
        now = now or datetime.now(timezone.utc)
        async with self._sync_lock:
            snapshot = await self.registry.snapshot(
                [g.slug for g in GUILDS], int(getattr(self.bot, "main_guild_id", 0))
            )
            stamp = now.isoformat()
            runs_since = await self.store.get_setting(RUNS_SINCE_KEY)
            if runs_since is None:
                # Runs vor dem Start dieses Systems geben keine Punkte.
                runs_since = stamp
                await self.store.set_setting(RUNS_SINCE_KEY, stamp)

            roster_guild = {m.blizzard_id: m.guild_slug for m in snapshot.members}
            member_by_id = {m.blizzard_id: m for m in snapshot.members}
            tracked = await self.store.tracked()
            notices: list[str] = []
            seen: set[int] = set()

            for char in snapshot.linked:
                guild = lotus_guild_of(char, roster_guild)
                if guild is None:
                    continue
                seen.add(char.character_id)
                member = member_by_id.get(char.blizzard_id)
                level = max(char.level, member.level if member else 0)
                known = tracked.get(char.character_id)
                if known is None:
                    # Ausgangsstand: was bis jetzt erreicht ist, zählt nicht.
                    await self.store.track(
                        Tracked(
                            char.character_id, char.discord_user_id, guild.slug, level
                        ),
                        stamp,
                    )
                    notices.append(link_notice(char, guild, member))
                    continue
                if (known.guild_slug, known.discord_user_id) != (
                    guild.slug,
                    char.discord_user_id,
                ):
                    await self.store.track(
                        Tracked(
                            char.character_id,
                            char.discord_user_id,
                            guild.slug,
                            known.baseline_level,
                        ),
                        stamp,
                    )
                    notices.append(link_notice(char, guild, member))
                for milestone in milestones_reached(known.baseline_level, level):
                    await self._award(
                        "level",
                        f"{char.character_id}:{milestone}",
                        char.discord_user_id,
                        LEVEL_MILESTONE_POINTS[milestone],
                        f"WoW Forever: {char.name} Level {milestone}",
                        stamp,
                    )

            for character_id in set(tracked) - seen:
                await self.store.untrack(character_id)

            since = datetime.fromisoformat(runs_since)
            for run in snapshot.runs:
                if run.recorded_at < since:
                    continue
                points = RUN_ORGANIZER_POINTS if run.is_organizer else RUN_POINTS
                role = "geleitet" if run.is_organizer else "gespielt"
                await self._award(
                    "run",
                    f"{run.run_id}:{run.discord_user_id}",
                    run.discord_user_id,
                    points,
                    f"WoW Forever: Dungeon-Run {role}",
                    stamp,
                )

        if notices:
            await self._post([(None, notices)])
        return snapshot

    async def _award(
        self, kind: str, key: str, user_id: int, points: int, reason: str, stamp: str
    ) -> None:
        champion = self.bot.get_cog("ChampionCog")
        if champion is None:
            return  # später erneut versuchen, nichts reservieren
        if not await self.store.claim_award(kind, key, stamp):
            return
        try:
            await champion.update_user_score(user_id, points, reason)
        except Exception as exc:
            logger.warning("[ForeverCog] Punkte nicht vergeben (%s): %s", key, exc)
            await self.store.release_award(kind, key)

    # ---------------------------------------------------------------- report

    def report_chunks(self, snapshot: Snapshot) -> list[str]:
        from lotus_bot.cogs.wow.cog import _pack_digest_sections_into_chunks

        owner_of = {c.blizzard_id: c.discord_user_id for c in snapshot.linked}
        sections: list[tuple[str | None, list[str]]] = []
        for guild in GUILDS:
            if guild.layout is None or guild.slug not in snapshot.rosters_loaded:
                continue
            members = [m for m in snapshot.members if m.guild_slug == guild.slug]
            report = build_report(guild, members, owner_of)
            sections.extend(report_sections(report))
        if not sections:
            return []
        header = (None, ["🔄 **Offi-Sync-Report WoW Forever**"])
        return _pack_digest_sections_into_chunks([header] + sections)

    async def post_report(self, snapshot: Snapshot, now: datetime | None = None) -> int:
        local = (now or datetime.now(timezone.utc)).astimezone(BERLIN)
        chunks = self.report_chunks(snapshot)
        posted = 0
        if chunks:
            posted = await self._send(chunks)
            if posted < len(chunks):
                return posted  # morgen nicht überspringen, nächste Runde erneut
        await self.store.set_setting(LAST_REPORT_KEY, local.date().isoformat())
        return posted

    # --------------------------------------------------------------- posting

    async def _channel(self):
        wow = self.bot.get_cog("WoWCog")
        channel_id = DEFAULT_LOG_CHANNEL_ID
        if wow is not None and hasattr(wow, "get_claim_review_channel_id"):
            channel_id = await wow.get_claim_review_channel_id()
        return self.bot.get_channel(channel_id)

    async def _post(self, sections: list[tuple[str | None, list[str]]]) -> int:
        from lotus_bot.cogs.wow.cog import _pack_digest_sections_into_chunks

        return await self._send(_pack_digest_sections_into_chunks(sections))

    async def _send(self, chunks: list[str]) -> int:
        channel = await self._channel()
        if channel is None:
            logger.warning("[ForeverCog] Log-Kanal nicht gefunden.")
            return 0
        posted = 0
        for chunk in chunks:
            try:
                await channel.send(chunk, allowed_mentions=NO_PINGS)
            except (discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("[ForeverCog] Meldung nicht gesendet: %s", exc)
                break
            posted += 1
        return posted

    async def cog_unload(self) -> None:
        super().cog_unload()
        await self.registry.close()
        await self.store.close()


async def setup(bot: commands.Bot) -> None:
    dsn = os.getenv("LOTUS_LINK_DATABASE_URL")
    if not dsn:
        logger.info("[ForeverCog] LOTUS_LINK_DATABASE_URL fehlt, Forever-Abgleich aus.")
        return
    path = os.getenv("FOREVER_DB_PATH", "data/pers/forever/forever.db")
    await bot.add_cog(ForeverCog(bot, PgRegistry(dsn), ForeverStore(path)))
    logger.info("[ForeverCog] Cog registriert (Gilden: %s).", ", ".join(GUILDS_BY_SLUG))
