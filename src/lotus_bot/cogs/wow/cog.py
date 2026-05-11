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
    CharacterKnownRecipe,
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
            self.bot.add_view(WoWPanelView(self))

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

    async def publish_panel(self, channel: discord.TextChannel) -> PanelPublishResult:
        content = self.format_panel_content()
        view = WoWPanelView(self)
        message_id_value = await self.data.get_setting("panel_message_id")
        if message_id_value:
            try:
                message = await channel.fetch_message(int(message_id_value))
                await message.edit(content=content, view=view)
                await self.data.set_setting("panel_channel_id", str(channel.id))
                return PanelPublishResult(channel.id, message.id, created=False)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.info("[WoWCog] Existing WoW panel message not editable.")
            except AttributeError:
                logger.info("[WoWCog] Channel does not support fetching panel message.")

        message = await channel.send(content, view=view)
        await self.data.set_setting("panel_channel_id", str(channel.id))
        await self.data.set_setting("panel_message_id", str(message.id))
        return PanelPublishResult(channel.id, message.id, created=True)

    def format_panel_content(self) -> str:
        return "\n".join(
            [
                "**Black Lotus WoW-Hub**",
                "",
                (
                    "Hier kannst du deine WoW-Charaktere verbinden, Berufe pflegen "
                    "und Crafter in der Gilde finden."
                ),
                "",
                "**Char claimen** verbindet einen Black-Lotus-Char mit deinem Discord-User.",
                "**Berufe pflegen** speichert Beruf, Skill und optional Spezialisierung.",
                "**Rezepte pflegen** speichert gelernte Spezialrezepte.",
                "**Crafter suchen** zeigt, wer ein Item herstellen kann.",
            ]
        )

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

    def _spell_for_recipe(self, recipe: dict) -> dict:
        return self._get_static_record("spells", recipe.get("spell_id"))

    def _item_for_recipe(self, recipe: dict) -> dict:
        return self._get_static_record("items", recipe.get("creates_item_id"))

    def _recipe_name(self, recipe: dict) -> str:
        spell = self._spell_for_recipe(recipe)
        item = self._item_for_recipe(recipe)
        return (
            self._localized_text(item.get("name"))
            or self._localized_text(spell.get("name"))
            or str(recipe.get("id") or recipe.get("spell_id") or "")
        )

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
        valid_spell_ids = {
            recipe.get("spell_id")
            for recipe in self._wow_records("profession_recipes")
            if recipe.get("profession_id") == profession_id
            and recipe.get("learned_from") != "trainer"
            and recipe.get("hardcore_valid")
        }
        accepted = [spell_id for spell_id in spell_ids if spell_id in valid_spell_ids]
        return await self.data.add_known_recipes(
            claim.character_key, profession_id, accepted
        )

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
                self._localized_text(self._spell_for_recipe(static).get("name"), "de")
                if static
                else "",
                self._localized_text(self._spell_for_recipe(static).get("name"), "en")
                if static
                else "",
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
            return "Dieses Item wurde in den WoW-Daten nicht gefunden."
        if result.status == "ambiguous_item":
            names = [
                f"- {self._localized_text(item.get('name'))}"
                for item in result.candidates or []
            ]
            return "Mehrere Items gefunden. Bitte genauer suchen:\n" + "\n".join(names)
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
    ) -> None:
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claim = claim
        self.profiles = profiles
        self.search = search
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
    ) -> None:
        super().__init__(timeout=300)
        self.owner_user_id = owner_user_id
        self.add_item(
            CraftingProfessionSelect(cog, owner_user_id, claim, profiles, search)
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
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claim = claim
        self.profile = profile
        self.recipes = recipes
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
        label = self.cog._recipe_name(recipe)
        return label[:100] or str(recipe.get("spell_id"))[:100]

    def option_description(self, recipe: dict) -> str:
        skill = int(recipe.get("required_skill") or 0)
        spell = self.cog._spell_for_recipe(recipe)
        spell_name = self.cog._localized_text(spell.get("name"))
        text = f"Skill {skill}"
        if spell_name and spell_name != self.option_label(recipe):
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
            view = PanelProfessionSelectView(
                self.parent_view.cog, interaction.user.id, claim
            )
            await interaction.response.edit_message(
                content=(
                    f"Welchen Beruf möchtest du für "
                    f"**{claim.character_name}** pflegen?"
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
        super().__init__(
            placeholder="Beruf auswählen",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=name[:100], value=value)
                for name, value in parent.cog.profession_choices("")
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
    def __init__(self, cog: WoWCog, owner_user_id: int, claim: CharacterClaim) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_user_id = owner_user_id
        self.claim = claim
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
        await interaction.response.send_modal(
            PanelRecipeSearchModal(
                self.parent_view.cog,
                self.parent_view.claim,
                self.values[0],
            )
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


class PanelRecipeSearchModal(discord.ui.Modal):
    def __init__(self, cog: WoWCog, claim: CharacterClaim, profession_id: str) -> None:
        super().__init__(title="Spezialrezepte suchen")
        self.cog = cog
        self.claim = claim
        self.profession_id = profession_id
        self.search = discord.ui.TextInput(
            label="Suchbegriff",
            placeholder="optional, z.B. Wut",
            required=False,
            max_length=80,
        )
        self.add_item(self.search)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        result = await self.cog.prepare_recipe_selection(
            interaction.user.id,
            self.claim.character_name,
            self.profession_id,
            str(self.search.value).strip() or None,
        )
        if result.status != "ok" or not result.recipes:
            await interaction.response.send_message(
                f"Für **{self.claim.character_name}** gibt es aktuell keine passenden offenen Spezialrezepte.",
                ephemeral=True,
            )
            return
        view = CraftingRecipeSelectionView(
            self.cog,
            interaction.user.id,
            result.claim,
            result.profile,
            result.recipes,
        )
        await interaction.response.send_message(
            view.content(),
            view=view,
            ephemeral=True,
        )


class PanelCraftingSearchModal(discord.ui.Modal):
    def __init__(self, cog: WoWCog) -> None:
        super().__init__(title="Crafter suchen")
        self.cog = cog
        self.item = discord.ui.TextInput(
            label="Item",
            placeholder="z.B. Wuttrank",
            min_length=2,
            max_length=80,
        )
        self.add_item(self.item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        result = await self.cog.search_crafting(str(self.item.value).strip())
        await interaction.response.send_message(
            self.cog.format_crafting_search_result(result),
            ephemeral=True,
        )


class WoWPanelView(discord.ui.View):
    def __init__(self, cog: WoWCog) -> None:
        super().__init__(timeout=None)
        self.cog = cog

    async def _send_claim_select(
        self, interaction: discord.Interaction, mode: str
    ) -> None:
        claims = await self.cog.data.claims_for_user(interaction.user.id)
        if not claims:
            await interaction.response.send_message(
                "Du hast noch keinen Charakter verbunden. Nutze zuerst **Char claimen**.",
                ephemeral=True,
            )
            return
        view = PanelOwnedCharacterSelectView(
            self.cog, interaction.user.id, claims, mode
        )
        await interaction.response.send_message(
            "Bitte wähle deinen Charakter aus.",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Char claimen",
        style=discord.ButtonStyle.primary,
        custom_id="wow_panel:claim",
    )
    async def claim(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(PanelCharacterSearchModal(self.cog))

    @discord.ui.button(
        label="Meine Chars",
        style=discord.ButtonStyle.secondary,
        custom_id="wow_panel:my_chars",
    )
    async def my_chars(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        claims = await self.cog.data.claims_for_user(interaction.user.id)
        if not claims:
            await interaction.response.send_message(
                "Du hast noch keinen Charakter verbunden.", ephemeral=True
            )
            return
        lines = [
            f"- **{claim.character_name}** ({'bestätigt' if claim.status == 'verified' else 'ungeprüft'})"
            for claim in claims
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @discord.ui.button(
        label="Berufe pflegen",
        style=discord.ButtonStyle.secondary,
        custom_id="wow_panel:professions",
    )
    async def professions(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._send_claim_select(interaction, "profession")

    @discord.ui.button(
        label="Rezepte pflegen",
        style=discord.ButtonStyle.secondary,
        custom_id="wow_panel:recipes",
    )
    async def recipes(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await self._send_claim_select(interaction, "recipes")

    @discord.ui.button(
        label="Crafter suchen",
        style=discord.ButtonStyle.secondary,
        custom_id="wow_panel:crafting_search",
    )
    async def crafting_search(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(PanelCraftingSearchModal(self.cog))

    @discord.ui.button(
        label="Hilfe",
        style=discord.ButtonStyle.secondary,
        custom_id="wow_panel:help",
    )
    async def help(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            "\n".join(
                [
                    "**Kurz erklärt**",
                    "1. Verbinde zuerst deinen Char über **Char claimen**.",
                    "2. Pflege danach Berufe und Skill über **Berufe pflegen**.",
                    "3. Spezialrezepte ergänzt du über **Rezepte pflegen**.",
                    "4. Über **Crafter suchen** findest du passende Gildenmitglieder.",
                ]
            ),
            ephemeral=True,
        )


def _format_panel_claim_result(result: ClaimResult, requested_name: str) -> str:
    if result.reason == "not_found":
        return (
            f"**{requested_name}** wurde im aktuellen Black-Lotus-Roster "
            "nicht gefunden."
        )
    if result.claim is None:
        return "Der Charakter konnte nicht verbunden werden."
    if result.reason == "taken":
        return (
            f"**{result.claim.character_name}** ist bereits mit einem "
            "Discord-User verbunden."
        )
    if result.reason == "already_own":
        status = "bestätigt" if result.claim.status == "verified" else "ungeprüft"
        return (
            f"Du hast **{result.claim.character_name}** bereits verbunden ({status})."
        )
    warning = (
        "" if result.review_posted else "\nOffi-Review konnte nicht gepostet werden."
    )
    return (
        f"Gespeichert: **{result.claim.character_name}** ist jetzt mit dir "
        f"verbunden.{warning}"
    )


def _format_panel_profession_result(cog: WoWCog, result: CraftingProfileResult) -> str:
    if result.reason == "unknown_profession":
        return "Dieser Beruf ist unbekannt."
    if result.reason == "not_claimed":
        return "Dieser Charakter ist nicht verbunden."
    if result.reason == "forbidden":
        return "Du darfst diesen Charakter nicht bearbeiten."
    if result.reason == "invalid_skill":
        return "Skill muss zwischen 1 und 300 liegen."
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
