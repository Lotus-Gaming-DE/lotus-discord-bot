"""WoW Forever: Battle.net-Claims, Offi-Meldungen und Champion-Punkte.

Alle zehn Minuten liest der Bot aus Lotus Link, wer welchen Char per Battle.net
verbunden hat, und die Gildenlisten von Silent, Crimson und Golden Lotus.

* Neue Verbindung → Meldung in #wow-logs mit Button „In Offi-Note eingetragen“.
  Bestätigen muss niemand mehr, der Login beweist den Besitz.
* Gildenrolle: Wer einen Char einer Lotus-Gilde verbunden hat, bekommt ihre
  Discord-Rolle. Steht kein verbundener Char mehr in der Gilde, fällt sie weg.
* Char nicht mehr in der Gildenliste → Austritts-Meldung (mit „gelistet seit“).
* Discord verlassen → Meldung mit Button „Runtergestuft“.
* Pings an die Gildenrolle höchstens einmal pro Stunde, gesammelt.
* Täglich um 9 Uhr → Offi-Sync-Report je Gilde (Ränge, die nicht passen).
* Champion-Punkte nur für Fortschritt nach dem Verbinden: Stufen-Meilensteine
  über dem Ausgangsstand und Dungeon-Runs auf diesem Server, die nach dem Start
  dieses Systems stattgefunden haben. Twinks zählen voll.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
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
    ForeverGuild,
    build_report,
    discord_left_notice,
    guild_left_notice,
    link_notice,
    lotus_guild_of,
    milestones_reached,
    mention,
    ping_text,
    report_sections,
    role_holders,
    roster_is_plausible,
)
from .registry import GuildMember, LinkedCharacter, PgRegistry, Registry, Snapshot
from .store import ForeverStore, Tracked

logger = get_logger(__name__)

SYNC_INTERVAL = 10 * 60
REPORT_HOUR = 9
BERLIN = ZoneInfo("Europe/Berlin")
# #wow-logs, derselbe Kanal wie die Claim-Meldungen von Black Lotus.
DEFAULT_LOG_CHANNEL_ID = 1544601948169314324
RUNS_SINCE_KEY = "runs_since"
LAST_REPORT_KEY = "last_report_date"
LAST_PING_KEY = "last_ping_at"
ROLE_STRIP_KEY = "role_strip_after"
# Pings an die Gildenrolle sammeln, damit die Leitung nicht zugespammt wird.
PING_INTERVAL = timedelta(hours=1)
# Wer die Rolle bisher selbst gewählt hat, bekommt so lange Zeit zum Verbinden.
ROLE_GRACE = timedelta(days=3)
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
        self._last_snapshot: Snapshot | None = None
        if hasattr(bot, "add_view"):
            bot.add_view(ClaimNoticeView(self))
            bot.add_view(DemoteNoticeView(self))
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
                await self.ping_if_due()
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
            links: list[tuple[LinkedCharacter, ForeverGuild, GuildMember | None]] = []
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
                    links.append((char, guild, member))
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
                    links.append((char, guild, member))
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

            departures, absent = await self._check_presence(snapshot, stamp)
            left = await self._roster_changes(snapshot, stamp)
            self._last_snapshot = snapshot

        for char, guild, member in links:
            await self._post_link(snapshot, char, guild, member, stamp)
        for text in left:
            await self._send([text])
        for user_id in departures:
            await self._post_departure(snapshot, user_id, stamp)
        await self.sync_roles(snapshot, absent, now)
        return snapshot

    # ------------------------------------------------------------ meldungen

    async def _post_link(
        self,
        snapshot: Snapshot,
        char: LinkedCharacter,
        guild: ForeverGuild,
        member: GuildMember | None,
        stamp: str,
    ) -> None:
        mine = {
            c.blizzard_id
            for c in snapshot.linked
            if c.discord_user_id == char.discord_user_id
            and c.character_id != char.character_id
        }
        others = [
            m
            for m in snapshot.members
            if m.guild_slug == guild.slug and m.blizzard_id in mine
        ]
        discord_member = self._member(char.discord_user_id)
        text = link_notice(
            char,
            guild,
            member,
            discord_name=getattr(discord_member, "name", None),
            others=others,
        )
        await self._send_notice(
            text, ClaimNoticeView(self), "link", guild, char.name, stamp
        )

    async def _roster_changes(self, snapshot: Snapshot, stamp: str) -> list[str]:
        """Vergleicht die Gildenlisten mit dem letzten Stand: Wer fehlt, ist raus."""
        owner_of = {c.blizzard_id: c.discord_user_id for c in snapshot.linked}
        guild_of = {m.blizzard_id: m.guild_slug for m in snapshot.members}
        notices: list[str] = []
        for guild in GUILDS:
            if guild.slug not in snapshot.rosters_loaded:
                continue
            current = [m for m in snapshot.members if m.guild_slug == guild.slug]
            previous = await self.store.roster(guild.slug)
            if not roster_is_plausible(len(previous), len(current)):
                logger.warning(
                    "[ForeverCog] Gildenliste %s unplausibel (%d → %d), übersprungen.",
                    guild.slug,
                    len(previous),
                    len(current),
                )
                continue
            ids = {m.blizzard_id for m in current}
            for blizzard_id, (old, since) in sorted(
                previous.items(), key=lambda item: item[1][0].name.casefold()
            ):
                if blizzard_id in ids:
                    continue
                moved = GUILDS_BY_SLUG.get(guild_of.get(blizzard_id, ""))
                notices.append(
                    guild_left_notice(
                        guild,
                        old,
                        owner_id=owner_of.get(blizzard_id),
                        listed_since=since,
                        moved_to=moved,
                    )
                )
            await self.store.replace_roster(guild.slug, current, stamp)
        return notices

    async def _check_presence(
        self, snapshot: Snapshot, stamp: str
    ) -> tuple[list[int], set[int]]:
        """Findet verbundene Spieler, die den Discord verlassen haben.

        Gibt die neu Gegangenen (noch nicht gemeldet) und alle Abwesenden
        zurück. Wer zurückkommt, wird wieder normal behandelt.
        """
        discord_guild = self._main_guild()
        if discord_guild is None:
            return [], set()
        in_roster = {m.blizzard_id for m in snapshot.members}
        owners = {
            c.discord_user_id for c in snapshot.linked if c.blizzard_id in in_roster
        }
        known = await self.store.departed()
        new: list[int] = []
        absent: set[int] = set()
        for user_id in sorted(owners | known):
            if await self._present(discord_guild, user_id):
                if user_id in known:
                    await self.store.clear_departed(user_id)
                continue
            absent.add(user_id)
            if user_id in owners and await self.store.mark_departed(user_id, stamp):
                new.append(user_id)
        return new, absent

    async def _post_departure(
        self, snapshot: Snapshot, user_id: int, stamp: str
    ) -> None:
        mine = {c.blizzard_id for c in snapshot.linked if c.discord_user_id == user_id}
        for guild in GUILDS:
            chars = [
                m
                for m in snapshot.members
                if m.guild_slug == guild.slug
                and m.blizzard_id in mine
                and (guild.layout is None or m.rank < guild.layout.initiate)
            ]
            if not chars:
                continue
            label = ", ".join(sorted(m.name for m in chars))
            await self._send_notice(
                discord_left_notice(guild, user_id, chars),
                DemoteNoticeView(self),
                "discord_left",
                guild,
                label,
                stamp,
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Sofort melden, nicht erst beim nächsten Abgleich."""
        main_guild_id = getattr(self.bot, "main_guild_id", None)
        if main_guild_id is not None and member.guild.id != main_guild_id:
            return
        snapshot = self._last_snapshot
        if snapshot is None:
            return  # der nächste Abgleich holt es nach
        if not any(c.discord_user_id == member.id for c in snapshot.linked):
            return
        stamp = datetime.now(timezone.utc).isoformat()
        if await self.store.mark_departed(member.id, stamp):
            await self._post_departure(snapshot, member.id, stamp)

    # --------------------------------------------------------------- rollen

    async def _strip_allowed(self, now: datetime) -> tuple[bool, datetime]:
        raw = await self.store.get_setting(ROLE_STRIP_KEY)
        if raw is None:
            after = now + ROLE_GRACE
            await self.store.set_setting(ROLE_STRIP_KEY, after.isoformat())
        else:
            after = datetime.fromisoformat(raw)
        return now >= after, after

    async def sync_roles(
        self, snapshot: Snapshot, absent: set[int], now: datetime
    ) -> dict[str, tuple[list[int], list[int]]]:
        """Gildenrolle = verbundener Char in dieser Gilde. Wie bei Black Lotus.

        Weggenommen wird nur, wenn die Gildenliste vorliegt und nicht leer ist,
        sonst verlöre bei einem Fehler in Lotus Link jeder seine Rolle.
        """
        discord_guild = self._main_guild()
        if discord_guild is None:
            return {}
        holders = role_holders(
            snapshot.linked, snapshot.members, snapshot.rosters_loaded, absent
        )
        strip, _ = await self._strip_allowed(now)
        changes: dict[str, tuple[list[int], list[int]]] = {}
        for guild in GUILDS:
            role = discord_guild.get_role(guild.role_id)
            if role is None:
                logger.warning("[ForeverCog] Rolle %s fehlt.", guild.role_id)
                continue
            wanted = holders[guild.slug]
            granted: list[int] = []
            removed: list[int] = []
            for user_id in sorted(wanted):
                member = discord_guild.get_member(user_id)
                if member is None or role in member.roles:
                    continue
                if await self._change_role(member, role, add=True):
                    granted.append(user_id)
            has_roster = guild.slug in snapshot.rosters_loaded and any(
                m.guild_slug == guild.slug for m in snapshot.members
            )
            if strip and has_roster:
                for member in list(role.members):
                    if member.id in wanted or getattr(member, "bot", False):
                        continue
                    if await self._change_role(member, role, add=False):
                        removed.append(member.id)
            if granted or removed:
                changes[guild.slug] = (granted, removed)
                await self._send([role_change_text(guild, granted, removed, self.who)])
        return changes

    async def _change_role(self, member, role, *, add: bool) -> bool:
        try:
            if add:
                await member.add_roles(role, reason="Char per Battle.net verbunden")
            else:
                await member.remove_roles(
                    role, reason="Kein verbundener Char mehr in der Gilde"
                )
            return True
        except discord.Forbidden:
            logger.warning(
                "[ForeverCog] Keine Rechte für Rolle %s (Rollenhierarchie prüfen).",
                role.id,
            )
        except discord.HTTPException as exc:
            logger.warning("[ForeverCog] Rolle %s nicht geändert: %s", role.id, exc)
        return False

    # ----------------------------------------------------------------- pings

    async def ping_if_due(self, now: datetime | None = None) -> int:
        """Einmal pro Stunde: neue offene Meldungen je Gilde, ein Ping pro Gilde."""
        now = now or datetime.now(timezone.utc)
        raw = await self.store.get_setting(LAST_PING_KEY)
        if raw is not None and now - datetime.fromisoformat(raw) < PING_INTERVAL:
            return 0
        await self.store.set_setting(LAST_PING_KEY, now.isoformat())
        if raw is None:
            return 0  # erst eine Stunde sammeln
        channel = await self._channel()
        if channel is None:
            return 0
        sent = 0
        for guild in GUILDS:
            rows = await self.store.unpinged(guild.slug)
            if not rows:
                continue
            text = ping_text(
                guild,
                rows,
                await self.store.open_count(guild.slug),
                lambda mid: self._jump_url(channel, mid),
            )
            try:
                await channel.send(
                    text,
                    allowed_mentions=discord.AllowedMentions(
                        everyone=False,
                        users=False,
                        roles=[discord.Object(guild.role_id)],
                    ),
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("[ForeverCog] Ping nicht gesendet: %s", exc)
                continue
            await self.store.mark_pinged([r[0] for r in rows], now.isoformat())
            sent += 1
        return sent

    def _jump_url(self, channel, message_id: int) -> str:
        guild_id = getattr(self.bot, "main_guild_id", 0)
        return (
            f"https://discord.com/channels/{guild_id}/{getattr(channel, 'id', 0)}"
            f"/{message_id}"
        )

    # ---------------------------------------------------------------- button

    async def handle_done(self, interaction: discord.Interaction, verb: str) -> None:
        message = interaction.message
        notice = await self.store.notice(message.id) if message else None
        if notice is None:
            await interaction.response.send_message(
                "❌ Diese Meldung ist nicht mehr aktiv.", ephemeral=True
            )
            return
        guild = GUILDS_BY_SLUG.get(notice["guild_slug"])
        if guild is None or not may_handle(interaction.user, guild):
            name = guild.name if guild else "dieser Gilde"
            await interaction.response.send_message(
                f"❌ Das darf nur die Leitung von {name}.", ephemeral=True
            )
            return
        now = datetime.now(timezone.utc).isoformat()
        if not await self.store.mark_done(message.id, interaction.user.id, now):
            await interaction.response.send_message(
                "Das hat schon jemand erledigt.", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            content=f"{message.content}\n✅ {verb} von <@{interaction.user.id}>",
            view=None,
            allowed_mentions=NO_PINGS,
        )

    # -------------------------------------------------------------- discord

    def _main_guild(self):
        get_guild = getattr(self.bot, "get_guild", None)
        guild_id = getattr(self.bot, "main_guild_id", None)
        if callable(get_guild) and guild_id is not None:
            guild = get_guild(guild_id)
            if guild is not None:
                return guild
        guild = getattr(self.bot, "main_guild", None)
        return guild if hasattr(guild, "get_role") else None

    def who(self, user_id: int) -> str:
        """Erwähnung plus Name. Discord zeigt Erwähnungen nur für Nutzer, die
        die App des Betrachters gerade geladen hat, alle anderen als
        „@unknown-user“. Der Name dahinter bleibt immer lesbar."""
        member = self._member(user_id)
        name = getattr(member, "display_name", None) or getattr(member, "name", None)
        if not name:
            return mention(user_id)
        name = discord.utils.escape_mentions(discord.utils.escape_markdown(name))
        return f"{mention(user_id)} ({name})"

    def _member(self, user_id: int):
        guild = self._main_guild()
        return guild.get_member(user_id) if guild is not None else None

    async def _present(self, guild, user_id: int) -> bool:
        """Nur ein bestätigtes 404 heißt „weg“, Störungen zählen als „da“."""
        if guild.get_member(user_id) is not None:
            return True
        try:
            await guild.fetch_member(user_id)
            return True
        except discord.NotFound:
            return False
        except discord.HTTPException:
            return True

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

    def report_chunks(
        self,
        snapshot: Snapshot,
        absent: set[int] | frozenset[int] = frozenset(),
        extra: list[tuple[str | None, list[str]]] | None = None,
    ) -> list[str]:
        from lotus_bot.cogs.wow.cog import _pack_digest_sections_into_chunks

        # Wer den Discord verlassen hat, zählt wie unverbunden (wie bei Black Lotus).
        owner_of = {
            c.blizzard_id: c.discord_user_id
            for c in snapshot.linked
            if c.discord_user_id not in absent
        }
        sections: list[tuple[str | None, list[str]]] = []
        for guild in GUILDS:
            if guild.layout is None or guild.slug not in snapshot.rosters_loaded:
                continue
            members = [m for m in snapshot.members if m.guild_slug == guild.slug]
            report = build_report(guild, members, owner_of)
            sections.extend(report_sections(report, self.who))
        sections.extend(extra or [])
        if not sections:
            return []
        header = (None, ["🔄 **Offi-Sync-Report WoW Forever**"])
        return _pack_digest_sections_into_chunks([header] + sections)

    async def post_report(self, snapshot: Snapshot, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        local = now.astimezone(BERLIN)
        absent = await self.store.departed()
        chunks = self.report_chunks(
            snapshot, absent, await self._grace_sections(snapshot, absent, now)
        )
        posted = 0
        if chunks:
            posted = await self._send(chunks)
            if posted < len(chunks):
                return posted  # morgen nicht überspringen, nächste Runde erneut
        await self.store.set_setting(LAST_REPORT_KEY, local.date().isoformat())
        return posted

    async def _grace_sections(
        self, snapshot: Snapshot, absent: set[int], now: datetime
    ) -> list[tuple[str | None, list[str]]]:
        """Solange die Übergangsfrist läuft: Wer hat die Rolle ohne Verbindung?"""
        strip, after = await self._strip_allowed(now)
        discord_guild = self._main_guild()
        if strip or discord_guild is None:
            return []
        holders = role_holders(
            snapshot.linked, snapshot.members, snapshot.rosters_loaded, absent
        )
        day = after.astimezone(BERLIN).strftime("%d.%m.")
        sections: list[tuple[str | None, list[str]]] = []
        for guild in GUILDS:
            role = discord_guild.get_role(guild.role_id)
            if role is None:
                continue
            without = sorted(
                m.id
                for m in role.members
                if m.id not in holders[guild.slug] and not getattr(m, "bot", False)
            )
            if without:
                sections.append(
                    (
                        f"{guild.icon} **{guild.name}: Rolle ohne verbundenen Char**, "
                        f"wird ab {day} entfernt. Bitte per Battle.net verbinden lassen:",
                        [", ".join(self.who(uid) for uid in without)],
                    )
                )
        return sections

    # --------------------------------------------------------------- posting

    async def _send_notice(
        self,
        text: str,
        view: discord.ui.View,
        kind: str,
        guild: ForeverGuild,
        label: str,
        stamp: str,
    ) -> None:
        """Eine Meldung mit Button. Gepingt wird später gesammelt (``ping_if_due``)."""
        channel = await self._channel()
        if channel is None:
            logger.warning("[ForeverCog] Log-Kanal nicht gefunden.")
            return
        try:
            message = await channel.send(text, view=view, allowed_mentions=NO_PINGS)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("[ForeverCog] Meldung nicht gesendet: %s", exc)
            return
        await self.store.add_notice(message.id, kind, guild.slug, label, stamp)

    async def _channel(self):
        wow = self.bot.get_cog("WoWCog")
        channel_id = DEFAULT_LOG_CHANNEL_ID
        if wow is not None and hasattr(wow, "get_claim_review_channel_id"):
            channel_id = await wow.get_claim_review_channel_id()
        return self.bot.get_channel(channel_id)

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


def may_handle(user, guild: ForeverGuild) -> bool:
    """Leitung der Gilde: wer #wow-logs sieht und die Gildenrolle hat, oder Admins."""
    permissions = getattr(user, "guild_permissions", None)
    if permissions is not None and permissions.manage_guild:
        return True
    return any(r.id == guild.role_id for r in getattr(user, "roles", []))


def role_change_text(
    guild: ForeverGuild,
    granted: list[int],
    removed: list[int],
    name_of: Callable[[int], str] = mention,
) -> str:
    lines = [f"{guild.tag} · 🎭 Gildenrolle"]
    if granted:
        lines.append("Vergeben: " + ", ".join(name_of(uid) for uid in granted))
    if removed:
        lines.append(
            "Entfernt (kein verbundener Char mehr in der Gilde): "
            + ", ".join(name_of(uid) for uid in removed)
        )
    return "\n".join(lines)


class ClaimNoticeView(discord.ui.View):
    """Button unter „Neuer Claim“: Discord-Name steht in der Offi-Note."""

    def __init__(self, cog: ForeverCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="In Offi-Note eingetragen",
        emoji="📝",
        style=discord.ButtonStyle.success,
        custom_id="forever_notice:entered",
    )
    async def entered(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self.cog.handle_done(interaction, "In Offi-Note eingetragen")


class DemoteNoticeView(discord.ui.View):
    """Button unter „Discord verlassen“: Chars sind im Spiel runtergestuft."""

    def __init__(self, cog: ForeverCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Runtergestuft",
        emoji="⬇️",
        style=discord.ButtonStyle.primary,
        custom_id="forever_notice:demoted",
    )
    async def demoted(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self.cog.handle_done(interaction, "Runtergestuft")


async def setup(bot: commands.Bot) -> None:
    dsn = os.getenv("LOTUS_LINK_DATABASE_URL")
    if not dsn:
        logger.info("[ForeverCog] LOTUS_LINK_DATABASE_URL fehlt, Forever-Abgleich aus.")
        return
    path = os.getenv("FOREVER_DB_PATH", "data/pers/forever/forever.db")
    await bot.add_cog(ForeverCog(bot, PgRegistry(dsn), ForeverStore(path)))
    logger.info("[ForeverCog] Cog registriert (Gilden: %s).", ", ".join(GUILDS_BY_SLUG))
