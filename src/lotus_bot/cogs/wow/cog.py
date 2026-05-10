from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

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
)
from .data import (
    CharacterClaim,
    CharacterProfession,
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
MILESTONE_LEVELS = {30, 40, 50, 60}

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
    "Schaut mal, was sich bei uns bewegt hat:",
    "Bei Black Lotus gibt es Neuigkeiten:",
    "Aus der Gilde gibt es frische Meldungen:",
    "Heute hat sich bei Black Lotus wieder etwas getan:",
    "Ein kurzer Blick ins Gildenleben:",
    "Unsere Hardcore-Reise geht weiter:",
    "Neue Bewegung bei Black Lotus:",
    "Aus Soulseeker gibt es Neues:",
    "Die Gilde war wieder fleißig:",
    "Hier kommt das aktuelle Black-Lotus-Update:",
]
DIGEST_CLOSERS = [
    "Wir gratulieren ganz herzlich!",
    "Stark gemacht, weiter so!",
    "Black Lotus gratuliert!",
    "Auf viele weitere sichere Level!",
    "Möge der nächste Pull gnädig sein.",
    "Sehr schön, wir feiern mit!",
    "Weiterhin sichere Wege da draußen!",
    "Das sieht nach Fortschritt aus.",
    "Wir freuen uns mit euch!",
    "Sauber, Black Lotus!",
]


@dataclass
class Milestone:
    member: RosterMember
    level: int


@dataclass
class DeathEvent:
    member: RosterMember
    confirmed: bool = True


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

    @property
    def public_count(self) -> int:
        return len(self.new_members) + len(self.milestones) + len(self.deaths)


@dataclass
class ScanResult:
    member_count: int
    milestones: list[Milestone]
    new_members: list[RosterMember] | None = None
    deaths: list[DeathEvent] | None = None
    officer_notes: list[OfficerNote] | None = None
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

    async def get_claim_review_channel_id(self) -> int:
        value = await self.data.get_setting("claim_review_channel_id")
        return int(value) if value else DEFAULT_CLAIM_REVIEW_CHANNEL_ID

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
        """Fetch the roster, detect activity, optionally post and persist it."""
        async with self._scan_lock:
            previous = await self.data.get_snapshot()
            current = await self.fetch_roster()
            activity = await self._detect_activity(previous, current)
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
                posted=posted,
            )

    async def _detect_activity(
        self,
        previous: dict[str, RosterMember],
        current: list[RosterMember],
    ) -> ActivityDiff:
        current_by_key = {member.character_key: member for member in current}
        new_members = [
            member for member in current if member.character_key not in previous
        ]
        milestones = await self._detect_milestones(previous, current)
        deaths = await self._detect_roster_deaths(previous, current)
        missing_deaths, officer_notes = await self._inspect_missing_members(
            previous, current_by_key
        )
        deaths.extend(missing_deaths)
        return ActivityDiff(
            new_members=new_members,
            milestones=milestones,
            deaths=deaths,
            officer_notes=officer_notes,
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
                deaths.append(DeathEvent(member))
        return deaths

    async def _inspect_missing_members(
        self,
        previous: dict[str, RosterMember],
        current_by_key: dict[str, RosterMember],
    ) -> tuple[list[DeathEvent], list[OfficerNote]]:
        deaths: list[DeathEvent] = []
        notes: list[OfficerNote] = []
        for member in previous.values():
            if member.character_key in current_by_key:
                continue
            if await self.data.death_exists(member.character_key):
                continue
            state = await self._profile_life_state(member)
            if state == "dead":
                deaths.append(DeathEvent(member, confirmed=True))
            elif state == "alive":
                notes.append(
                    OfficerNote(
                        member,
                        f"{member.name} ist nicht mehr Teil von {self.guild_name}.",
                    )
                )
            else:
                deaths.append(DeathEvent(member, confirmed=False))
        return deaths, notes

    async def _profile_life_state(self, member: RosterMember) -> str:
        try:
            profile = await fetch_character_profile(
                member.realm_slug,
                member.name,
                namespace=self.namespace,
                locale=self.locale,
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

        try:
            await channel.send(await self.format_activity_digest(activity))
        except discord.Forbidden:
            logger.warning(
                "[WoWCog] Missing access to announcement channel %s.",
                channel_id,
            )
            return 0
        except discord.HTTPException as exc:
            logger.warning(
                "[WoWCog] Could not post activity digest to channel %s: %s",
                channel_id,
                exc,
                exc_info=True,
            )
            return 0
        return 1

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
            posted += 1
        return posted

    async def _record_public_events(self, activity: ActivityDiff) -> None:
        for milestone in activity.milestones:
            await self.data.record_milestone(
                milestone.member.character_key, milestone.level
            )
        for death in activity.deaths:
            await self.data.record_death(death.member.character_key)

    def format_milestone(self, milestone: Milestone) -> str:
        return self._format_milestone_line(milestone, None)

    async def format_activity_digest(self, activity: ActivityDiff) -> str:
        lines = [random.choice(DIGEST_OPENERS), ""]
        for member in activity.new_members:
            lines.append(f"- {self._format_new_member_line(member)}")
        for milestone in activity.milestones:
            claim = await self.data.get_claim(milestone.member.character_key)
            lines.append(f"- {self._format_milestone_line(milestone, claim)}")
        for death in activity.deaths:
            lines.append(f"- {self._format_death_line(death)}")
        lines.extend(["", random.choice(DIGEST_CLOSERS)])
        return "\n".join(lines)

    def _format_new_member_line(self, member: RosterMember) -> str:
        return (
            "Wir begrüßen ganz herzlich den neuen Char "
            f"**{self._display_character(member)}** bei uns in der Gilde!"
        )

    def _format_milestone_line(
        self, milestone: Milestone, claim: CharacterClaim | None
    ) -> str:
        character = self._display_character(milestone.member)
        if claim:
            return (
                f"<@{claim.discord_user_id}> hat mit **{character}** "
                f"Level **{milestone.level}** erreicht."
            )
        return f"**{character}** ist auf Level **{milestone.level}** aufgestiegen."

    def _format_death_line(self, death: DeathEvent) -> str:
        character = self._display_character(death.member)
        level = death.member.level
        if not death.confirmed:
            return (
                f"**{character}** ist auf Level **{level}** aus dem Roster "
                "verschwunden und nicht mehr auffindbar. Wir gehen davon aus, "
                "dass die Hardcore-Reise geendet hat."
            )
        return (
            f"**{character}** ist auf Level **{level}** gestorben. "
            "Wir trinken einen Heiltrank auf den Mut."
        )

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
            f"<@{claim.discord_user_id}> hat gerade den Char "
            f"**{claim.character_name}** geclaimed."
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

    def _profession_name(self, profession_id: str) -> str:
        profession = self._get_static_record("professions", profession_id)
        return self._localized_text(profession.get("name")) or profession_id

    def _crafting_professions(self) -> list[dict]:
        return [
            profession
            for profession in self._wow_records("professions")
            if profession.get("id") != "first-aid"
        ]

    def _get_static_record(self, table: str, record_id: str | None) -> dict:
        if not record_id:
            return {}
        for record in self._wow_records(table):
            if record.get("id") == record_id:
                return record
        return {}

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
        profession = await self.data.set_character_profession(
            claim, profession_id, skill_level, specialization
        )
        return CraftingProfileResult(profession, claim=claim, reason="saved")

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

    async def search_crafting(self, item_name: str) -> CraftingSearchResult:
        matches = self._match_items(item_name)
        if not matches:
            return CraftingSearchResult("item_not_found")
        if len(matches) > 1:
            return CraftingSearchResult("ambiguous_item", candidates=matches[:5])

        item = matches[0]
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
        if not trainer_recipes:
            return CraftingSearchResult("manual_recipe", item=item, recipe=recipes[0])

        recipe = min(
            trainer_recipes,
            key=lambda record: int(record.get("required_skill") or 0),
        )
        profession_id = recipe.get("profession_id")
        required_skill = int(recipe.get("required_skill") or 1)
        crafters = await self.data.find_crafters(profession_id, required_skill)
        if not crafters:
            return CraftingSearchResult(
                "no_crafter",
                item=item,
                recipe=recipe,
                required_skill=required_skill,
                profession_id=profession_id,
                crafters=[],
            )
        return CraftingSearchResult(
            "ok",
            item=item,
            recipe=recipe,
            crafters=crafters,
            required_skill=required_skill,
            profession_id=profession_id,
        )

    def _match_items(self, item_name: str) -> list[dict]:
        needle = _norm(item_name)
        exact = []
        partial = []
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
        return exact or partial[:5]

    def format_profession(self, profile: CharacterProfession) -> str:
        specialization = (
            f" ({profile.specialization})" if profile.specialization else ""
        )
        return (
            f"**{profile.character_name}** - "
            f"{self._profession_name(profile.profession_id)} "
            f"{profile.skill_level}{specialization}"
        )

    def format_crafting_search_result(self, result: CraftingSearchResult) -> str:
        if result.status == "item_not_found":
            return "❌ Dieses Item wurde in den WoW-Daten nicht gefunden."
        if result.status == "ambiguous_item":
            names = [
                f"- {self._localized_text(item.get('name'))}"
                for item in result.candidates or []
            ]
            return "Mehrere Items gefunden. Bitte genauer suchen:\n" + "\n".join(names)
        item_name = self._localized_text((result.item or {}).get("name"))
        if result.status == "recipe_not_found":
            return f"❌ Für **{item_name}** wurde kein Crafting-Rezept gefunden."
        if result.status == "manual_recipe":
            return (
                f"ℹ️ **{item_name}** hat ein Rezept, aber es ist kein Trainerrezept. "
                "V1 kennt gefundene/gekaufte Rezepte noch nicht als gelernt."
            )
        profession_name = self._profession_name(result.profession_id or "")
        if result.status == "no_crafter":
            return (
                f"❌ **{item_name}** benötigt {profession_name} "
                f"{result.required_skill}. Kein geclaimter Crafter passt aktuell."
            )
        lines = [
            f"**{item_name}** kann vermutlich gecraftet werden von:",
            "",
        ]
        for crafter in result.crafters or []:
            specialization = (
                f" ({crafter.specialization})" if crafter.specialization else ""
            )
            lines.append(
                f"- <@{crafter.discord_user_id}> mit **{crafter.character_name}** "
                f"({profession_name} {crafter.skill_level}{specialization})"
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
        return {
            "guild": self.guild_name,
            "realm": self.realm_slug,
            "channel_id": channel_id,
            "officer_channel_id": await self.get_claim_review_channel_id(),
            "last_scan_at": await self.data.last_scan_at(),
            "member_count": await self.data.member_count(),
            "poll_interval": self.poll_interval,
        }

    def cog_unload(self) -> None:
        super().cog_unload()
        self.create_task(self.data.close())


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
