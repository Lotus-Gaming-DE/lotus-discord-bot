from __future__ import annotations

import asyncio
import difflib
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import discord
from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

from .api import (
    DEFAULT_LOCALE,
    DEFAULT_NAMESPACE,
    WoWAPIError,
    fetch_character_profile,
    fetch_guild_roster,
    wow_api_session,
)
from .data import (
    BankCharacter,
    CharacterClaim,
    CharacterKnownRecipe,
    CharacterProfession,
    Cooldown,
    GearMilestoneEvent,
    ProfessionSkillEvent,
    RecipeLearningEvent,
    RosterMember,
    WoWData,
    parse_roster_member,
)

logger = get_logger(__name__)

DEFAULT_REALM_SLUG = "soulseeker"
DEFAULT_GUILD_SLUG = "black-lotus"
DEFAULT_GUILD_NAME = "Black Lotus"
DEFAULT_POLL_INTERVAL = 3 * 60 * 60
DEFAULT_CLAIM_REVIEW_CHANNEL_ID = 1184115540822855772
DEFAULT_PANEL_CHANNEL_ID = 1463577361562992807
DEFAULT_DIGEST_HOUR = 9
try:
    DIGEST_TIMEZONE = ZoneInfo("Europe/Berlin")
except ZoneInfoNotFoundError:  # pragma: no cover - depends on host tzdata
    DIGEST_TIMEZONE = datetime.now().astimezone().tzinfo or timezone.utc
MILESTONE_LEVELS = {30, 40, 50, 60}
GHOST_REFRESH_CONCURRENCY = 8
ITEM_LEVEL_MILESTONES = {50, 55, 60, 65, 70, 75}
ITEM_LEVEL_MILESTONE_POINTS = {50: 2, 55: 2, 60: 5, 65: 8, 70: 15, 75: 25}
CLAIMED_MILESTONE_POINTS = {30: 5, 40: 10, 50: 20, 60: 50}
# Recipe rewards scale with two axes: how the recipe is acquired (source)
# and how skilled the crafter has to be (required_skill bracket).
RECIPE_POINTS_BY_SOURCE = {
    "world_drop": 4,  # rare BoE world drops
    "pickpocketed": 3,  # rogue-exclusive
    "drop": 2,  # regular mob/boss drops (incl. drop+vendor)
    "quest": 1,  # deterministic quest reward
}
RECIPE_SKILL_BRACKETS = [
    (276, 3.0),  # endgame
    (201, 2.0),
    (101, 1.5),
    (0, 1.0),
]
EPIC_RECIPE_BASE_POINTS = 10  # special hand-curated spell IDs
# Profession-skill milestones (cumulative): each threshold crossed awards
# the points once. Total for a 1→300 run is 46 points.
PROFESSION_SKILL_MILESTONES = {75: 3, 150: 6, 225: 12, 300: 25}
# Hardcoded craft-cooldown groups for WoW Classic Era 1.x. Add new entries
# here if a content patch introduces more (e.g. Spellcloth in TBC).
COOLDOWN_GROUPS: dict[str, dict] = {
    "alchemy_transmute": {
        "label": "Transmutationen",
        "hours": 48,
        "spell_ids": frozenset(
            {
                "spell.17187",  # Transmute: Arcanite
                "spell.11479",  # Transmute: Iron to Gold
                "spell.11480",  # Transmute: Mithril to Truesilver
                "spell.17559",  # Transmute: Air to Fire
                "spell.17560",  # Transmute: Fire to Earth
                "spell.17561",  # Transmute: Earth to Water
                "spell.17562",  # Transmute: Water to Air
                "spell.17563",  # Transmute: Undeath to Water
                "spell.17564",  # Transmute: Water to Undeath
                "spell.17565",  # Transmute: Life to Earth
                "spell.17566",  # Transmute: Earth to Life
                "spell.25146",  # Transmute: Elemental Fire
            }
        ),
    },
    "tailoring_mooncloth": {
        "label": "Mondstoff",
        "hours": 96,
        "spell_ids": frozenset({"spell.18560"}),
    },
}
# Reverse-lookup: spell_id → (group_key, group_config). Built once at
# module load — every COOLDOWN_GROUPS edit is reflected automatically.
COOLDOWN_SPELL_TO_GROUP: dict[str, tuple[str, dict]] = {
    spell_id: (group_key, group)
    for group_key, group in COOLDOWN_GROUPS.items()
    for spell_id in group["spell_ids"]
}
MAX_PRIMARY_PROFESSIONS = 2
SECONDARY_CRAFTING_PROFESSIONS = {"cooking"}
EXCLUDED_CRAFTING_PROFESSIONS = {"first-aid", "fishing"}
EPIC_RECIPE_SPELL_IDS = {
    "spell.22749",  # Enchant Weapon - Spell Power
    "spell.22750",  # Enchant Weapon - Healing Power
    "spell.20034",  # Enchant Weapon - Crusader
    "spell.20036",  # Enchant 2H Weapon - Major Intellect
    "spell.20035",  # Enchant 2H Weapon - Major Spirit
    "spell.16994",  # Arcanite Reaper
    "spell.16990",  # Arcanite Champion
    "spell.19830",  # Arcanite Dragonling
    "spell.24121",  # Primal Batskin Jerkin
    "spell.24122",  # Primal Batskin Gloves
    "spell.24123",  # Primal Batskin Bracers
}

CLASS_NAMES_DE = {
    1: "Krieger",
    2: "Paladin",
    3: "Jäger",
    4: "Schurke",
    5: "Priester",
    7: "Schamane",
    8: "Magier",
    9: "Hexenmeister",
    11: "Druide",
}
CLASS_EMOJI_NAMES = {
    1: "wow_warrior",
    2: "wow_paladin",
    3: "wow_hunter",
    4: "wow_rogue",
    5: "wow_priest",
    7: "wow_shaman",
    8: "wow_mage",
    9: "wow_warlock",
    11: "wow_druid",
}
RACE_NAMES_DE = {
    1: "Mensch",
    2: "Orc",
    3: "Zwerg",
    4: "Nachtelf",
    5: "Untoter",
    6: "Tauren",
    7: "Gnom",
    8: "Troll",
}
DIGEST_OPENERS = [
    "🪷 **Black Lotus Tagesbericht**",
    "📜 **Was gestern bei Black Lotus passiert ist**",
    "🌅 **Guten Morgen, Black Lotus**",
    "🪷 **Neues aus der Gilde**",
    "⚔️ **Unser Hardcore-Tag — kurz zusammengefasst**",
]
DIGEST_POSITIVE_CLOSERS = [
    "Glückwunsch an alle, die gestern Fortschritt gemacht haben. Weiter so — sichere Wege! 🪷",
    "Stark gespielt. Mögen die nächsten Pulls genauso sauber laufen.",
    "Black Lotus gratuliert. Heute geht es weiter.",
]
DIGEST_MIXED_CLOSERS = [
    "Glückwunsch an die Aufsteiger — und Respekt für alle gefallenen Chars. 🕯️",
    "Hardcore bleibt gnadenlos. Passt heute gut aufeinander auf.",
    "Fortschritt und Verluste liegen nah beieinander. Bleibt wachsam da draußen.",
]
DIGEST_DEATH_CLOSERS = [
    "Ruhe in Frieden. Der nächste Char trägt die Geschichte weiter. 🕯️",
    "Hardcore vergisst nichts. Passt heute gut aufeinander auf.",
    "Ein stiller Gruß an alle gefallenen Chars.",
]


@dataclass
class Milestone:
    member: RosterMember
    level: int


@dataclass
class DeathEvent:
    member: RosterMember
    confirmed: bool = True
    average_item_level: float | None = None


@dataclass
class OfficerNote:
    member: RosterMember
    message: str


@dataclass
class ActivityDiff:
    new_members: list[RosterMember]
    milestones: list[Milestone]
    deaths: list[DeathEvent]
    officer_notes: list[OfficerNote]
    recipe_events: list[RecipeLearningEvent] | None = None
    gear_events: list[GearMilestoneEvent] | None = None
    skill_events: list[ProfessionSkillEvent] | None = None
    cooldowns_ready: list[Cooldown] | None = None

    @property
    def public_count(self) -> int:
        return (
            len(self.new_members)
            + len(self.milestones)
            + len(self.deaths)
            + len(self.recipe_events or [])
            + len(self.gear_events or [])
            + len(self.skill_events or [])
            + len(self.cooldowns_ready or [])
        )


@dataclass
class ScanResult:
    member_count: int
    milestones: list[Milestone]
    new_members: list[RosterMember] | None = None
    deaths: list[DeathEvent] | None = None
    officer_notes: list[OfficerNote] | None = None
    recipe_events: list[RecipeLearningEvent] | None = None
    gear_events: list[GearMilestoneEvent] | None = None
    skill_events: list[ProfessionSkillEvent] | None = None
    cooldowns_ready: list[Cooldown] | None = None
    posted: int = 0


@dataclass
class ClaimResult:
    claim: CharacterClaim | None
    member: RosterMember | None
    created: bool = False
    reason: str = ""
    review_posted: bool = False


@dataclass
class CraftingProfileResult:
    profession: CharacterProfession | None
    claim: CharacterClaim | None = None
    reason: str = ""


@dataclass
class CraftingSearchResult:
    status: str
    item: dict | None = None
    candidates: list[dict] | None = None
    recipe: dict | None = None
    crafters: list[CharacterProfession] | None = None
    required_skill: int = 0
    profession_id: str | None = None
    manual_recipe: bool = False


@dataclass
class RecipeSelectionResult:
    status: str
    claim: CharacterClaim | None = None
    profiles: list[CharacterProfession] | None = None
    profile: CharacterProfession | None = None
    recipes: list[dict] | None = None


@dataclass
class PanelPublishResult:
    channel_id: int
    message_id: int
    created: bool


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
        if hasattr(self.bot, "add_view"):
            self.bot.add_view(ClaimReviewView(self))
            self.bot.add_view(WoWPanelLayoutView(self))

    async def _poll_loop(self) -> None:
        await self.bot.wait_until_ready()
        await self._auto_publish_panel()
        while True:
            try:
                if await self._scheduled_digest_due():
                    await self._run_scheduled_digest()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("[WoWCog] Polling failed: %s", exc, exc_info=True)
            await asyncio.sleep(self._seconds_until_next_digest())

    def _seconds_until_next_digest(self, now: datetime | None = None) -> float:
        now = self._digest_now(now)
        target = now.replace(
            hour=DEFAULT_DIGEST_HOUR, minute=0, second=0, microsecond=0
        )
        if now >= target:
            target += timedelta(days=1)
        return max((target - now).total_seconds(), 1)

    def _digest_now(self, now: datetime | None = None) -> datetime:
        if now is None:
            return datetime.now(DIGEST_TIMEZONE)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc).astimezone(DIGEST_TIMEZONE)
        return now.astimezone(DIGEST_TIMEZONE)

    async def _scheduled_digest_due(self, now: datetime | None = None) -> bool:
        now = self._digest_now(now)
        target = now.replace(
            hour=DEFAULT_DIGEST_HOUR, minute=0, second=0, microsecond=0
        )
        if now < target:
            return False
        last_scan_at = await self.data.last_scan_at()
        if not last_scan_at:
            return True
        try:
            last_scan = datetime.fromisoformat(last_scan_at)
        except ValueError:
            return True
        last_scan = self._digest_now(last_scan)
        return last_scan < target

    async def _run_scheduled_digest(self) -> None:
        channel_id = await self.data.get_setting("announcement_channel_id")
        if channel_id:
            await self.scan(post=True, persist=True)

    async def _auto_publish_panel(self) -> None:
        channel = self.bot.get_channel(DEFAULT_PANEL_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "[WoWCog] Panel-Channel %s nicht gefunden.", DEFAULT_PANEL_CHANNEL_ID
            )
            return
        try:
            result = await self.publish_panel(channel)
            action = "erstellt" if result.created else "aktualisiert"
            logger.info(
                "[WoWCog] WoW-Panel beim Start %s (Message %s).",
                action,
                result.message_id,
            )
        except Exception as exc:
            logger.error("[WoWCog] Auto-Publish fehlgeschlagen: %s", exc, exc_info=True)

    async def set_announcement_channel(self, channel_id: int) -> None:
        await self.data.set_setting("announcement_channel_id", str(channel_id))

    async def get_announcement_channel_id(self) -> int | None:
        value = await self.data.get_setting("announcement_channel_id")
        return int(value) if value else None

    async def get_claim_review_channel_id(self) -> int:
        value = await self.data.get_setting("claim_review_channel_id")
        return int(value) if value else DEFAULT_CLAIM_REVIEW_CHANNEL_ID

    async def publish_panel(self, channel: discord.TextChannel) -> PanelPublishResult:
        """Send or update the Components-V2 hub message.

        Discord requires V2 messages to have no ``content`` — all visible
        text lives inside the ``LayoutView``'s ``TextDisplay`` items.
        Editing an existing classic-V1 panel into a V2 LayoutView works
        in discord.py 2.6+; if the old message can't be edited (deleted,
        wrong permissions, etc.) we fall back to a fresh send.
        """
        view = WoWPanelLayoutView(self)
        message_id_value = await self.data.get_setting("panel_message_id")
        if message_id_value:
            try:
                message = await channel.fetch_message(int(message_id_value))
                await message.edit(content=None, view=view)
                await self.data.set_setting("panel_channel_id", str(channel.id))
                return PanelPublishResult(channel.id, message.id, created=False)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.info("[WoWCog] Existing WoW panel message not editable.")
            except AttributeError:
                logger.info("[WoWCog] Channel does not support fetching panel message.")

        message = await channel.send(view=view)
        await self.data.set_setting("panel_channel_id", str(channel.id))
        await self.data.set_setting("panel_message_id", str(message.id))
        return PanelPublishResult(channel.id, message.id, created=True)

    def format_panel_content(self) -> str:
        # Legacy helper retained for any callers/tests; the V2 hub builds
        # its own TextDisplays inside WoWPanelLayoutView. Kept here so
        # existing imports don't break.
        return "\n".join(
            [
                "**🪷 Black Lotus WoW-Hub**",
                "",
                (
                    "Hier verbindest du deine Charaktere, pflegst Berufe "
                    "und findest Crafter in der Gilde."
                ),
                "",
                "**Char claimen** — verbinde deinen Black-Lotus-Char mit deinem Discord-Account.",
                "**Berufe pflegen** — trage Beruf, Skill und Spezialisierung ein.",
                "**Rezepte pflegen** — halte deine gelernten Spezialrezepte aktuell.",
                "**Crafter suchen** — finde, wer in der Gilde ein bestimmtes Item herstellen kann.",
            ]
        )

    async def fetch_roster(self, session=None) -> list[RosterMember]:
        raw_members = await fetch_guild_roster(
            self.realm_slug,
            self.guild_slug,
            namespace=self.namespace,
            locale=self.locale,
            session=session,
        )
        members = [parse_roster_member(raw) for raw in raw_members]
        return [member for member in members if member is not None]

    async def scan(self, *, post: bool = True, persist: bool = True) -> ScanResult:
        """Fetch the roster, detect activity, optionally post and persist it."""
        async with self._scan_lock:
            previous = await self.data.get_snapshot()
            async with wow_api_session() as session:
                current = await self.fetch_roster(session=session)
                if self._roster_response_unsafe(previous, current):
                    logger.warning(
                        "[WoWCog] Roster-Response unplausibel (%d → %d). Scan ohne Persistenz.",
                        len(previous),
                        len(current),
                    )
                    return ScanResult(
                        member_count=len(previous),
                        milestones=[],
                        new_members=[],
                        deaths=[],
                        officer_notes=[],
                        recipe_events=[],
                        gear_events=[],
                        skill_events=[],
                        cooldowns_ready=[],
                        posted=0,
                    )
                await self._refresh_member_profiles(current, session=session)
                activity = await self._detect_activity(
                    previous, current, session=session
                )
            posted = 0

            if post and activity.public_count:
                posted = await self._post_activity_digest(activity)
                if posted:
                    await self._record_public_events(activity)
                else:
                    persist = False

            if post and activity.officer_notes:
                await self._post_officer_notes(activity.officer_notes)

            if persist:
                await self.data.replace_snapshot(current)
                await self.data.mark_scanned()

            return ScanResult(
                member_count=len(current),
                milestones=activity.milestones,
                new_members=activity.new_members,
                deaths=activity.deaths,
                officer_notes=activity.officer_notes,
                recipe_events=activity.recipe_events or [],
                gear_events=activity.gear_events or [],
                skill_events=activity.skill_events or [],
                cooldowns_ready=activity.cooldowns_ready or [],
                posted=posted,
            )

    @staticmethod
    def _roster_response_unsafe(
        previous: dict[str, RosterMember], current: list[RosterMember]
    ) -> bool:
        """Reject obviously broken roster responses to protect the snapshot.

        Blizzard occasionally returns a partial or empty member list during
        outages — overwriting the snapshot with that would mark everyone as
        new on the next scan. The guard only kicks in for guilds of a real
        size (>5 previous members), so small test rosters and edge cases
        (last member leaves a 2-person guild) aren't blocked.
        """
        if len(previous) <= 5:
            return False
        if not current:
            return True
        return len(current) < len(previous) // 2

    async def _detect_activity(
        self,
        previous: dict[str, RosterMember],
        current: list[RosterMember],
        *,
        session=None,
    ) -> ActivityDiff:
        current_by_key = {member.character_key: member for member in current}
        new_members = [
            member for member in current if member.character_key not in previous
        ]
        milestones = await self._detect_milestones(previous, current)
        deaths = await self._detect_roster_deaths(previous, current)
        missing_deaths, officer_notes = await self._inspect_missing_members(
            previous, current_by_key, session=session
        )
        deaths.extend(missing_deaths)
        recipe_events = await self.data.pending_recipe_learning_events()
        gear_events = await self.data.pending_gear_milestone_events()
        skill_events = await self.data.pending_skill_milestone_events()
        cooldowns_ready = await self._cooldowns_ready_in_next_24h()
        return ActivityDiff(
            new_members=new_members,
            milestones=milestones,
            deaths=deaths,
            officer_notes=officer_notes,
            recipe_events=recipe_events,
            gear_events=gear_events,
            skill_events=skill_events,
            cooldowns_ready=cooldowns_ready,
        )

    async def _cooldowns_ready_in_next_24h(self) -> list[Cooldown]:
        """Cooldowns that fire from now until 24h ahead.

        Used for the daily digest. Window starts at "now" so freshly-ready
        CDs still appear on the day they unlock; ends 24h later so we don't
        spam multi-day previews.
        """
        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=24)
        return await self.data.cooldowns_ready_in_window(
            now.isoformat(), end.isoformat()
        )

    async def _refresh_member_profiles(
        self, members: list[RosterMember], *, session=None
    ) -> None:
        """Patch ghost state and gear from the per-character profile endpoint.

        The guild roster endpoint omits ``is_ghost`` and gear info, so we hit
        the profile endpoint per member with bounded concurrency. One call
        gives us both the death signal and ``equipped_item_level`` — no
        equipment endpoint or local item-id lookup needed. Per-member failures
        are logged but never block the scan; affected members keep their
        roster defaults (alive, no fresh gear snapshot).
        """
        if not members:
            return
        semaphore = asyncio.Semaphore(GHOST_REFRESH_CONCURRENCY)

        async def refresh_one(member: RosterMember) -> None:
            async with semaphore:
                try:
                    profile = await fetch_character_profile(
                        member.realm_slug,
                        member.name,
                        namespace=self.namespace,
                        locale=self.locale,
                        session=session,
                    )
                except WoWAPIError as exc:
                    logger.info(
                        "[WoWCog] Profile für %s nicht abrufbar: %s",
                        member.name,
                        exc,
                    )
                    return
                except Exception as exc:
                    logger.info(
                        "[WoWCog] Profile-Abfrage für %s fehlgeschlagen: %s",
                        member.name,
                        exc,
                    )
                    return
                if not isinstance(profile, dict):
                    return
                if profile.get("is_ghost"):
                    member.is_ghost = True
                if member.level >= 60:
                    await self._apply_gear_from_profile(member, profile)

        await asyncio.gather(*(refresh_one(member) for member in members))

    async def _apply_gear_from_profile(
        self, member: RosterMember, profile: dict
    ) -> None:
        raw = profile.get("equipped_item_level")
        if not isinstance(raw, (int, float)):
            return
        average_item_level = float(raw)
        previous = await self.data.gear_snapshot(member.character_key)
        await self.data.set_gear_snapshot(member.character_key, average_item_level, 0)
        if previous is None or member.is_ghost:
            return
        for threshold in sorted(ITEM_LEVEL_MILESTONES):
            if (
                previous.average_item_level < threshold <= average_item_level
                and not await self.data.gear_milestone_exists(
                    member.character_key, threshold
                )
            ):
                await self.data.record_gear_milestone(
                    member.character_key,
                    threshold,
                    average_item_level,
                    ITEM_LEVEL_MILESTONE_POINTS.get(threshold, 0),
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
                if (
                    old.level < level <= member.level
                    and not await self.data.milestone_exists(
                        member.character_key, level
                    )
                ):
                    milestones.append(Milestone(member=member, level=level))
        return milestones

    async def _detect_roster_deaths(
        self,
        previous: dict[str, RosterMember],
        current: list[RosterMember],
    ) -> list[DeathEvent]:
        deaths: list[DeathEvent] = []
        for member in current:
            old = previous.get(member.character_key)
            if (
                member.is_ghost
                and (old is None or not old.is_ghost)
                and not await self.data.death_exists(member.character_key)
            ):
                deaths.append(
                    DeathEvent(
                        member,
                        average_item_level=await self._member_average_item_level(
                            member.character_key
                        ),
                    )
                )
        return deaths

    async def _inspect_missing_members(
        self,
        previous: dict[str, RosterMember],
        current_by_key: dict[str, RosterMember],
        *,
        session=None,
    ) -> tuple[list[DeathEvent], list[OfficerNote]]:
        deaths: list[DeathEvent] = []
        notes: list[OfficerNote] = []
        for member in previous.values():
            if member.character_key in current_by_key:
                continue
            if await self.data.death_exists(member.character_key):
                continue
            if await self.data.officer_note_exists(member.character_key):
                # Already announced as "left guild" — don't re-notify even if
                # the snapshot wasn't replaced (e.g. previous digest failed).
                continue
            state = await self._profile_life_state(member, session=session)
            average_item_level = await self._member_average_item_level(
                member.character_key
            )
            if state == "dead":
                deaths.append(
                    DeathEvent(
                        member, confirmed=True, average_item_level=average_item_level
                    )
                )
            elif state == "alive":
                notes.append(
                    OfficerNote(
                        member,
                        f"{member.name} ist nicht mehr Teil von {self.guild_name}.",
                    )
                )
            else:
                deaths.append(
                    DeathEvent(
                        member, confirmed=False, average_item_level=average_item_level
                    )
                )
        return deaths, notes

    async def _member_average_item_level(self, character_key: str) -> float | None:
        snapshot = await self.data.gear_snapshot(character_key)
        return snapshot.average_item_level if snapshot else None

    async def _profile_life_state(self, member: RosterMember, *, session=None) -> str:
        try:
            profile = await fetch_character_profile(
                member.realm_slug,
                member.name,
                namespace=self.namespace,
                locale=self.locale,
                session=session,
            )
        except WoWAPIError as exc:
            logger.info(
                "[WoWCog] Could not inspect missing character %s: %s",
                member.name,
                exc,
            )
            return "unknown"
        except Exception as exc:
            logger.info(
                "[WoWCog] Profile inspection failed for %s: %s",
                member.name,
                exc,
                exc_info=True,
            )
            return "unknown"
        return "dead" if self._profile_is_dead(profile) else "alive"

    def _profile_is_dead(self, profile: dict) -> bool:
        return bool(
            profile.get("is_ghost")
            or profile.get("is_dead")
            or profile.get("dead")
            or profile.get("ghost")
        )

    async def _post_activity_digest(self, activity: ActivityDiff) -> int:
        channel_id = await self.get_announcement_channel_id()
        if channel_id is None:
            logger.warning("[WoWCog] No announcement channel configured.")
            return 0
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning("[WoWCog] Announcement channel %s not found.", channel_id)
            return 0

        sections = await self._digest_sections(activity)
        chunks = _pack_digest_sections_into_chunks(sections)
        posted = 0
        for chunk in chunks:
            try:
                await channel.send(chunk)
            except discord.Forbidden:
                logger.warning(
                    "[WoWCog] Missing access to announcement channel %s.",
                    channel_id,
                )
                return posted
            except discord.HTTPException as exc:
                logger.warning(
                    "[WoWCog] Could not post activity digest chunk to channel %s: %s",
                    channel_id,
                    exc,
                    exc_info=True,
                )
                return posted
            posted += 1
        return posted

    async def _post_milestones(self, milestones: list[Milestone]) -> int:
        activity = ActivityDiff(
            new_members=[], milestones=milestones, deaths=[], officer_notes=[]
        )
        return await self._post_activity_digest(activity)

    async def _post_officer_notes(self, notes: list[OfficerNote]) -> int:
        channel_id = await self.get_claim_review_channel_id()
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning("[WoWCog] Claim review channel %s not found.", channel_id)
            return 0
        posted = 0
        for note in notes:
            try:
                await channel.send(f"⚠️ {note.message}")
            except (discord.Forbidden, discord.HTTPException) as exc:
                logger.warning(
                    "[WoWCog] Could not post officer note to channel %s: %s",
                    channel_id,
                    exc,
                )
                break
            # Persist immediately so a later scan failure can't cause a
            # duplicate "X ist nicht mehr Teil von …" message.
            await self.data.record_officer_note(note.member.character_key)
            posted += 1
        return posted

    async def _record_public_events(self, activity: ActivityDiff) -> None:
        for milestone in activity.milestones:
            await self.data.record_milestone(
                milestone.member.character_key, milestone.level
            )
            await self._award_claimed_milestone_points(milestone)
        for death in activity.deaths:
            await self.data.record_death(death.member.character_key)
            # Auto-release the dead char's claim so the owner can claim a
            # re-rolled character with the same name without first having
            # to manually release. The owner already learns about the
            # death via the digest's @mention.
            claim = await self.data.get_claim(death.member.character_key)
            if claim:
                await self.data.release_claim(
                    death.member.character_key, claim.discord_user_id
                )
        for event in activity.recipe_events or []:
            await self.data.mark_recipe_learning_announced(
                event.character_key, event.spell_id
            )
            await self._award_recipe_learning_points(event)
        for event in activity.gear_events or []:
            await self.data.mark_gear_milestone_announced(
                event.character_key, event.threshold
            )
            await self._award_gear_milestone_points(event)
        for event in activity.skill_events or []:
            await self.data.mark_skill_milestone_announced(
                event.character_key, event.profession_id, event.threshold
            )
            await self._award_skill_milestone_points(event)
        # Cooldowns are read-only in the digest — no DB write needed here.
        await self._retry_unawarded_pending_events()

    async def _retry_unawarded_pending_events(self) -> None:
        """Re-fund events that were announced but never landed Champion points.

        A row stuck in "announced, not awarded" means a previous
        ``champion.update_user_score()`` call failed (e.g. SQLite-lock). The
        row is invisible to the digest's ``pending_*_events`` filter because
        ``announced_at`` is already set, so without this loop the points
        would be permanently lost. Each ``_award_*_points`` call is
        idempotent — successful retries mark ``awarded_at`` and exit the
        retry pool; persistent failures stay queued for the next scan.
        """
        for event in await self.data.pending_award_retries_recipe_learning():
            await self._award_recipe_learning_points(event)
        for event in await self.data.pending_award_retries_gear_milestone():
            await self._award_gear_milestone_points(event)
        for event in await self.data.pending_award_retries_skill_milestone():
            await self._award_skill_milestone_points(event)

    async def _award_claimed_milestone_points(self, milestone: Milestone) -> None:
        claim = await self.data.get_claim(milestone.member.character_key)
        if not claim:
            return
        points = CLAIMED_MILESTONE_POINTS.get(milestone.level, 0)
        if points <= 0:
            return
        get_cog = getattr(self.bot, "get_cog", None)
        champion = get_cog("ChampionCog") if get_cog else None
        if champion is None or not hasattr(champion, "update_user_score"):
            logger.info("[WoWCog] ChampionCog not available for milestone bonus.")
            return
        reason = f"WoW-Meilenstein: {milestone.member.name} Level {milestone.level}"
        try:
            await champion.update_user_score(claim.discord_user_id, points, reason)
        except Exception as exc:  # pragma: no cover - defensive integration logging
            logger.warning(
                "[WoWCog] Could not award claimed milestone points: %s",
                exc,
                exc_info=True,
            )

    async def _award_recipe_learning_points(self, event: RecipeLearningEvent) -> None:
        if event.points <= 0:
            return
        get_cog = getattr(self.bot, "get_cog", None)
        champion = get_cog("ChampionCog") if get_cog else None
        if champion is None or not hasattr(champion, "update_user_score"):
            logger.info("[WoWCog] ChampionCog not available for recipe bonus.")
            return
        # CAS-reserve the slot first (`awarded_at IS NULL` guard). If
        # somebody already awarded this event (e.g. a previous scan or a
        # concurrent retry pass), exit silently — no double-vote possible.
        if not await self.data.mark_recipe_learning_awarded(
            event.character_key, event.spell_id
        ):
            return
        recipe = self._recipe_by_spell_id(event.spell_id)
        recipe_name = self._recipe_name(recipe) if recipe else event.spell_id
        reason = f"WoW-Rezept: {event.character_name} lernt {recipe_name}"
        try:
            await champion.update_user_score(
                event.discord_user_id, event.points, reason
            )
        except Exception as exc:  # pragma: no cover - defensive integration logging
            logger.warning(
                "[WoWCog] Could not award recipe learning points: %s",
                exc,
                exc_info=True,
            )
            # Roll back the CAS so the next scan's retry loop can pick
            # it up again. Without this the points would be lost forever.
            await self.data.unmark_recipe_learning_awarded(
                event.character_key, event.spell_id
            )

    async def _award_gear_milestone_points(self, event: GearMilestoneEvent) -> None:
        if event.points <= 0 or event.discord_user_id is None:
            return
        get_cog = getattr(self.bot, "get_cog", None)
        champion = get_cog("ChampionCog") if get_cog else None
        if champion is None or not hasattr(champion, "update_user_score"):
            logger.info("[WoWCog] ChampionCog not available for gear bonus.")
            return
        if not await self.data.mark_gear_milestone_awarded(
            event.character_key, event.threshold
        ):
            return
        reason = (
            f"WoW-iLvl-Meilenstein: {event.character_name} " f"Ø iLvl {event.threshold}"
        )
        try:
            await champion.update_user_score(
                event.discord_user_id, event.points, reason
            )
        except Exception as exc:  # pragma: no cover - defensive integration logging
            logger.warning(
                "[WoWCog] Could not award gear milestone points: %s",
                exc,
                exc_info=True,
            )
            await self.data.unmark_gear_milestone_awarded(
                event.character_key, event.threshold
            )

    async def cooldown_eligible_options(
        self, discord_user_id: int
    ) -> list[tuple[CharacterClaim, str, str, str]]:
        """Return (claim, spell_id, spell_name, group_label) per eligible (char, CD-spell).

        A spell is eligible if the user's claimed character has explicitly
        learned it AND it's in the cooldown spell-to-group lookup.
        """
        eligible: list[tuple[CharacterClaim, str, str, str]] = []
        for claim in await self.data.claims_for_user(discord_user_id):
            known = await self.data.known_recipe_spell_ids(claim.character_key)
            for spell_id in sorted(known):
                if spell_id not in COOLDOWN_SPELL_TO_GROUP:
                    continue
                _, group = COOLDOWN_SPELL_TO_GROUP[spell_id]
                recipe = self._recipe_by_spell_id(spell_id)
                spell_name = self._recipe_name(recipe) if recipe else spell_id
                eligible.append((claim, spell_id, spell_name, group["label"]))
        return eligible

    async def log_cooldown(
        self,
        discord_user_id: int,
        character_key: str,
        spell_id: str,
    ) -> tuple[str, Cooldown | None]:
        """Persist a cooldown for the given user's character + spell.

        Returns ``(status, cooldown)``. Status codes:
        * ``"ok"`` — saved.
        * ``"not_owner"`` — claim belongs to someone else.
        * ``"unknown_spell"`` — spell isn't a tracked CD recipe.
        * ``"recipe_missing"`` — char hasn't learned that recipe.
        """
        if spell_id not in COOLDOWN_SPELL_TO_GROUP:
            return "unknown_spell", None
        claim = await self.data.get_claim(character_key)
        if not claim or claim.discord_user_id != discord_user_id:
            return "not_owner", None
        known = await self.data.known_recipe_spell_ids(character_key)
        if spell_id not in known:
            return "recipe_missing", None
        group_key, group = COOLDOWN_SPELL_TO_GROUP[spell_id]
        recipe = self._recipe_by_spell_id(spell_id)
        spell_name = self._recipe_name(recipe) if recipe else spell_id
        now = datetime.now(timezone.utc)
        ready = now + timedelta(hours=int(group["hours"]))
        await self.data.set_cooldown(
            character_key,
            group_key,
            spell_id,
            spell_name,
            now.isoformat(),
            ready.isoformat(),
        )
        return "ok", Cooldown(
            character_key=character_key,
            character_name=claim.character_name,
            realm_slug=claim.realm_slug,
            discord_user_id=claim.discord_user_id,
            cooldown_group=group_key,
            last_spell_id=spell_id,
            last_spell_name=spell_name,
            used_at=now.isoformat(),
            ready_at=ready.isoformat(),
        )

    async def _award_skill_milestone_points(self, event: ProfessionSkillEvent) -> None:
        if event.points <= 0 or event.discord_user_id is None:
            return
        get_cog = getattr(self.bot, "get_cog", None)
        champion = get_cog("ChampionCog") if get_cog else None
        if champion is None or not hasattr(champion, "update_user_score"):
            logger.info("[WoWCog] ChampionCog not available for skill bonus.")
            return
        if not await self.data.mark_skill_milestone_awarded(
            event.character_key, event.profession_id, event.threshold
        ):
            return
        profession_name = self._profession_name(event.profession_id)
        reason = (
            f"WoW-Berufsskill: {event.character_name} ({profession_name}) "
            f"Skill {event.threshold}"
        )
        try:
            await champion.update_user_score(
                event.discord_user_id, event.points, reason
            )
        except Exception as exc:  # pragma: no cover - defensive integration logging
            logger.warning(
                "[WoWCog] Could not award skill milestone points: %s",
                exc,
                exc_info=True,
            )
            await self.data.unmark_skill_milestone_awarded(
                event.character_key, event.profession_id, event.threshold
            )

    def format_milestone(self, milestone: Milestone) -> str:
        return self._format_milestone_line(milestone, None)

    async def _format_activity_digest_legacy(self, activity: ActivityDiff) -> str:
        lines = [random.choice(DIGEST_OPENERS), ""]
        if activity.new_members:
            lines.append("**Neue Chars**")
            for member in activity.new_members:
                lines.append(f"🆕 {self._format_new_member_line(member)}")
            lines.append("")
        if activity.milestones:
            lines.append("**Level-Meilensteine**")
            for milestone in activity.milestones:
                claim = await self.data.get_claim(milestone.member.character_key)
                lines.append(f"🏅 {self._format_milestone_line(milestone, claim)}")
            lines.append("")
        if activity.deaths:
            lines.append("**Gefallene Chars**")
            for death in activity.deaths:
                lines.append(f"🕯️ {self._format_death_line(death)}")
            lines.append("")
        lines.append(self._digest_closer(activity))
        return "\n".join(lines)

    def _digest_closer(self, activity: ActivityDiff) -> str:
        has_good_news = bool(
            activity.new_members
            or activity.milestones
            or (activity.recipe_events or [])
            or (activity.gear_events or [])
            or (activity.skill_events or [])
            or (activity.cooldowns_ready or [])
        )
        has_deaths = bool(activity.deaths)
        if has_deaths and has_good_news:
            return random.choice(DIGEST_MIXED_CLOSERS)
        if has_deaths:
            return random.choice(DIGEST_DEATH_CLOSERS)
        return random.choice(DIGEST_POSITIVE_CLOSERS)

    def _format_new_member_line(self, member: RosterMember) -> str:
        return (
            "Willkommen bei Black Lotus: "
            f"**{self._display_character(member)}** "
            f"(Level **{member.level}**)."
        )

    def _format_milestone_line(
        self, milestone: Milestone, claim: CharacterClaim | None
    ) -> str:
        character = self._display_character(milestone.member)
        if claim:
            return (
                f"<@{claim.discord_user_id}> hat mit **{character}** "
                f"Level **{milestone.level}** erreicht "
                f"(+{CLAIMED_MILESTONE_POINTS.get(milestone.level, 0)} Champion-Punkte)."
            )
        return f"**{character}** ist auf Level **{milestone.level}** aufgestiegen."

    def _format_death_line(self, death: DeathEvent) -> str:
        character = self._display_character(death.member)
        level = death.member.level
        gear = self._format_death_gear_suffix(death)
        if not death.confirmed:
            return (
                f"**{character}** ist auf Level **{level}**{gear} nicht mehr im Roster auffindbar. "
                "Die Hardcore-Reise endet hier — wahrscheinlich."
            )
        return (
            f"**{character}** ist auf Level **{level}**{gear} gefallen. "
            "Ruhe in Frieden. 🕯️"
        )

    async def _digest_sections(
        self, activity: ActivityDiff
    ) -> list[tuple[str | None, list[str]]]:
        """Return the digest as ordered (header, body_lines) sections.

        ``header`` is ``None`` for headerless blocks (opener, closer).
        Blank-line separators between sections are NOT included — the
        chunker inserts them only where sections actually end up adjacent.
        """
        sections: list[tuple[str | None, list[str]]] = [
            (None, [random.choice(DIGEST_OPENERS)])
        ]

        if activity.new_members:
            body: list[str] = []
            for member in sorted(
                activity.new_members,
                key=lambda item: (-item.level, item.name.casefold()),
            ):
                line = self._format_roster_line(member)
                if member.level >= 60:
                    snapshot = await self.data.gear_snapshot(member.character_key)
                    if snapshot:
                        line = (
                            f"{line}, Ø iLvl "
                            f"**{self._format_item_level(snapshot.average_item_level)}**"
                        )
                claim = await self.data.get_claim(member.character_key)
                if claim:
                    line = f"{line} - <@{claim.discord_user_id}>"
                body.append(f"- {line}")
            sections.append(("**Herzlich willkommen in der Gilde** 👋", body))

        if activity.milestones:
            body = []
            for milestone in sorted(
                activity.milestones,
                key=lambda item: (-item.level, item.member.name.casefold()),
            ):
                claim = await self.data.get_claim(milestone.member.character_key)
                line = self._format_roster_line(milestone.member, level=milestone.level)
                if claim:
                    points = CLAIMED_MILESTONE_POINTS.get(milestone.level, 0)
                    line = (
                        f"{line} - <@{claim.discord_user_id}> "
                        f"(+{points} Champion-Punkte)"
                    )
                body.append(f"- {line}")
            sections.append(("**Glückwunsch zu diesen Meilensteinen** 🏆", body))

        if activity.recipe_events:
            body = []
            for event in sorted(
                activity.recipe_events,
                key=lambda item: (
                    -item.points,
                    self._profession_name(item.profession_id).casefold(),
                    item.character_name.casefold(),
                ),
            ):
                recipe = self._recipe_by_spell_id(event.spell_id)
                recipe_name = self._recipe_name(recipe) if recipe else event.spell_id
                source = self._recipe_source_label(recipe)
                required_skill = int(recipe.get("required_skill") or 0) if recipe else 0
                skill_label = f", ab Skill {required_skill}" if required_skill else ""
                tail_parts = []
                if event.discord_user_id is not None:
                    tail_parts.append(f"<@{event.discord_user_id}>")
                    if event.points > 0:
                        tail_parts.append(f"(+{event.points} Champion-Punkte)")
                tail = f" - {' '.join(tail_parts)}" if tail_parts else ""
                body.append(
                    f"- **{event.character_name}** "
                    f"({self._profession_name(event.profession_id)}{skill_label}): "
                    f"**{recipe_name}** *({event.rarity}, {source})*{tail}"
                )
            sections.append(("**Neue seltene Rezepte in der Gilde** 📖", body))

        if activity.gear_events:
            body = []
            for event in sorted(
                activity.gear_events,
                key=lambda item: (-item.threshold, item.character_name.casefold()),
            ):
                tail_parts: list[str] = []
                if event.discord_user_id is not None:
                    tail_parts.append(f"<@{event.discord_user_id}>")
                    if event.points > 0:
                        tail_parts.append(f"(+{event.points} Champion-Punkte)")
                tail = f" - {' '.join(tail_parts)}" if tail_parts else ""
                body.append(
                    f"- **{event.character_name}** hat ein durchschnittliches Itemlevel "
                    f"von **{self._format_item_level(event.average_item_level)}** "
                    f"erreicht{tail}"
                )
            sections.append(("**Ausrüstungs-Meilensteine** 🛡️", body))

        if activity.skill_events:
            body = []
            for event in sorted(
                activity.skill_events,
                key=lambda item: (-item.threshold, item.character_name.casefold()),
            ):
                tail_parts: list[str] = []
                if event.discord_user_id is not None:
                    tail_parts.append(f"<@{event.discord_user_id}>")
                    if event.points > 0:
                        tail_parts.append(f"(+{event.points} Champion-Punkte)")
                tail = f" - {' '.join(tail_parts)}" if tail_parts else ""
                body.append(
                    f"- **{event.character_name}** "
                    f"({self._profession_name(event.profession_id)}): "
                    f"hat Skill **{event.threshold}** erreicht{tail}"
                )
            sections.append(("**Berufsskill-Meilensteine** 🧪", body))

        if activity.cooldowns_ready:
            body = []
            now = datetime.now(timezone.utc)
            for cd in sorted(activity.cooldowns_ready, key=lambda c: c.ready_at):
                ready_label = self._format_cooldown_ready_label(cd.ready_at, now)
                group = COOLDOWN_GROUPS.get(cd.cooldown_group, {})
                group_label = group.get("label", cd.cooldown_group)
                mention = (
                    f" - <@{cd.discord_user_id}>"
                    if cd.discord_user_id is not None
                    else ""
                )
                body.append(
                    f"- **{cd.character_name}** ({group_label} — "
                    f"{cd.last_spell_name}): {ready_label}{mention}"
                )
            sections.append(("**Cooldowns bereit in den nächsten 24h** ⏳", body))

        if activity.deaths:
            body = []
            for death in sorted(
                activity.deaths,
                key=lambda item: (-item.member.level, item.member.name.casefold()),
            ):
                suffix = (
                    ""
                    if death.confirmed
                    else " — *nicht mehr im Roster, wahrscheinlich auf Reise gegangen*"
                )
                gear = self._format_death_gear_suffix(death)
                claim = await self.data.get_claim(death.member.character_key)
                mention = f" - <@{claim.discord_user_id}>" if claim else ""
                body.append(
                    f"- {self._format_roster_line(death.member)}{gear}{mention}{suffix}"
                )
            sections.append(("**Heute nehmen wir Abschied** 🕯️", body))

        sections.append((None, [self._digest_closer(activity)]))
        return sections

    async def format_activity_digest(self, activity: ActivityDiff) -> str:
        """Render the digest as a single joined string.

        The wire path uses ``_digest_sections`` directly via the chunker;
        this method exists for callers (tests, manual inspection) that
        want the full text in one piece.
        """
        sections = await self._digest_sections(activity)
        parts: list[str] = []
        for idx, (header, body) in enumerate(sections):
            if idx > 0:
                parts.append("")
            if header is not None:
                parts.append(header)
            parts.extend(body)
        return "\n".join(parts)

    def _format_roster_line(
        self, member: RosterMember, level: int | None = None
    ) -> str:
        parts = [f"**{member.name}**", f"Level **{level or member.level}**"]
        race = RACE_NAMES_DE.get(member.race_id)
        class_name = CLASS_NAMES_DE.get(member.class_id)
        if race:
            parts.append(race)
        if class_name:
            parts.append(class_name)
        return ", ".join(parts)

    def _format_item_level(self, average_item_level: float) -> str:
        return f"{average_item_level:.1f}"

    def _format_cooldown_ready_label(
        self, ready_at_iso: str, now: datetime | None = None
    ) -> str:
        """Render ``ready_at`` as 'ab heute HH:MM' / 'ab morgen HH:MM' / 'jetzt'.

        Times are shown in the digest timezone so users see local clock time.
        """
        now = now or datetime.now(timezone.utc)
        try:
            ready = datetime.fromisoformat(ready_at_iso)
        except ValueError:
            return "Zeitpunkt unklar"
        if ready.tzinfo is None:
            ready = ready.replace(tzinfo=timezone.utc)
        ready_local = ready.astimezone(DIGEST_TIMEZONE)
        now_local = now.astimezone(DIGEST_TIMEZONE)
        if ready <= now:
            return "ready **jetzt**"
        today = now_local.date()
        target = ready_local.date()
        when = (
            "heute"
            if target == today
            else (
                "morgen"
                if target == today + timedelta(days=1)
                else target.strftime("%d.%m.")
            )
        )
        return f"ab {when} **{ready_local.strftime('%H:%M')}**"

    def _format_death_gear_suffix(self, death: DeathEvent) -> str:
        if death.member.level < 60 or death.average_item_level is None:
            return ""
        return f", Ø iLvl **{self._format_item_level(death.average_item_level)}**"

    def _display_character(self, member: RosterMember) -> str:
        parts = []
        race = RACE_NAMES_DE.get(member.race_id)
        class_name = CLASS_NAMES_DE.get(member.class_id)
        if race:
            parts.append(race)
        if class_name:
            parts.append(class_name)
        parts.append(member.name)
        return " ".join(parts)

    async def claim_character(
        self, discord_user_id: int, char_name: str
    ) -> ClaimResult:
        member = await self.data.find_roster_member_by_name(char_name)
        if not member:
            return ClaimResult(
                claim=None,
                member=None,
                reason="not_found",
            )

        claim, created = await self.data.create_claim(member, discord_user_id)
        if not created:
            reason = (
                "already_own" if claim.discord_user_id == discord_user_id else "taken"
            )
            return ClaimResult(
                claim=claim,
                member=member,
                created=False,
                reason=reason,
            )

        review_posted = await self._post_claim_review(claim)
        return ClaimResult(
            claim=claim,
            member=member,
            created=True,
            reason="created",
            review_posted=review_posted,
        )

    # ---- "Meine Chars" detail view action handlers ----

    async def _my_chars_profession(
        self, interaction: discord.Interaction, view: "PanelMyCharsView"
    ) -> None:
        claim = view.selected_claim
        if claim is None:
            await view.refresh(interaction)
            return
        profiles = await self.data.professions_for_character(claim.character_key)
        sub_view = PanelProfessionSelectView(self, interaction.user.id, claim, profiles)
        await interaction.response.edit_message(
            content=(
                f"Berufe für **{claim.character_name}**:\n"
                f"{self.format_profession_slots(profiles)}\n\n"
                "Welchen Beruf möchtest du pflegen?"
            ),
            embed=None,
            view=sub_view,
        )

    async def _my_chars_recipes(
        self, interaction: discord.Interaction, view: "PanelMyCharsView"
    ) -> None:
        claim = view.selected_claim
        if claim is None:
            await view.refresh(interaction)
            return
        profiles = await self.data.professions_for_character(claim.character_key)
        if not profiles:
            await interaction.response.edit_message(
                content=(
                    f"Für **{claim.character_name}** sind noch keine Berufe gepflegt. "
                    "Nutze zuerst **Berufe pflegen**."
                ),
                embed=None,
                view=None,
            )
            return
        sub_view = PanelRecipeProfessionSelectView(
            self, interaction.user.id, claim, profiles
        )
        await interaction.response.edit_message(
            content="Für welchen Beruf möchtest du Spezialrezepte pflegen?",
            embed=None,
            view=sub_view,
        )

    async def _my_chars_release(
        self, interaction: discord.Interaction, view: "PanelMyCharsView"
    ) -> None:
        claim = view.selected_claim
        if claim is None:
            await view.refresh(interaction)
            return
        await self.data.release_claim(claim.character_key, claim.discord_user_id)
        view.selected_claim = None
        await view.refresh(interaction)

    async def _my_chars_claim_new(
        self, interaction: discord.Interaction, view: "PanelMyCharsView"
    ) -> None:
        # Direct text-modal: a 25-char dropdown was useless for larger guilds.
        await interaction.response.send_modal(PanelCharacterSearchModal(self))

    async def build_whois_view(
        self, char_name: str, viewer_id: int
    ) -> "discord.ui.LayoutView | None":
        """Render an ephemeral Components-V2 profile card.

        Returns ``None`` if no matching roster member exists. Uses only
        existing DB helpers — no extra Blizzard API calls.
        """
        member = await self.data.find_roster_member_by_name(char_name)
        if member is None:
            return None
        claim = await self.data.get_claim(member.character_key)
        gear = await self.data.gear_snapshot(member.character_key)
        professions = await self.data.professions_for_character(member.character_key)

        twins: list[CharacterClaim] = []
        if claim is not None:
            all_claims = await self.data.claims_for_user(claim.discord_user_id)
            twins = [c for c in all_claims if c.character_key != claim.character_key]

        viewer_is_owner = claim is not None and claim.discord_user_id == viewer_id
        return _WhoisLayoutView(
            self, member, claim, gear, professions, twins, viewer_id, viewer_is_owner
        )

    async def submit_gbank_request(
        self,
        requester: discord.abc.User,
        requester_char_name: str,
        bank_character_key: str,
        bank_character_name: str,
        request_text: str,
    ) -> None:
        """Deliver a guild-bank request to the bank char's owner.

        Tries a DM to the claiming owner first; on failure (DMs closed)
        or if the bank char is unclaimed, posts to the officer channel so
        nothing is lost. The requester always sees success.
        """
        claim = await self.data.get_claim(bank_character_key)
        body = (
            f"🏦 **Neue Gildenbank-Anfrage** von **{requester_char_name}** "
            f"(von {requester.mention})\n"
            f'„{request_text}"\n'
            f"Die Items liegen auf dem Bank-Char **{bank_character_name}**."
        )

        if claim is not None:
            owner = self.bot.get_user(claim.discord_user_id)
            if owner is None:
                try:
                    owner = await self.bot.fetch_user(claim.discord_user_id)
                except discord.HTTPException:
                    owner = None
            if owner is not None:
                try:
                    await owner.send(body)
                    return
                except (discord.Forbidden, discord.HTTPException) as exc:
                    logger.info(
                        "[WoWCog] gbank DM to %s failed: %s",
                        claim.discord_user_id,
                        exc,
                    )

        reason = (
            "Bank-Char ist nicht geclaimed"
            if claim is None
            else "DM an den Owner fehlgeschlagen"
        )
        await self._post_gbank_to_officer_channel(f"_({reason})_\n{body}")

    async def _post_gbank_to_officer_channel(self, content: str) -> None:
        channel_id = await self.get_claim_review_channel_id()
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning("[WoWCog] gbank officer channel %s not found.", channel_id)
            return
        try:
            await channel.send(content)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning(
                "[WoWCog] Could not post gbank request to channel %s: %s",
                channel_id,
                exc,
            )

    async def _post_claim_review(self, claim: CharacterClaim) -> bool:
        channel_id = await self.get_claim_review_channel_id()
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.warning("[WoWCog] Claim review channel %s not found.", channel_id)
            return False

        try:
            message = await channel.send(
                self.format_claim_review(claim),
                view=ClaimReviewView(self),
            )
        except discord.Forbidden:
            logger.warning(
                "[WoWCog] Missing access to claim review channel %s.", channel_id
            )
            return False
        except discord.HTTPException as exc:
            logger.warning(
                "[WoWCog] Could not post claim review to channel %s: %s",
                channel_id,
                exc,
                exc_info=True,
            )
            return False

        await self.data.set_claim_review_message(claim.character_key, message.id)
        return True

    def format_claim_review(self, claim: CharacterClaim) -> str:
        return (
            f"<@{claim.discord_user_id}> möchte **{claim.character_name}** verbinden "
            f"— bitte bestätigen oder ablehnen."
        )

    def _wow_records(self, table: str) -> list[dict]:
        data = getattr(self.bot, "data", {}).get("wow", {})
        records = data.get(table, [])
        return records if isinstance(records, list) else []

    def _localized_text(self, value: object, language: str = "de") -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return value.get(language) or value.get("de") or value.get("en") or ""
        return ""

    def _profession_name(self, profession_id: str, language: str = "de") -> str:
        profession = self._get_static_record("professions", profession_id)
        return self._localized_text(profession.get("name"), language) or profession_id

    def normalize_recipe_language(self, language: str | None) -> str:
        if language in {"de", "en"}:
            return str(language)
        return "de"

    def _profession_type(self, profession_id: str) -> str:
        profession = self._get_static_record("professions", profession_id)
        return str(profession.get("type") or "primary")

    def _is_primary_profession(self, profession_id: str) -> bool:
        return self._profession_type(profession_id) == "primary"

    def _is_crafting_profession(self, profession: dict) -> bool:
        profession_id = profession.get("id")
        if not profession_id:
            return False
        if profession_id in EXCLUDED_CRAFTING_PROFESSIONS:
            return False
        profession_type = profession.get("type") or "primary"
        return (
            profession_type == "primary"
            or profession_id in SECONDARY_CRAFTING_PROFESSIONS
        )

    def _crafting_professions(self) -> list[dict]:
        return [
            profession
            for profession in self._wow_records("professions")
            if self._is_crafting_profession(profession)
        ]

    def _get_static_record(self, table: str, record_id: str | None) -> dict:
        if not record_id:
            return {}
        for record in self._wow_records(table):
            if record.get("id") == record_id:
                return record
        return {}

    def _spell_for_recipe(self, recipe: dict) -> dict:
        return self._get_static_record("spells", recipe.get("spell_id"))

    def _item_for_recipe(self, recipe: dict) -> dict:
        return self._get_static_record("items", recipe.get("creates_item_id"))

    def _recipe_name(self, recipe: dict, language: str = "de") -> str:
        language = self.normalize_recipe_language(language)
        spell = self._spell_for_recipe(recipe)
        item = self._item_for_recipe(recipe)
        return (
            self._localized_text(item.get("name"), language)
            or self._localized_text(spell.get("name"), language)
            or str(recipe.get("id") or recipe.get("spell_id") or "")
        )

    def _recipe_secondary_name(self, recipe: dict, language: str = "de") -> str:
        other_language = (
            "en" if self.normalize_recipe_language(language) == "de" else "de"
        )
        name = self._recipe_name(recipe, other_language)
        return name if name != self._recipe_name(recipe, language) else ""

    def _recipe_source_label(self, recipe: dict) -> str:
        sources = [str(source) for source in recipe.get("recipe_item_sources") or []]
        if not sources:
            return "Quelle unbekannt"
        labels = {
            "drop": "Drop",
            "world_drop": "World-Drop",
            "pickpocketed": "Taschendiebstahl",
            "quest": "Quest",
            "vendor": "Haendler",
            "crafted": "Crafting",
        }
        return ", ".join(labels.get(source, source) for source in sources)

    def recipe_learning_reward(self, recipe: dict) -> tuple[str, int]:
        """Return ``(rarity, points)`` for a recipe.

        Points scale with two factors:
        * **Source**: World-drops > pickpocketed > regular drops > quest.
          Vendor-only or trainer recipes don't trigger an event (0 points).
        * **Skill bracket**: required_skill 276-300 → ×3, 201-275 → ×2,
          101-200 → ×1.5, 1-100 → ×1.

        Hand-curated "epic" recipes (Crusader enchant, Arcanite gear, etc.)
        start at a 10-point base and still scale with the skill multiplier.
        """
        if not recipe or recipe.get("learned_from") == "trainer":
            return "common", 0
        spell_id = str(recipe.get("spell_id") or "")
        sources = {str(source) for source in recipe.get("recipe_item_sources") or []}
        required_skill = int(recipe.get("required_skill") or 0)

        if spell_id in EPIC_RECIPE_SPELL_IDS:
            base = EPIC_RECIPE_BASE_POINTS
            rarity = "epic"
        else:
            base = max(
                (
                    RECIPE_POINTS_BY_SOURCE[src]
                    for src in sources
                    if src in RECIPE_POINTS_BY_SOURCE
                ),
                default=0,
            )
            if base == 0:
                return "common", 0
            rarity = "rare"

        multiplier = next(
            mult
            for threshold, mult in RECIPE_SKILL_BRACKETS
            if required_skill >= threshold
        )
        points = max(1, int(round(base * multiplier)))
        return rarity, points

    def _recipe_search_text(self, recipe: dict) -> str:
        spell = self._spell_for_recipe(recipe)
        item = self._item_for_recipe(recipe)
        parts = [
            recipe.get("id", ""),
            recipe.get("spell_id", ""),
            self._localized_text(spell.get("name"), "de"),
            self._localized_text(spell.get("name"), "en"),
            self._localized_text(item.get("name"), "de"),
            self._localized_text(item.get("name"), "en"),
        ]
        return " ".join(_norm(part) for part in parts if part)

    def resolve_profession_id(self, value: str) -> str | None:
        needle = _norm(value)
        for profession in self._crafting_professions():
            names = [
                profession.get("id", ""),
                self._localized_text(profession.get("name"), "de"),
                self._localized_text(profession.get("name"), "en"),
            ]
            if needle in {_norm(name) for name in names if name}:
                return profession["id"]
        return None

    def profession_choices(self, current: str = "") -> list[tuple[str, str]]:
        needle = _norm(current)
        choices = []
        for profession in self._crafting_professions():
            name = self._localized_text(profession.get("name"))
            profession_id = profession.get("id")
            if not profession_id or not name:
                continue
            searchable = f"{profession_id} {name} {self._localized_text(profession.get('name'), 'en')}"
            if not needle or needle in _norm(searchable):
                choices.append((name, profession_id))
        return choices[:25]

    def profession_choices_for_claim(
        self, profiles: list[CharacterProfession], current: str = ""
    ) -> list[tuple[str, str, str]]:
        needle = _norm(current)
        current_ids = {profile.profession_id for profile in profiles}
        primary_count = sum(
            1
            for profile in profiles
            if self._is_primary_profession(profile.profession_id)
        )
        choices = []
        for profession in self._crafting_professions():
            profession_id = profession.get("id")
            if not profession_id:
                continue
            is_existing = profession_id in current_ids
            is_primary = self._is_primary_profession(profession_id)
            if (
                not is_existing
                and is_primary
                and primary_count >= MAX_PRIMARY_PROFESSIONS
            ):
                continue
            if (
                not is_existing
                and not is_primary
                and profession_id not in SECONDARY_CRAFTING_PROFESSIONS
            ):
                continue
            name = self._localized_text(profession.get("name"))
            if not name:
                continue
            searchable = f"{profession_id} {name} {self._localized_text(profession.get('name'), 'en')}"
            if needle and needle not in _norm(searchable):
                continue
            profile = next(
                (
                    profile
                    for profile in profiles
                    if profile.profession_id == profession_id
                ),
                None,
            )
            if profile:
                description = f"Aktuell: Skill {profile.skill_level}"
            elif is_primary:
                description = "Freier Hauptberuf-Slot"
            else:
                description = "Nebenberuf"
            choices.append((name, profession_id, description))
        return choices[:25]

    def format_profession_slots(self, profiles: list[CharacterProfession]) -> str:
        primary_profiles = [
            profile
            for profile in profiles
            if self._is_primary_profession(profile.profession_id)
        ]
        primary_profiles.sort(
            key=lambda profile: self._profession_name(profile.profession_id)
        )
        lines = []
        for index in range(MAX_PRIMARY_PROFESSIONS):
            if index < len(primary_profiles):
                profile = primary_profiles[index]
                lines.append(
                    f"Hauptberuf {index + 1}: {self.format_profession(profile)}"
                )
            else:
                lines.append(f"Hauptberuf {index + 1}: frei")

        cooking = next(
            (profile for profile in profiles if profile.profession_id == "cooking"),
            None,
        )
        if cooking:
            lines.append(f"Kochen: {self.format_profession(cooking)}")
        else:
            lines.append("Kochen: frei")
        return "\n".join(lines)

    def format_profession_slots_short(self, profiles: list[CharacterProfession]) -> str:
        primary_profiles = [
            profile
            for profile in profiles
            if self._is_primary_profession(profile.profession_id)
        ]
        primary_profiles.sort(
            key=lambda profile: self._profession_name(profile.profession_id)
        )
        lines = []
        for index in range(MAX_PRIMARY_PROFESSIONS):
            if index < len(primary_profiles):
                profile = primary_profiles[index]
                lines.append(
                    f"Hauptberuf {index + 1}: {self.format_profession_short(profile)}"
                )
            else:
                lines.append(f"Hauptberuf {index + 1}: frei")

        cooking = next(
            (profile for profile in profiles if profile.profession_id == "cooking"),
            None,
        )
        if cooking:
            lines.append(f"Kochen: {self.format_profession_short(cooking)}")
        else:
            lines.append("Kochen: frei")
        return "\n".join(lines)

    async def set_crafting_profile(
        self,
        discord_user_id: int,
        char_name: str,
        profession_value: str,
        skill_level: int,
        specialization: str | None,
        *,
        is_mod: bool = False,
    ) -> CraftingProfileResult:
        if skill_level < 1 or skill_level > 300:
            return CraftingProfileResult(None, reason="invalid_skill")
        profession_id = self.resolve_profession_id(profession_value)
        if not profession_id:
            return CraftingProfileResult(None, reason="unknown_profession")
        claim = await self.data.get_claim_by_name(char_name)
        if not claim:
            return CraftingProfileResult(None, reason="not_claimed")
        if not is_mod and claim.discord_user_id != discord_user_id:
            return CraftingProfileResult(None, claim=claim, reason="forbidden")
        profiles = await self.data.professions_for_character(claim.character_key)
        already_set = any(
            profile.profession_id == profession_id for profile in profiles
        )
        primary_count = sum(
            1
            for profile in profiles
            if self._is_primary_profession(profile.profession_id)
        )
        if (
            self._is_primary_profession(profession_id)
            and not already_set
            and primary_count >= MAX_PRIMARY_PROFESSIONS
        ):
            return CraftingProfileResult(None, claim=claim, reason="primary_limit")
        previous = await self.data.get_character_profession(
            claim.character_key, profession_id
        )
        old_skill = int(previous.skill_level) if previous else 0
        profession = await self.data.set_character_profession(
            claim, profession_id, skill_level, specialization
        )
        await self._record_skill_milestones(
            claim.character_key, profession_id, old_skill, int(skill_level)
        )
        return CraftingProfileResult(profession, claim=claim, reason="saved")

    async def _record_skill_milestones(
        self,
        character_key: str,
        profession_id: str,
        old_skill: int,
        new_skill: int,
    ) -> None:
        """Record milestone events for every threshold crossed in this update.

        Cumulative: a jump from 50 to 250 awards 75 and 150 and 225 in one go.
        Idempotent via the table's primary key (character_key, profession_id,
        threshold) plus an explicit ``skill_milestone_exists`` guard so we
        only ever count the same crossing once.
        """
        if new_skill <= old_skill:
            return
        for threshold in sorted(PROFESSION_SKILL_MILESTONES):
            if not (old_skill < threshold <= new_skill):
                continue
            if await self.data.skill_milestone_exists(
                character_key, profession_id, threshold
            ):
                continue
            await self.data.record_skill_milestone(
                character_key,
                profession_id,
                threshold,
                new_skill,
                PROFESSION_SKILL_MILESTONES[threshold],
            )

    async def remove_crafting_profile(
        self,
        discord_user_id: int,
        char_name: str,
        profession_value: str,
        *,
        is_mod: bool = False,
    ) -> CraftingProfileResult:
        profession_id = self.resolve_profession_id(profession_value)
        if not profession_id:
            return CraftingProfileResult(None, reason="unknown_profession")
        claim = await self.data.get_claim_by_name(char_name)
        if not claim:
            return CraftingProfileResult(None, reason="not_claimed")
        if not is_mod and claim.discord_user_id != discord_user_id:
            return CraftingProfileResult(None, claim=claim, reason="forbidden")
        removed = await self.data.remove_character_profession(
            claim.character_key, profession_id
        )
        return CraftingProfileResult(
            None, claim=claim, reason="removed" if removed else "not_set"
        )

    async def prepare_recipe_selection(
        self,
        discord_user_id: int,
        char_name: str,
        profession_value: str | None,
        search: str | None,
        *,
        is_mod: bool = False,
    ) -> RecipeSelectionResult:
        claim = await self.data.get_claim_by_name(char_name)
        if not claim:
            return RecipeSelectionResult("not_claimed")
        if not is_mod and claim.discord_user_id != discord_user_id:
            return RecipeSelectionResult("forbidden", claim=claim)

        profiles = await self.data.professions_for_character(claim.character_key)
        if not profiles:
            return RecipeSelectionResult("no_professions", claim=claim, profiles=[])

        if profession_value:
            profession_id = self.resolve_profession_id(profession_value)
            if not profession_id:
                return RecipeSelectionResult("unknown_profession", claim=claim)
            profile = next(
                (
                    profile
                    for profile in profiles
                    if profile.profession_id == profession_id
                ),
                None,
            )
            if not profile:
                return RecipeSelectionResult("profession_not_set", claim=claim)
            return await self._recipe_selection_for_profile(claim, profile, search)

        if len(profiles) == 1:
            return await self._recipe_selection_for_profile(claim, profiles[0], search)
        return RecipeSelectionResult(
            "choose_profession", claim=claim, profiles=profiles
        )

    async def _recipe_selection_for_profile(
        self,
        claim: CharacterClaim,
        profile: CharacterProfession,
        search: str | None,
    ) -> RecipeSelectionResult:
        known_spell_ids = await self.data.known_recipe_spell_ids(claim.character_key)
        recipes = self._available_manual_recipes(profile, known_spell_ids, search)
        return RecipeSelectionResult(
            "ok",
            claim=claim,
            profile=profile,
            recipes=recipes,
        )

    def _available_manual_recipes(
        self,
        profile: CharacterProfession,
        known_spell_ids: set[str],
        search: str | None,
    ) -> list[dict]:
        needle = _norm(search or "")
        recipes = []
        for recipe in self._wow_records("profession_recipes"):
            if recipe.get("profession_id") != profile.profession_id:
                continue
            if recipe.get("learned_from") == "trainer":
                continue
            if not recipe.get("hardcore_valid"):
                continue
            if int(recipe.get("required_skill") or 0) > profile.skill_level:
                continue
            if recipe.get("spell_id") in known_spell_ids:
                continue
            if needle and needle not in self._recipe_search_text(recipe):
                continue
            recipes.append(recipe)
        return sorted(
            recipes,
            key=lambda recipe: (
                int(recipe.get("required_skill") or 0),
                self._recipe_name(recipe).casefold(),
            ),
        )

    async def save_known_recipes(
        self,
        claim: CharacterClaim,
        profession_id: str,
        spell_ids: list[str],
    ) -> int:
        valid_recipes = {
            recipe.get("spell_id"): recipe
            for recipe in self._wow_records("profession_recipes")
            if recipe.get("profession_id") == profession_id
            and recipe.get("learned_from") != "trainer"
            and recipe.get("hardcore_valid")
        }
        accepted = [spell_id for spell_id in spell_ids if spell_id in valid_recipes]
        inserted = await self.data.add_known_recipes_returning_inserted(
            claim.character_key, profession_id, accepted
        )
        for spell_id in inserted:
            rarity, points = self.recipe_learning_reward(valid_recipes[spell_id])
            if points > 0 and claim.status == "verified":
                await self.data.record_recipe_learning_event(
                    claim.character_key, spell_id, profession_id, rarity, points
                )
        return len(inserted)

    async def known_recipes_for_character(
        self,
        discord_user_id: int,
        char_name: str,
        *,
        is_mod: bool = False,
    ) -> RecipeSelectionResult:
        claim = await self.data.get_claim_by_name(char_name)
        if not claim:
            return RecipeSelectionResult("not_claimed")
        if not is_mod and claim.discord_user_id != discord_user_id:
            return RecipeSelectionResult("forbidden", claim=claim)
        records = await self.data.known_recipes_for_character(claim.character_key)
        return RecipeSelectionResult("ok", claim=claim, recipes=list(records))

    async def remove_known_recipe(
        self,
        discord_user_id: int,
        char_name: str,
        recipe_value: str,
        *,
        is_mod: bool = False,
    ) -> RecipeSelectionResult:
        claim = await self.data.get_claim_by_name(char_name)
        if not claim:
            return RecipeSelectionResult("not_claimed")
        if not is_mod and claim.discord_user_id != discord_user_id:
            return RecipeSelectionResult("forbidden", claim=claim)
        recipe = await self.resolve_known_recipe(claim.character_key, recipe_value)
        if not recipe:
            return RecipeSelectionResult("recipe_not_found", claim=claim)
        removed = await self.data.remove_known_recipe(
            claim.character_key, recipe.spell_id
        )
        return RecipeSelectionResult(
            "removed" if removed else "recipe_not_found", claim=claim
        )

    async def resolve_known_recipe(
        self, character_key: str, recipe_value: str
    ) -> CharacterKnownRecipe | None:
        needle = _norm(recipe_value)
        for recipe in await self.data.known_recipes_for_character(character_key):
            static = self._recipe_by_spell_id(recipe.spell_id)
            names = [
                recipe.spell_id,
                self._recipe_name(static) if static else "",
                (
                    self._localized_text(
                        self._spell_for_recipe(static).get("name"), "de"
                    )
                    if static
                    else ""
                ),
                (
                    self._localized_text(
                        self._spell_for_recipe(static).get("name"), "en"
                    )
                    if static
                    else ""
                ),
            ]
            if needle in {_norm(name) for name in names if name}:
                return recipe
        return None

    def _recipe_by_spell_id(self, spell_id: str | None) -> dict:
        for recipe in self._wow_records("profession_recipes"):
            if recipe.get("spell_id") == spell_id:
                return recipe
        return {}

    async def search_crafting(self, item_name: str) -> CraftingSearchResult:
        matches = self._match_items(item_name)
        if not matches:
            return CraftingSearchResult("item_not_found")
        # Filter: keep only items that are the output of some profession recipe.
        # Drops recipe-teaching items ("Rezept: ...") and other non-craftable
        # matches that the fuzzy name search returned.
        craftable_ids = {
            str(r.get("creates_item_id"))
            for r in self._wow_records("profession_recipes")
            if r.get("creates_item_id")
        }
        craftable = [m for m in matches if str(m.get("id")) in craftable_ids]
        if not craftable:
            return CraftingSearchResult("item_not_found")
        if len(craftable) > 1:
            return CraftingSearchResult("ambiguous_item", candidates=craftable[:5])
        return await self._search_crafting_for_item(craftable[0])

    async def search_crafting_by_item_id(self, item_id: str) -> CraftingSearchResult:
        item = self._get_static_record("items", item_id)
        if not item:
            return CraftingSearchResult("item_not_found")
        return await self._search_crafting_for_item(item)

    async def _search_crafting_for_item(self, item: dict) -> CraftingSearchResult:
        recipes = [
            recipe
            for recipe in self._wow_records("profession_recipes")
            if recipe.get("creates_item_id") == item.get("id")
            and recipe.get("hardcore_valid")
            and recipe.get("profession_id") != "first-aid"
        ]
        if not recipes:
            return CraftingSearchResult("recipe_not_found", item=item)

        trainer_recipes = [
            recipe for recipe in recipes if recipe.get("learned_from") == "trainer"
        ]
        manual_recipes = [
            recipe for recipe in recipes if recipe.get("learned_from") != "trainer"
        ]
        recipe = min(
            trainer_recipes,
            key=lambda record: int(record.get("required_skill") or 0),
            default=None,
        )
        manual_recipe = False
        if recipe is None and manual_recipes:
            recipe = min(
                manual_recipes,
                key=lambda record: int(record.get("required_skill") or 0),
            )
            manual_recipe = True
        if recipe is None:
            return CraftingSearchResult("recipe_not_found", item=item)

        profession_id = recipe.get("profession_id")
        required_skill = int(recipe.get("required_skill") or 1)
        if manual_recipe:
            crafters = await self.data.find_crafters_with_known_recipe(
                profession_id, required_skill, str(recipe.get("spell_id"))
            )
        else:
            crafters = await self.data.find_crafters(profession_id, required_skill)
        if not crafters:
            status = "manual_recipe" if manual_recipe else "no_crafter"
            return CraftingSearchResult(
                status,
                item=item,
                recipe=recipe,
                required_skill=required_skill,
                profession_id=profession_id,
                crafters=[],
                manual_recipe=manual_recipe,
            )
        return CraftingSearchResult(
            "ok",
            item=item,
            recipe=recipe,
            crafters=crafters,
            required_skill=required_skill,
            profession_id=profession_id,
            manual_recipe=manual_recipe,
        )

    def _match_items(self, item_name: str) -> list[dict]:
        needle = _norm(item_name)
        exact = []
        partial = []
        fuzzy: list[tuple[float, dict]] = []
        for item in self._wow_records("items"):
            names = [
                self._localized_text(item.get("name"), "de"),
                self._localized_text(item.get("name"), "en"),
            ]
            normalized = [_norm(name) for name in names if name]
            if needle in normalized:
                exact.append(item)
            elif any(needle and needle in name for name in normalized):
                partial.append(item)
            elif needle:
                score = max(
                    (
                        difflib.SequenceMatcher(None, needle, name).ratio()
                        for name in normalized
                    ),
                    default=0,
                )
                if score >= 0.82:
                    fuzzy.append((score, item))
        if exact:
            return exact[:25]
        if partial:
            return partial[:25]
        fuzzy.sort(
            key=lambda match: (
                -match[0],
                self._localized_text(match[1].get("name")).casefold(),
            )
        )
        return [item for _, item in fuzzy[:25]]

    def format_profession(self, profile: CharacterProfession) -> str:
        specialization = (
            f" ({profile.specialization})" if profile.specialization else ""
        )
        return (
            f"**{profile.character_name}** - "
            f"{self._profession_name(profile.profession_id)} "
            f"{profile.skill_level}{specialization}"
        )

    def format_profession_short(self, profile: CharacterProfession) -> str:
        specialization = (
            f" ({profile.specialization})" if profile.specialization else ""
        )
        return (
            f"{self._profession_name(profile.profession_id)} "
            f"{profile.skill_level}{specialization}"
        )

    def format_crafting_search_result(self, result: CraftingSearchResult) -> str:
        if result.status == "item_not_found":
            return "Dieses Item wurde in den WoW-Daten nicht gefunden."
        if result.status == "ambiguous_item":
            return "Mehrere Items gefunden — bitte aus dem Menü wählen."
        item_name = self._localized_text((result.item or {}).get("name"))
        if result.status == "recipe_not_found":
            return f"Für **{item_name}** wurde kein Crafting-Rezept gefunden."
        if result.status == "manual_recipe":
            return (
                f"**{item_name}** ist ein Spezialrezept. "
                "Aktuell hat es noch niemand gepflegt."
            )
        profession_name = self._profession_name(result.profession_id or "")
        if result.status == "no_crafter":
            return (
                f"**{item_name}** benötigt {profession_name} "
                f"{result.required_skill}. Kein geclaimter Crafter passt aktuell."
            )
        lines = [
            f"**{item_name}** kann gecraftet werden von:",
            "",
        ]
        for crafter in result.crafters or []:
            specialization = (
                f" ({crafter.specialization})" if crafter.specialization else ""
            )
            recipe_note = " - Spezialrezept gepflegt" if result.manual_recipe else ""
            lines.append(
                f"- <@{crafter.discord_user_id}> mit **{crafter.character_name}** "
                f"({profession_name} {crafter.skill_level}{specialization}){recipe_note}"
            )
        return "\n".join(lines)

    async def update_claim_review_message(
        self, interaction: discord.Interaction, claim: CharacterClaim, action: str
    ) -> None:
        if action == "verified":
            content = (
                f"{self.format_claim_review(claim)}\n"
                f"Bestätigt von <@{interaction.user.id}>."
            )
        else:
            content = (
                f"{self.format_claim_review(claim)}\n"
                f"Abgelehnt von <@{interaction.user.id}>."
            )
        await interaction.response.edit_message(content=content, view=None)

    async def status(self) -> dict[str, object]:
        channel_id = await self.get_announcement_channel_id()
        panel_channel_id = await self.data.get_setting("panel_channel_id")
        panel_message_id = await self.data.get_setting("panel_message_id")
        return {
            "guild": self.guild_name,
            "realm": self.realm_slug,
            "channel_id": channel_id,
            "officer_channel_id": await self.get_claim_review_channel_id(),
            "panel_channel_id": int(panel_channel_id) if panel_channel_id else None,
            "panel_message_id": int(panel_message_id) if panel_message_id else None,
            "last_scan_at": await self.data.last_scan_at(),
            "member_count": await self.data.member_count(),
            "poll_interval": self.poll_interval,
            "recipe_events": "aktiv",
        }

    def cog_unload(self) -> None:
        super().cog_unload()
        self.create_task(self.data.close())


class CraftingProfessionSelect(discord.ui.Select):
    def __init__(
        self,
        cog: WoWCog,
        owner_user_id: int,
        claim: CharacterClaim,
        profiles: list[CharacterProfession],
        search: str | None,
        language: str = "de",
    ) -> None:
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claim = claim
        self.profiles = profiles
        self.search = search
        self.language = cog.normalize_recipe_language(language)
        options = [
            discord.SelectOption(
                label=cog._profession_name(profile.profession_id),
                value=profile.profession_id,
                description=f"Skill {profile.skill_level}",
            )
            for profile in profiles[:25]
        ]
        super().__init__(
            placeholder="Beruf auswählen",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        profile = next(
            (
                profile
                for profile in self.profiles
                if profile.profession_id == self.values[0]
            ),
            None,
        )
        if profile is None:
            await interaction.response.send_message(
                "Dieser Beruf ist nicht mehr verfügbar.", ephemeral=True
            )
            return
        result = await self.cog._recipe_selection_for_profile(
            self.claim, profile, self.search
        )
        if not result.recipes:
            await interaction.response.edit_message(
                content=(
                    f"Für **{self.claim.character_name}** gibt es aktuell keine "
                    f"offenen Spezialrezepte für "
                    f"{self.cog._profession_name(profile.profession_id)}."
                ),
                view=None,
            )
            return
        view = CraftingRecipeSelectionView(
            self.cog,
            self.owner_user_id,
            self.claim,
            profile,
            result.recipes,
            language=self.language,
        )
        await interaction.response.edit_message(content=view.content(), view=view)


class CraftingProfessionSelectView(discord.ui.View):
    def __init__(
        self,
        cog: WoWCog,
        owner_user_id: int,
        claim: CharacterClaim,
        profiles: list[CharacterProfession],
        search: str | None,
        language: str = "de",
    ) -> None:
        super().__init__(timeout=300)
        self.owner_user_id = owner_user_id
        self.add_item(
            CraftingProfessionSelect(
                cog, owner_user_id, claim, profiles, search, language
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class CraftingRecipeSelect(discord.ui.Select):
    def __init__(self, parent: "CraftingRecipeSelectionView") -> None:
        self.parent_view = parent
        options = [
            discord.SelectOption(
                label=parent.option_label(recipe),
                value=str(recipe.get("spell_id")),
                description=parent.option_description(recipe),
                default=str(recipe.get("spell_id")) in parent.selected_spell_ids,
            )
            for recipe in parent.current_page_recipes()
        ]
        super().__init__(
            placeholder="Gelernte Rezepte auswählen",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        current_spell_ids = {
            str(recipe.get("spell_id"))
            for recipe in self.parent_view.current_page_recipes()
        }
        self.parent_view.selected_spell_ids -= current_spell_ids
        self.parent_view.selected_spell_ids.update(self.values)
        self.parent_view.refresh_items()
        await interaction.response.edit_message(
            content=self.parent_view.content(),
            view=self.parent_view,
        )


class CraftingRecipeSelectionView(discord.ui.View):
    page_size = 25

    def __init__(
        self,
        cog: WoWCog,
        owner_user_id: int,
        claim: CharacterClaim,
        profile: CharacterProfession,
        recipes: list[dict],
        language: str = "de",
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claim = claim
        self.profile = profile
        self.recipes = recipes
        self.language = cog.normalize_recipe_language(language)
        self.page = 0
        self.selected_spell_ids: set[str] = set()
        self.refresh_items()

    @property
    def max_page(self) -> int:
        return max(0, (len(self.recipes) - 1) // self.page_size)

    def current_page_recipes(self) -> list[dict]:
        start = self.page * self.page_size
        return self.recipes[start : start + self.page_size]

    def option_label(self, recipe: dict) -> str:
        label = self.cog._recipe_name(recipe, self.language)
        return label[:100] or str(recipe.get("spell_id"))[:100]

    def option_description(self, recipe: dict) -> str:
        skill = int(recipe.get("required_skill") or 0)
        spell = self.cog._spell_for_recipe(recipe)
        other_name = self.cog._recipe_secondary_name(recipe, self.language)
        spell_name = self.cog._localized_text(spell.get("name"), self.language)
        text = f"Skill {skill}"
        if other_name:
            text = f"{text} - {other_name}"
        elif spell_name and spell_name != self.option_label(recipe):
            text = f"{text} - {spell_name}"
        return text[:100]

    def content(self) -> str:
        return _recipe_selection_content(
            self.cog,
            self.claim,
            self.profile,
            self.recipes,
            self.page,
            self.selected_spell_ids,
        )

    def refresh_items(self) -> None:
        self.clear_items()
        self.add_item(CraftingRecipeSelect(self))
        self.previous_page.disabled = self.page <= 0
        self.next_page.disabled = self.page >= self.max_page
        self.add_item(self.previous_page)
        self.add_item(self.next_page)
        self.add_item(self.save)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False

    @discord.ui.button(label="Zurück", style=discord.ButtonStyle.secondary)
    async def previous_page(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        self.page = max(0, self.page - 1)
        self.refresh_items()
        await interaction.response.edit_message(content=self.content(), view=self)

    @discord.ui.button(label="Weiter", style=discord.ButtonStyle.secondary)
    async def next_page(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        self.page = min(self.max_page, self.page + 1)
        self.refresh_items()
        await interaction.response.edit_message(content=self.content(), view=self)

    @discord.ui.button(label="Speichern", style=discord.ButtonStyle.success)
    async def save(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        if not self.selected_spell_ids:
            await interaction.response.send_message(
                "Bitte wähle mindestens ein Rezept aus.", ephemeral=True
            )
            return
        saved = await self.cog.save_known_recipes(
            self.claim,
            self.profile.profession_id,
            sorted(self.selected_spell_ids),
        )
        await interaction.response.edit_message(
            content=(
                f"{saved} Rezepte für **{self.claim.character_name}** gespeichert."
            ),
            view=None,
        )


class CraftingSearchSuggestionSelect(discord.ui.Select):
    def __init__(self, parent: "CraftingSearchSuggestionView") -> None:
        self.parent_view = parent
        super().__init__(
            placeholder="Item auswählen",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=parent.cog._localized_text(item.get("name"), "de")[:100],
                    value=str(item.get("id")),
                    description=parent.cog._localized_text(item.get("name"), "en")[
                        :100
                    ],
                )
                for item in parent.items[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await self.parent_view.cog.search_crafting_by_item_id(self.values[0])
        await interaction.response.edit_message(
            content=self.parent_view.cog.format_crafting_search_result(result),
            view=None,
        )


class CraftingSearchSuggestionView(discord.ui.View):
    def __init__(self, cog: WoWCog, owner_user_id: int, items: list[dict]) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.items = items
        self.add_item(CraftingSearchSuggestionSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


def _recipe_selection_content(
    cog: WoWCog,
    claim: CharacterClaim,
    profile: CharacterProfession,
    recipes: list[dict],
    page: int = 0,
    selected: set[str] | None = None,
) -> str:
    selected_count = len(selected or set())
    return (
        f"**{claim.character_name}** - "
        f"{cog._profession_name(profile.profession_id)} {profile.skill_level}\n"
        f"Offene Spezialrezepte: {len(recipes)} | Seite {page + 1} | "
        f"ausgewählt: {selected_count}"
    )


class PanelCharacterSearchModal(discord.ui.Modal):
    def __init__(self, cog: WoWCog) -> None:
        super().__init__(title="Charakter suchen")
        self.cog = cog
        self.query = discord.ui.TextInput(
            label="Charaktername",
            placeholder="z.B. Voidok",
            min_length=2,
            max_length=32,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        query = str(self.query.value).strip()
        snapshot = await self.cog.data.get_snapshot()
        matches = [
            member
            for member in sorted(
                snapshot.values(), key=lambda item: item.name.casefold()
            )
            if query.casefold() in member.name.casefold()
        ][:25]
        if not matches:
            await interaction.response.send_message(
                f"Kein Black-Lotus-Charakter zu **{query}** gefunden.",
                ephemeral=True,
            )
            return
        view = PanelRosterCharacterSelectView(self.cog, interaction.user.id, matches)
        await interaction.response.send_message(
            "Bitte wähle deinen Charakter aus.",
            view=view,
            ephemeral=True,
        )


class PanelRosterCharacterSelect(discord.ui.Select):
    def __init__(self, parent: "PanelRosterCharacterSelectView") -> None:
        self.parent_view = parent
        super().__init__(
            placeholder="Charakter auswählen",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=member.name[:100],
                    value=member.name,
                    description=(
                        f"Level {member.level} - "
                        f"{parent.cog._display_character(member)}"
                    )[:100],
                )
                for member in parent.members
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await self.parent_view.cog.claim_character(
            interaction.user.id, self.values[0]
        )
        await interaction.response.edit_message(
            content=_format_panel_claim_result(result, self.values[0]),
            view=None,
        )


class PanelRosterCharacterSelectView(discord.ui.View):
    def __init__(
        self, cog: WoWCog, owner_user_id: int, members: list[RosterMember]
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.members = members
        self.add_item(PanelRosterCharacterSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class PanelOwnedCharacterSelect(discord.ui.Select):
    def __init__(
        self, parent: "PanelOwnedCharacterSelectView", claims: list[CharacterClaim]
    ) -> None:
        self.parent_view = parent
        super().__init__(
            placeholder="Charakter auswählen",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=claim.character_name[:100],
                    value=claim.character_name,
                    description=(
                        "bestätigt" if claim.status == "verified" else "ungeprüft"
                    ),
                )
                for claim in claims[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        claim = await self.parent_view.cog.data.get_claim_by_name(self.values[0])
        if not claim or claim.discord_user_id != interaction.user.id:
            await interaction.response.edit_message(
                content="Dieser Charakter ist nicht mehr verfügbar.",
                view=None,
            )
            return
        if self.parent_view.mode == "profession":
            profiles = await self.parent_view.cog.data.professions_for_character(
                claim.character_key
            )
            view = PanelProfessionSelectView(
                self.parent_view.cog, interaction.user.id, claim, profiles
            )
            await interaction.response.edit_message(
                content=(
                    f"Berufe fuer **{claim.character_name}**:\n"
                    f"{self.parent_view.cog.format_profession_slots(profiles)}\n\n"
                    "Welchen Beruf moechtest du pflegen?"
                ),
                view=view,
            )
            return
        profiles = await self.parent_view.cog.data.professions_for_character(
            claim.character_key
        )
        if not profiles:
            await interaction.response.edit_message(
                content=(
                    f"Für **{claim.character_name}** sind noch keine Berufe gepflegt. "
                    "Nutze zuerst **Berufe pflegen**."
                ),
                view=None,
            )
            return
        view = PanelRecipeProfessionSelectView(
            self.parent_view.cog, interaction.user.id, claim, profiles
        )
        await interaction.response.edit_message(
            content="Für welchen Beruf möchtest du Spezialrezepte pflegen?",
            view=view,
        )


class PanelOwnedCharacterSelectView(discord.ui.View):
    def __init__(
        self,
        cog: WoWCog,
        owner_user_id: int,
        claims: list[CharacterClaim],
        mode: str,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.mode = mode
        self.add_item(PanelOwnedCharacterSelect(self, claims))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class PanelProfessionSelect(discord.ui.Select):
    def __init__(self, parent: "PanelProfessionSelectView") -> None:
        self.parent_view = parent
        choices = parent.cog.profession_choices_for_claim(parent.profiles)
        super().__init__(
            placeholder="Beruf auswählen",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=name[:100],
                    value=value,
                    description=description[:100],
                )
                for name, value, description in choices
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            PanelProfessionEditModal(
                self.parent_view.cog,
                self.parent_view.claim,
                self.values[0],
            )
        )


class PanelProfessionSelectView(discord.ui.View):
    def __init__(
        self,
        cog: WoWCog,
        owner_user_id: int,
        claim: CharacterClaim,
        profiles: list[CharacterProfession],
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claim = claim
        self.profiles = profiles
        self.add_item(PanelProfessionSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class PanelProfessionEditModal(discord.ui.Modal):
    def __init__(self, cog: WoWCog, claim: CharacterClaim, profession_id: str) -> None:
        super().__init__(title="Beruf pflegen")
        self.cog = cog
        self.claim = claim
        self.profession_id = profession_id
        self.skill = discord.ui.TextInput(
            label="Skill",
            placeholder="1-300",
            min_length=1,
            max_length=3,
        )
        self.specialization = discord.ui.TextInput(
            label="Spezialisierung",
            placeholder="optional, z.B. Tränke",
            required=False,
            max_length=64,
        )
        self.add_item(self.skill)
        self.add_item(self.specialization)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            skill = int(str(self.skill.value).strip())
        except ValueError:
            await interaction.response.send_message(
                "Skill muss eine Zahl zwischen 1 und 300 sein.",
                ephemeral=True,
            )
            return
        result = await self.cog.set_crafting_profile(
            interaction.user.id,
            self.claim.character_name,
            self.profession_id,
            skill,
            str(self.specialization.value).strip() or None,
        )
        await interaction.response.send_message(
            _format_panel_profession_result(self.cog, result),
            ephemeral=True,
        )


class PanelRecipeProfessionSelect(discord.ui.Select):
    def __init__(self, parent: "PanelRecipeProfessionSelectView") -> None:
        self.parent_view = parent
        super().__init__(
            placeholder="Beruf auswählen",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=parent.cog._profession_name(profile.profession_id)[:100],
                    value=profile.profession_id,
                    description=f"Skill {profile.skill_level}",
                )
                for profile in parent.profiles[:25]
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await self.parent_view.cog.prepare_recipe_selection(
            interaction.user.id,
            self.parent_view.claim.character_name,
            self.values[0],
            None,
        )
        if result.status != "ok" or not result.recipes:
            await interaction.response.edit_message(
                content=(
                    f"Für **{self.parent_view.claim.character_name}** gibt es "
                    "aktuell keine offenen Spezialrezepte."
                ),
                view=None,
            )
            return
        view = CraftingRecipeSelectionView(
            self.parent_view.cog,
            interaction.user.id,
            result.claim,
            result.profile,
            result.recipes,
        )
        await interaction.response.edit_message(
            content=view.content(),
            view=view,
        )


class PanelRecipeProfessionSelectView(discord.ui.View):
    def __init__(
        self,
        cog: WoWCog,
        owner_user_id: int,
        claim: CharacterClaim,
        profiles: list[CharacterProfession],
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claim = claim
        self.profiles = profiles
        self.add_item(PanelRecipeProfessionSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class PanelCraftingSearchModal(discord.ui.Modal):
    def __init__(self, cog: WoWCog) -> None:
        super().__init__(title="Crafter in der Gilde suchen")
        self.cog = cog
        self.item = discord.ui.TextInput(
            label="Welches Item brauchst du?",
            placeholder="z. B. Wuttrank, Klingenstein-Rüstung ...",
            min_length=2,
            max_length=80,
        )
        self.add_item(self.item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        result = await self.cog.search_crafting(str(self.item.value).strip())
        content = self.cog.format_crafting_search_result(result)
        # discord.py's send_message uses MISSING as the "no view" sentinel
        # and does ``not view.is_finished()`` on whatever else is passed —
        # explicitly passing ``view=None`` raises AttributeError. Only
        # forward ``view=...`` when we actually have a View instance.
        if result.status == "ambiguous_item":
            view = CraftingSearchSuggestionView(
                self.cog, interaction.user.id, result.candidates or []
            )
            await interaction.response.send_message(content, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(content, ephemeral=True)


class PanelCooldownStartView(discord.ui.View):
    """Ephemeral picker for logging a craft-cooldown.

    Each option is a (char, CD-spell) pair derived from the user's
    explicitly-learned recipes. Click → "now" is persisted via
    :meth:`WoWCog.log_cooldown` and the user gets a confirmation with the
    computed ready-at time.
    """

    def __init__(
        self,
        cog: WoWCog,
        owner_user_id: int,
        options: list[tuple[CharacterClaim, str, str, str]],
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.options = options
        self.add_item(PanelCooldownStartSelect(self))
        _add_dismiss_button(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class PanelCooldownStartSelect(discord.ui.Select):
    def __init__(self, parent: PanelCooldownStartView) -> None:
        self.parent_view = parent
        # Each value encodes "<character_key>|<spell_id>" so the callback
        # knows both pieces without juggling extra state.
        select_options = []
        for claim, spell_id, spell_name, group_label in parent.options[:25]:
            label = f"{claim.character_name}: {spell_name}"[:100]
            description = f"{group_label} CD"[:100]
            select_options.append(
                discord.SelectOption(
                    label=label,
                    value=f"{claim.character_key}|{spell_id}",
                    description=description,
                )
            )
        super().__init__(
            placeholder="Cooldown auswählen",
            min_values=1,
            max_values=1,
            options=select_options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        character_key, spell_id = self.values[0].split("|", 1)
        status, cooldown = await self.parent_view.cog.log_cooldown(
            interaction.user.id, character_key, spell_id
        )
        if status != "ok" or cooldown is None:
            error_messages = {
                "not_owner": "Dieser Char gehört nicht dir.",
                "unknown_spell": "Unbekannter Cooldown-Spell.",
                "recipe_missing": (
                    "Dieser Char hat das Rezept nicht als gelernt eingetragen."
                ),
            }
            await interaction.response.edit_message(
                content=error_messages.get(status, "Speichern fehlgeschlagen."),
                view=None,
            )
            return
        ready_label = self.parent_view.cog._format_cooldown_ready_label(
            cooldown.ready_at
        )
        await interaction.response.edit_message(
            content=(
                f"✅ **{cooldown.character_name}** hat "
                f"**{cooldown.last_spell_name}** eingesetzt. "
                f"Wieder verfügbar {ready_label}."
            ),
            view=None,
        )


_PANEL_CHANNEL_OVERVIEW = (
    "**WoW Channels im Überblick**\n"
    "**#wow-info** — Infos & dieses Panel\n"
    "**#wow-general** — Allgemeiner WoW-Chat\n"
    "**#wow-dungeons** — Dungeon- & Raid-Runs (Raid Helper: `/create`)\n"
    "**#wow-classic-news** — Aktuelle News zu WoW Classic\n"
    "**#wow-content** — Streams, Videos & Clips\n"
    "**#wow-classes** — Klassen, Builds, Talente, Spielweise\n"
    "**#wow-welcome** — Neu im WoW-Bereich? Hier starten!"
)
PANEL_HUB_TEXT = (
    "## 🪷 Black Lotus WoW-Hub\n"
    "Hier verbindest du deine Chars, pflegst Berufe, loggst Cooldowns und "
    "findest Crafter in der Gilde. Wähle einen Bereich aus."
)
PANEL_HELP_TEXT = (
    "**Kurzanleitung**\n\n"
    "**👤 Deine Chars** — verbinde Black-Lotus-Charaktere mit deinem "
    "Discord-Account, pflege Berufe & Spezialrezepte, schau dir aktive "
    "Cooldowns an und gib Claims frei.\n\n"
    "**🔎 In der Gilde suchen** — finde, wer ein bestimmtes Item craften "
    "kann, oder schlag einen Char nach (Owner, Berufe, Status).\n\n"
    "**⏳ Cooldown loggen** — wenn du als Alchemist eine Transmute oder "
    "als Schneider Mondstoff machst, trag das hier über den Hub-Button ein. "
    "Der Bot erinnert im täglichen Digest, sobald sie wieder bereit sind.\n\n"
    "**Daily Digest** — jeden Morgen um **09:00 Berlin** postet der Bot "
    "Aufstiege, Tode, neue Crafts, Berufsskill-Meilensteine und "
    "bereitstehende Cooldowns. Geclaimte Chars werden gepingt.\n\n"
    "**🏆 Champion-System** — serverweites Punkte-System. Punkte gibt es "
    "automatisch für WoW-Aktivitäten (Chars claimen, Levelaufstiege, "
    "Berufs-Meilensteine, Rezepte). Commands: `/champion score` · "
    "`/champion rank` · `/champion leaderboard` · `/champion myhistory`\n\n"
    "Power-User: alle Funktionen gibt's auch als `/wow ...` Slash-Command.\n\n"
    "──────────────────────\n" + _PANEL_CHANNEL_OVERVIEW
)


def _add_dismiss_button(view: discord.ui.View) -> None:
    """Adds a ✖ Schließen button that deletes the ephemeral message."""
    btn = discord.ui.Button(label="✖ Schließen", style=discord.ButtonStyle.secondary)

    async def _close(interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

    btn.callback = _close
    view.add_item(btn)


class _PanelTextView(discord.ui.View):
    """Minimal view for ephemeral text-only panel responses."""

    def __init__(self) -> None:
        super().__init__(timeout=300)
        _add_dismiss_button(self)


class WoWPanelLayoutView(discord.ui.LayoutView):
    """Components-V2 hub for the WoW cog.

    Layout: a single ``Container`` with a header ``TextDisplay`` followed
    by ``Section`` blocks — one per top-level concern. Each section has an
    accessory button that opens a classic-V1 sub-flow (claim select,
    char-detail view, cooldown picker, etc.). All sub-flows are ephemeral
    so the public hub message stays stable.

    Persistence: the LayoutView is registered via ``bot.add_view`` at
    cog-load so buttons survive bot restarts. The hub message itself is
    re-issued automatically on startup via ``_auto_publish_panel``.
    """

    def __init__(self, cog: WoWCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

        chars_btn = discord.ui.Button(
            label="Öffnen",
            style=discord.ButtonStyle.primary,
            custom_id="wow_panel_v2:chars",
        )
        chars_btn.callback = self._open_my_chars

        search_btn = discord.ui.Button(
            label="Suchen",
            style=discord.ButtonStyle.secondary,
            custom_id="wow_panel_v2:search",
        )
        search_btn.callback = self._open_search

        gbank_btn = discord.ui.Button(
            label="Anfragen",
            style=discord.ButtonStyle.secondary,
            custom_id="wow_panel_v2:gbank",
        )
        gbank_btn.callback = self._open_gbank_request

        cooldown_btn = discord.ui.Button(
            label="Loggen",
            style=discord.ButtonStyle.secondary,
            custom_id="wow_panel_v2:cooldown",
        )
        cooldown_btn.callback = self._open_cooldown_log

        help_btn = discord.ui.Button(
            label="Anzeigen",
            style=discord.ButtonStyle.secondary,
            custom_id="wow_panel_v2:help",
        )
        help_btn.callback = self._open_help

        champion_btn = discord.ui.Button(
            label="Anzeigen",
            style=discord.ButtonStyle.secondary,
            custom_id="wow_panel_v2:champion",
        )
        champion_btn.callback = self._open_champion

        container = discord.ui.Container(
            discord.ui.TextDisplay(PANEL_HUB_TEXT),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(
                    "### 👤 Deine Chars\n"
                    "Claimen, Berufe & Rezepte pflegen, Cooldowns ansehen, "
                    "Claim freigeben."
                ),
                accessory=chars_btn,
            ),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(
                    "### 🔎 In der Gilde suchen\n"
                    "Wer kann was craften? Wer steckt hinter dem Char?"
                ),
                accessory=search_btn,
            ),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(
                    "### 🏦 Gildenbank-Anfrage\n"
                    "Etwas aus der Gildenbank gebraucht? Anfrage stellen — "
                    "der Verwalter des Bank-Chars bekommt eine DM."
                ),
                accessory=gbank_btn,
            ),
            discord.ui.Separator(),
            discord.ui.TextDisplay(
                "### 📅 Event erstellen\n"
                "Erstelle ein Raid- oder Dungeon-Event mit "
                "</create:885023455739777079>. Du bekommst danach eine "
                "private Nachricht von Raid-Helper mit den weiteren Schritten."
            ),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(
                    "### ⏳ Cooldown loggen\n"
                    "Transmute oder Mondstoff gemacht? Hier eintragen, "
                    "Bot meldet sich wenn wieder bereit."
                ),
                accessory=cooldown_btn,
            ),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(
                    "### ❓ Hilfe & Übersicht\n"
                    "Kanal-Übersicht und Bot-Kurzanleitung."
                ),
                accessory=help_btn,
            ),
            discord.ui.Separator(),
            discord.ui.Section(
                discord.ui.TextDisplay(
                    "### 🏆 Mein Champion-Rang\n"
                    "Dein Punktestand & Rang im serverweiten Champion-System."
                ),
                accessory=champion_btn,
            ),
        )
        self.add_item(container)

    async def _open_my_chars(self, interaction: discord.Interaction) -> None:
        view = PanelMyCharsView(self.cog, interaction.user.id)
        await view.send(interaction)

    async def _open_search(self, interaction: discord.Interaction) -> None:
        view = PanelSearchSubView(self.cog)
        await interaction.response.send_message(
            "Was suchst du?", view=view, ephemeral=True
        )

    async def _open_gbank_request(self, interaction: discord.Interaction) -> None:
        claims = await self.cog.data.claims_for_user(interaction.user.id)
        if not claims:
            await interaction.response.send_message(
                "Du musst zuerst einen Char claimen, bevor du eine "
                "Gildenbank-Anfrage stellen kannst. Nutze **Deine Chars → "
                "Neuen Char claimen**.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(GBankRequestModal(self.cog))

    async def _open_cooldown_log(self, interaction: discord.Interaction) -> None:
        eligible = await self.cog.cooldown_eligible_options(interaction.user.id)
        if not eligible:
            await interaction.response.send_message(
                "Keiner deiner Chars hat ein Rezept mit Cooldown gelernt. "
                "Trag das passende Rezept zuerst über **Deine Chars → Rezepte "
                "pflegen** ein.",
                ephemeral=True,
            )
            return
        view = PanelCooldownStartView(self.cog, interaction.user.id, eligible)
        await interaction.response.send_message(
            "Welchen Cooldown willst du eintragen?",
            view=view,
            ephemeral=True,
        )

    async def _open_help(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            PANEL_HELP_TEXT, view=_PanelTextView(), ephemeral=True
        )

    async def _open_champion(self, interaction: discord.Interaction) -> None:
        champion = interaction.client.get_cog("ChampionCog")
        if champion is None or not hasattr(champion, "data"):
            await interaction.response.send_message(
                "Champion-System nicht verfügbar.", ephemeral=True
            )
            return
        user_id_str = str(interaction.user.id)
        total = await champion.data.get_total(user_id_str)
        rank_result = await champion.data.get_rank(user_id_str)
        role = champion.get_current_role(total)

        if total == 0:
            text = (
                "**🏆 Champion-Status**\n\n"
                "Du hast noch keine Punkte gesammelt.\n\n"
                "Punkte gibt es automatisch für WoW-Aktivitäten: Chars claimen, "
                "Levelaufstiege, Berufs-Meilensteine, Spezialrezepte und mehr."
            )
        else:
            role_text = f"**{role.name}**" if role else "Champion"
            rank_text = f"Rang **#{rank_result[0]}**" if rank_result else "kein Rang"
            text = (
                f"**🏆 Champion-Status**\n\n"
                f"Rolle: {role_text}\n"
                f"Punkte: **{total}**  ·  {rank_text}\n\n"
                f"`/champion score` · `/champion rank`\n"
                f"`/champion leaderboard` · `/champion myhistory`"
            )
        await interaction.response.send_message(
            text, view=_PanelTextView(), ephemeral=True
        )


class PanelSearchSubView(discord.ui.View):
    """Sub-menu for the 🔎 Search section: crafter lookup or char-whois."""

    def __init__(self, cog: WoWCog) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        _add_dismiss_button(self)

    @discord.ui.button(label="Crafter suchen", style=discord.ButtonStyle.primary)
    async def crafter(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(PanelCraftingSearchModal(self.cog))

    @discord.ui.button(label="Char nachschlagen", style=discord.ButtonStyle.secondary)
    async def whois(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(PanelWhoisModal(self.cog))


class PanelWhoisModal(discord.ui.Modal):
    """Free-text wrapper around ``build_whois_view`` — same payload as
    ``/wow whois`` but reachable from the panel hub."""

    def __init__(self, cog: WoWCog) -> None:
        super().__init__(title="Char nachschlagen")
        self.cog = cog
        self.query = discord.ui.TextInput(
            label="Charaktername",
            placeholder="z. B. Voidok",
            min_length=2,
            max_length=32,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        name = str(self.query.value).strip()
        view = await self.cog.build_whois_view(name, interaction.user.id)
        if view is None:
            await interaction.response.send_message(
                f"**{name}** ist nicht im aktuellen Roster.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(view=view, ephemeral=True)


class _WhoisLayoutView(discord.ui.LayoutView):
    """Components-V2 profile card for a roster char.

    Layout: a single ``Container`` with title, info, professions, and
    (if claimed) twin links. The twin buttons swap the view in-place
    via ``edit_message`` so the user navigates without spawning more
    ephemerals.
    """

    def __init__(
        self,
        cog: "WoWCog",
        member: RosterMember,
        claim: "CharacterClaim | None",
        gear,
        professions: list[CharacterProfession],
        twins: list["CharacterClaim"],
        viewer_id: int,
        viewer_is_owner: bool,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.viewer_id = viewer_id
        self._member_key = member.character_key

        emoji_name = CLASS_EMOJI_NAMES.get(member.class_id, "")
        class_emoji = cog.bot.data.get("emojis", {}).get(emoji_name, "")
        class_name = CLASS_NAMES_DE.get(member.class_id) or "Klasse?"
        race_name = RACE_NAMES_DE.get(member.race_id) or ""
        title_line = (
            f"## {class_emoji} **{member.name}** — "
            f"Level {member.level} {race_name} {class_name}"
        ).strip()

        owner_str = f"<@{claim.discord_user_id}>" if claim else "_Nicht geclaimed_"
        status_str = "🕯️ Tot (Geist)" if member.is_ghost else "🟢 Lebt"
        ilvl_str = cog._format_item_level(gear.average_item_level) if gear else "—"
        info_line = (
            f"**Owner:** {owner_str}  ·  **Status:** {status_str}  ·  "
            f"**Ø iLvl:** {ilvl_str}"
        )

        items: list[discord.ui.Item] = [
            discord.ui.TextDisplay(title_line),
            discord.ui.Separator(),
            discord.ui.TextDisplay(info_line),
        ]

        if professions:
            berufe_text = "**Berufe:**\n" + cog.format_profession_slots_short(
                professions
            )
            items.append(discord.ui.Separator())
            if viewer_is_owner:
                pflegen_btn = discord.ui.Button(
                    label="🛠️ Berufe pflegen",
                    style=discord.ButtonStyle.primary,
                )
                pflegen_btn.callback = self._open_professions
                items.append(
                    discord.ui.Section(
                        discord.ui.TextDisplay(berufe_text),
                        accessory=pflegen_btn,
                    )
                )
            else:
                items.append(discord.ui.TextDisplay(berufe_text))

        if twins:
            items.append(discord.ui.Separator())
            owner_mention = f"<@{claim.discord_user_id}>"
            twin_header = f"**Andere Chars von {owner_mention}:**"
            if len(twins) > 5:
                twin_header += f"  _(5 von {len(twins)})_"
            items.append(discord.ui.TextDisplay(twin_header))

        self.add_item(discord.ui.Container(*items))

        # V2 LayoutView only accepts layout-type items at the top level
        # (ActionRow, Section, Container, TextDisplay, …). Plain Buttons
        # must be wrapped in an ActionRow.
        if twins:
            twin_row = discord.ui.ActionRow()
            for twin in twins[:5]:
                twin_btn = discord.ui.Button(
                    label=twin.character_name[:80],
                    style=discord.ButtonStyle.secondary,
                )
                twin_btn.callback = self._make_twin_callback(twin.character_name)
                twin_row.add_item(twin_btn)
            self.add_item(twin_row)

        dismiss_row = discord.ui.ActionRow()
        close_btn = discord.ui.Button(
            label="✖ Schließen", style=discord.ButtonStyle.secondary
        )

        async def _close(interaction: discord.Interaction) -> None:
            await interaction.response.defer()
            try:
                await interaction.delete_original_response()
            except discord.NotFound:
                pass

        close_btn.callback = _close
        dismiss_row.add_item(close_btn)
        self.add_item(dismiss_row)

    def _make_twin_callback(self, char_name: str):
        async def cb(interaction: discord.Interaction) -> None:
            new_view = await self.cog.build_whois_view(char_name, self.viewer_id)
            if new_view is None:
                # V2 messages can't carry plain content via edit_message;
                # spawn a fresh ephemeral for the error.
                await interaction.response.send_message(
                    f"**{char_name}** ist nicht im aktuellen Roster.",
                    ephemeral=True,
                )
                return
            await interaction.response.edit_message(view=new_view)

        return cb

    async def _open_professions(self, interaction: discord.Interaction) -> None:
        # PanelMyCharsView is a V1 view with an embed; we can't edit the
        # whois LayoutView message to a V1 payload (Discord locks the V2
        # flag on the message). Open as a fresh ephemeral instead.
        view = PanelMyCharsView(self.cog, interaction.user.id)
        await view._load()
        for c in view.claims:
            if c.character_key == self._member_key:
                view.selected_claim = c
                break
        view._rebuild()
        embed = await view._build_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class GBankRequestModal(discord.ui.Modal):
    """Step 1 of a guild-bank request: free-text 'what do you need?'."""

    def __init__(self, cog: WoWCog) -> None:
        super().__init__(title="Gildenbank-Anfrage")
        self.cog = cog
        self.request = discord.ui.TextInput(
            label="Was wird angefragt?",
            placeholder="z. B. 20x Runenstoff, Mondstoff, ...",
            style=discord.TextStyle.paragraph,
            min_length=2,
            max_length=300,
        )
        self.add_item(self.request)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bank_chars = await self.cog.data.list_bank_characters()
        if not bank_chars:
            await interaction.response.send_message(
                "Aktuell sind keine Gildenbank-Chars eingetragen. Bitte wende "
                "dich an einen Mod.",
                ephemeral=True,
            )
            return
        view = GBankBankCharSelectView(
            self.cog,
            interaction.user.id,
            str(self.request.value).strip(),
            bank_chars,
        )
        await interaction.response.send_message(
            "Auf welchem Bank-Char liegen die Items?",
            view=view,
            ephemeral=True,
        )


class GBankBankCharSelectView(discord.ui.View):
    """Step 2: pick the bank char that holds the requested items."""

    def __init__(
        self,
        cog: WoWCog,
        requester_id: int,
        request_text: str,
        bank_chars: list["BankCharacter"],
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.requester_id = requester_id
        self.request_text = request_text
        self.bank_chars = bank_chars
        self.add_item(GBankBankCharSelect(self))
        _add_dismiss_button(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class GBankBankCharSelect(discord.ui.Select):
    def __init__(self, parent: GBankBankCharSelectView) -> None:
        self.parent_view = parent
        options = [
            discord.SelectOption(
                label=bank.character_name[:100], value=bank.character_key
            )
            for bank in parent.bank_chars[:25]
        ]
        super().__init__(
            placeholder="Bank-Char auswählen",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        bank_key = self.values[0]
        bank_name = next(
            (
                bank.character_name
                for bank in self.parent_view.bank_chars
                if bank.character_key == bank_key
            ),
            bank_key,
        )
        claims = await self.parent_view.cog.data.claims_for_user(
            self.parent_view.requester_id
        )
        if len(claims) == 1:
            # Respond first (3s interaction window), then do the slow DM work.
            await interaction.response.edit_message(
                content="✅ Anfrage gesendet.", view=None
            )
            await self.parent_view.cog.submit_gbank_request(
                interaction.user,
                claims[0].character_name,
                bank_key,
                bank_name,
                self.parent_view.request_text,
            )
            return
        view = GBankOwnCharSelectView(
            self.parent_view.cog,
            self.parent_view.requester_id,
            self.parent_view.request_text,
            bank_key,
            bank_name,
            claims,
        )
        await interaction.response.edit_message(
            content="Für welchen deiner Chars ist die Anfrage?", view=view
        )


class GBankOwnCharSelectView(discord.ui.View):
    """Step 3 (only if requester has multiple claims): pick own char."""

    def __init__(
        self,
        cog: WoWCog,
        requester_id: int,
        request_text: str,
        bank_key: str,
        bank_name: str,
        claims: list[CharacterClaim],
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.requester_id = requester_id
        self.request_text = request_text
        self.bank_key = bank_key
        self.bank_name = bank_name
        self.claims = claims
        self.add_item(GBankOwnCharSelect(self))
        _add_dismiss_button(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message(
            "Diese Auswahl gehört nicht dir.", ephemeral=True
        )
        return False


class GBankOwnCharSelect(discord.ui.Select):
    def __init__(self, parent: GBankOwnCharSelectView) -> None:
        self.parent_view = parent
        options = [
            discord.SelectOption(
                label=claim.character_name[:100], value=claim.character_name
            )
            for claim in parent.claims[:25]
        ]
        super().__init__(
            placeholder="Dein Char",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        # Respond first (3s interaction window), then do the slow DM work.
        await interaction.response.edit_message(
            content="✅ Anfrage gesendet.", view=None
        )
        await self.parent_view.cog.submit_gbank_request(
            interaction.user,
            self.values[0],
            self.parent_view.bank_key,
            self.parent_view.bank_name,
            self.parent_view.request_text,
        )


class PanelMyCharsView(discord.ui.View):
    """Ephemeral overview-and-control panel for the user's claimed chars.

    Replaces the old "Meine Chars" plain-text response with an embed +
    char-select + inline action buttons. Consolidates what previously
    required five separate slash commands (``/wow claims mine``,
    ``/wow crafting mine``, ``/wow crafting learned``, ``/wow cooldowns
    mine``, ``/wow claim-release``) into one surface.
    """

    def __init__(self, cog: WoWCog, owner_user_id: int) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claims: list[CharacterClaim] = []
        self.selected_claim: CharacterClaim | None = None
        self._char_select: discord.ui.Select | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_user_id:
            return True
        await interaction.response.send_message(
            "Diese Ansicht gehört nicht dir.", ephemeral=True
        )
        return False

    async def _load(self) -> None:
        self.claims = await self.cog.data.claims_for_user(self.owner_user_id)
        if self.claims:
            if (
                self.selected_claim is None
                or self.selected_claim.character_key
                not in {c.character_key for c in self.claims}
            ):
                self.selected_claim = self.claims[0]
        else:
            self.selected_claim = None

    def _rebuild(self) -> None:
        """Recreate items based on the current claim list + selection."""
        self.clear_items()
        if len(self.claims) > 1:
            self._char_select = _MyCharsSelect(self, self.claims)
            self.add_item(self._char_select)
        if self.selected_claim is not None:
            self.add_item(_MyCharsActionButton(self, "profession", "🛠️ Berufe pflegen"))
            self.add_item(_MyCharsActionButton(self, "recipes", "📖 Rezepte pflegen"))
            self.add_item(
                _MyCharsActionButton(
                    self,
                    "release",
                    "🗑️ Claim freigeben",
                    style=discord.ButtonStyle.danger,
                )
            )
        self.add_item(
            _MyCharsActionButton(
                self,
                "claim_new",
                "➕ Neuen Char claimen",
                style=discord.ButtonStyle.success,
            )
        )
        _add_dismiss_button(self)

    async def _build_embed(self) -> discord.Embed:
        if not self.claims:
            return discord.Embed(
                title="Deine Chars",
                description=(
                    "Du hast noch keinen Black-Lotus-Char verbunden. "
                    "Klick **Neuen Char claimen** unten."
                ),
                color=0x9B59B6,
            )
        embed = discord.Embed(title="🪷 Deine Chars", color=0x2ECC71)
        for claim in self.claims:
            member = await self.cog.data.find_roster_member_by_name(
                claim.character_name
            )
            lines: list[str] = []
            if member is not None:
                race = RACE_NAMES_DE.get(member.race_id, "")
                klass = CLASS_NAMES_DE.get(member.class_id, "")
                lines.append(f"Level **{member.level}** {race} {klass}".strip())
                if member.is_ghost:
                    lines.append("🕯️ Tot (Geist)")
            lines.append(
                "✅ bestätigt"
                if claim.status == "verified"
                else "🕐 wartet auf Bestätigung"
            )
            gear = await self.cog.data.gear_snapshot(claim.character_key)
            if gear is not None:
                lines.append(
                    f"Ø iLvl **{self.cog._format_item_level(gear.average_item_level)}**"
                )
            professions = await self.cog.data.professions_for_character(
                claim.character_key
            )
            if professions:
                prof_lines = [
                    f"{self.cog._profession_name(p.profession_id)} **{p.skill_level}**"
                    for p in professions
                ]
                lines.append("Berufe: " + ", ".join(prof_lines))
            cooldowns = await self.cog.data.cooldowns_for_character(claim.character_key)
            if cooldowns:
                now = datetime.now(timezone.utc)
                cd_lines = []
                for cd in cooldowns:
                    try:
                        ready = datetime.fromisoformat(cd.ready_at)
                    except ValueError:
                        continue
                    if ready.tzinfo is None:
                        ready = ready.replace(tzinfo=timezone.utc)
                    if ready <= now:
                        cd_lines.append(f"⏳ {cd.last_spell_name}: **jetzt bereit**")
                    else:
                        delta = ready - now
                        hours = int(delta.total_seconds() // 3600)
                        minutes = int((delta.total_seconds() % 3600) // 60)
                        cd_lines.append(
                            f"⏳ {cd.last_spell_name}: ready in {hours}h {minutes:02d}m"
                        )
                lines.extend(cd_lines)
            marker = (
                "▶ "
                if (
                    self.selected_claim is not None
                    and claim.character_key == self.selected_claim.character_key
                    and len(self.claims) > 1
                )
                else ""
            )
            embed.add_field(
                name=f"{marker}{claim.character_name}",
                value="\n".join(lines) or "—",
                inline=False,
            )
        if self.selected_claim is not None and len(self.claims) > 1:
            embed.set_footer(
                text=f"Aktionen wirken auf {self.selected_claim.character_name}."
            )
        return embed

    async def send(self, interaction: discord.Interaction) -> None:
        await self._load()
        self._rebuild()
        embed = await self._build_embed()
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)

    async def refresh(self, interaction: discord.Interaction) -> None:
        await self._load()
        self._rebuild()
        embed = await self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class _MyCharsSelect(discord.ui.Select):
    def __init__(self, parent: PanelMyCharsView, claims: list[CharacterClaim]) -> None:
        self.parent_view = parent
        options = []
        for claim in claims[:25]:
            options.append(
                discord.SelectOption(
                    label=claim.character_name[:100],
                    value=claim.character_key,
                    default=(
                        parent.selected_claim is not None
                        and claim.character_key == parent.selected_claim.character_key
                    ),
                )
            )
        super().__init__(
            placeholder="Char auswählen",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        new_key = self.values[0]
        match = next(
            (c for c in self.parent_view.claims if c.character_key == new_key), None
        )
        if match is None:
            await self.parent_view.refresh(interaction)
            return
        self.parent_view.selected_claim = match
        await self.parent_view.refresh(interaction)


class _MyCharsActionButton(discord.ui.Button):
    def __init__(
        self,
        parent: PanelMyCharsView,
        action: str,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ) -> None:
        super().__init__(label=label, style=style)
        self.parent_view = parent
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        await getattr(self.parent_view.cog, f"_my_chars_{self.action}")(
            interaction, self.parent_view
        )


DISCORD_MESSAGE_LIMIT = 1900  # Below Discord's 2000-char baseline for safety.
CONTINUATION_SUFFIX = " *(Forts.)*"


def _pack_digest_sections_into_chunks(
    sections: list[tuple[str | None, list[str]]],
    limit: int = DISCORD_MESSAGE_LIMIT,
) -> list[str]:
    """Pack ordered digest sections into Discord-postable message chunks.

    Each section is ``(header, body_lines)``. ``header=None`` marks a
    headerless block (opener, closer) whose body is emitted verbatim.

    Rules:
    * A section is kept together in one chunk if it fits.
    * Multiple small sections may share a chunk, separated by a blank line.
    * A section larger than ``limit`` is split internally — every
      continuation chunk repeats the header with ``" *(Forts.)*"`` appended,
      so readers always know what section they're looking at.
    * The chunker never splits a single line.
    """

    def _section_lines(header: str | None, body: list[str]) -> list[str]:
        return ([header] if header is not None else []) + list(body)

    def _cost(lines: list[str]) -> int:
        # Each joined line contributes len(line) + 1 (the \n separator).
        return sum(len(line) + 1 for line in lines)

    # Pass 1: expand any oversized section into multiple fitting sub-sections,
    # marking continuations with the Forts. suffix.
    expanded: list[tuple[str | None, list[str]]] = []
    for header, body in sections:
        if _cost(_section_lines(header, body)) <= limit:
            expanded.append((header, list(body)))
            continue
        if header is None:
            # Headerless block — break body into runs that each fit.
            current_body: list[str] = []
            current_size = 0
            for line in body:
                line_cost = len(line) + 1
                if current_body and current_size + line_cost > limit:
                    expanded.append((None, current_body))
                    current_body = []
                    current_size = 0
                current_body.append(line)
                current_size += line_cost
            if current_body:
                expanded.append((None, current_body))
            continue
        cont_header = f"{header}{CONTINUATION_SUFFIX}"
        first_part = True
        current_body = []
        current_size = len(header) + 1
        for line in body:
            line_cost = len(line) + 1
            if current_body and current_size + line_cost > limit:
                expanded.append((header if first_part else cont_header, current_body))
                first_part = False
                current_body = []
                current_size = len(cont_header) + 1
            current_body.append(line)
            current_size += line_cost
        if current_body:
            expanded.append((header if first_part else cont_header, current_body))

    # Pass 2: pack expanded sections into chunks, separating with a blank line.
    chunks: list[str] = []
    current_lines: list[str] = []
    current_size = 0
    for header, body in expanded:
        section_lines = _section_lines(header, body)
        prefix = [""] if current_lines else []
        added_cost = _cost(prefix + section_lines)
        if current_size + added_cost <= limit:
            current_lines.extend(prefix + section_lines)
            current_size += added_cost
        else:
            if current_lines:
                chunks.append("\n".join(current_lines))
            current_lines = list(section_lines)
            current_size = _cost(section_lines)
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks


def _format_panel_claim_result(result: ClaimResult, requested_name: str) -> str:
    if result.reason == "not_found":
        return (
            f"**{requested_name}** wurde im aktuellen Black-Lotus-Roster "
            "nicht gefunden. Stimmt die Schreibweise?"
        )
    if result.claim is None:
        return "Der Charakter konnte gerade nicht verbunden werden. Versuch es gleich nochmal."
    if result.reason == "taken":
        return (
            f"**{result.claim.character_name}** ist bereits mit einem "
            "anderen Discord-Account verbunden."
        )
    if result.reason == "already_own":
        status = (
            "bestätigt ✅"
            if result.claim.status == "verified"
            else "wartet auf Bestätigung 🕐"
        )
        return f"**{result.claim.character_name}** hast du bereits verbunden — Status: *{status}*"
    warning = (
        "" if result.review_posted else "\nOffi-Review konnte nicht gepostet werden."
    )
    return f"**{result.claim.character_name}** wurde verbunden und wartet auf Bestätigung durch einen Moderator. 🪷{warning}"


def _format_panel_profession_result(cog: WoWCog, result: CraftingProfileResult) -> str:
    if result.reason == "unknown_profession":
        return "Dieser Beruf ist unbekannt."
    if result.reason == "not_claimed":
        return "Dieser Charakter ist nicht verbunden."
    if result.reason == "forbidden":
        return "Du darfst diesen Charakter nicht bearbeiten."
    if result.reason == "invalid_skill":
        return "Skill muss zwischen 1 und 300 liegen."
    if result.reason == "primary_limit":
        return "Dieser Charakter hat bereits zwei Hauptberufe gepflegt."
    return f"Gespeichert: {cog.format_profession(result.profession)}"


class ClaimReviewView(discord.ui.View):
    def __init__(self, cog: WoWCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    async def _ensure_mod(self, interaction: discord.Interaction) -> bool:
        permissions = getattr(interaction.user, "guild_permissions", None)
        if permissions and permissions.manage_guild:
            return True
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung für diese Claim-Prüfung.",
            ephemeral=True,
        )
        return False

    async def _claim_for_message(
        self, interaction: discord.Interaction
    ) -> CharacterClaim | None:
        message = interaction.message
        if message is None:
            return None
        return await self.cog.data.get_claim_by_review_message(message.id)

    @discord.ui.button(
        label="Bestätigen",
        style=discord.ButtonStyle.success,
        custom_id="wow_claim_review:verify",
    )
    async def verify(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        if not await self._ensure_mod(interaction):
            return
        claim = await self._claim_for_message(interaction)
        if claim is None:
            await interaction.response.send_message(
                "❌ Dieser Claim ist nicht mehr aktiv.", ephemeral=True
            )
            return
        await self.cog.data.verify_claim(claim.character_key, interaction.user.id)
        await self.cog.update_claim_review_message(interaction, claim, "verified")

    @discord.ui.button(
        label="Ablehnen",
        style=discord.ButtonStyle.danger,
        custom_id="wow_claim_review:reject",
    )
    async def reject(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        if not await self._ensure_mod(interaction):
            return
        claim = await self._claim_for_message(interaction)
        if claim is None:
            await interaction.response.send_message(
                "❌ Dieser Claim ist nicht mehr aktiv.", ephemeral=True
            )
            return
        await self.cog.data.remove_claim(claim.character_key)
        await self.cog.update_claim_review_message(interaction, claim, "rejected")


def _norm(value: str) -> str:
    return " ".join(str(value).casefold().split())
