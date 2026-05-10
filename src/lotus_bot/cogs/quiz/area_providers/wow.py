import hashlib
import random
from typing import Any

from lotus_bot.log_setup import get_logger

from ..utils import create_permutations_list
from .base import DynamicQuestionProvider

logger = get_logger(__name__)


QUALITY_LABELS = {
    "de": {
        "poor": "Schlecht",
        "common": "Gewöhnlich",
        "uncommon": "Ungewöhnlich",
        "rare": "Selten",
        "epic": "Episch",
        "legendary": "Legendär",
    },
    "en": {
        "poor": "Poor",
        "common": "Common",
        "uncommon": "Uncommon",
        "rare": "Rare",
        "epic": "Epic",
        "legendary": "Legendary",
    },
}

ITEM_SUBCLASS_LABELS = {
    "de": {
        "dagger": "Dolch",
        "potion": "Trank",
        "miscellaneous": "Verschiedenes",
    },
    "en": {
        "dagger": "Dagger",
        "potion": "Potion",
        "miscellaneous": "Miscellaneous",
    },
}

LEARNED_FROM_LABELS = {
    "de": {"trainer": "Trainer", "recipe": "Rezept"},
    "en": {"trainer": "Trainer", "recipe": "Recipe"},
}

ZONE_TYPE_LABELS = {
    "de": {
        "city": "Stadt",
        "outdoor_zone": "Outdoor-Zone",
        "battleground": "Schlachtfeld",
        "dungeon": "Instanz",
        "raid": "Instanz",
    },
    "en": {
        "city": "City",
        "outdoor_zone": "Outdoor Zone",
        "battleground": "Battleground",
        "dungeon": "Instance",
        "raid": "Instance",
    },
}


class WoWQuestionProvider(DynamicQuestionProvider):
    question_generators = [
        "generate_race_faction",
        "generate_racial_trait_description",
        "generate_race_class_allowed",
        "generate_class_power_type",
        "generate_talent_tree",
        "generate_talent_class",
        "generate_talent_description",
        "generate_ability_class",
        "generate_ability_required_level",
        "generate_ability_description",
        "generate_zone_continent",
        "generate_zone_level_fit",
        "generate_zone_type",
        "generate_instance_level_fit",
        "generate_instance_players",
        "generate_instance_location",
        "generate_drop_instance",
        "generate_drop_source",
        "generate_item_subclass",
        "generate_item_required_level",
    ]

    def __init__(self, bot, language: str = "de"):
        self.bot = bot
        self.language = language
        self.data = bot.data.get("wow", {})
        self.templates = bot.data.get("quiz", {}).get("templates", {}).get("wow", {})
        self.indexes: dict[str, dict[str, dict[str, Any]]] = {}

    def _make_id(self, text: str) -> int:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return int(digest, 16)

    def _records(self, key: str) -> list[dict[str, Any]]:
        records = self.data.get(key, [])
        return records if isinstance(records, list) else []

    def _by_id(self, key: str) -> dict[str, dict[str, Any]]:
        if key not in self.indexes:
            self.indexes[key] = {
                str(record.get("id")): record
                for record in self._records(key)
                if record.get("id")
            }
        return self.indexes[key]

    def _get(self, key: str, record_id: str | None) -> dict[str, Any]:
        if not record_id:
            return {}
        return self._by_id(key).get(str(record_id), {})

    def _text(
        self,
        value: dict[str, str] | str | None,
        lang: str | None = None,
        *,
        require_lang: bool = False,
    ) -> str:
        if isinstance(value, str):
            return value
        if not value:
            return ""
        lang = lang or self.language
        if require_lang and lang not in value:
            return ""
        return value.get(lang) or value.get("de") or value.get("en") or ""

    def _answer_aliases(self, *values: Any) -> list[str]:
        aliases: list[str] = []
        for value in values:
            self._collect_aliases(value, aliases)
        return create_permutations_list(sorted(set(aliases)))

    def _collect_aliases(self, value: Any, aliases: list[str]) -> None:
        if isinstance(value, dict):
            for item in value.values():
                self._collect_aliases(item, aliases)
        elif isinstance(value, list):
            for item in value:
                self._collect_aliases(item, aliases)
        elif value is not None and value != "":
            aliases.append(str(value))

    def _template(self, name: str) -> str | None:
        return self.templates.get(self.language, {}).get(name)

    def _source_url(self, record: dict[str, Any]) -> str | None:
        urls = record.get("source_urls")
        if isinstance(urls, dict):
            return urls.get(self.language) or urls.get("de") or urls.get("en")
        return record.get("source_url")

    def _source_label(self, record: dict[str, Any]) -> str:
        name = self._text(record.get("name"))
        return f"Wowhead - {name}" if name else "Wowhead"

    def _question(
        self,
        pattern: str,
        record_id: str,
        *,
        category: str,
        answers: list[str],
        difficulty: str,
        contexts: list[str] | None = None,
        source: dict[str, Any] | None = None,
        **kwargs: str,
    ) -> dict[str, Any] | None:
        template = self._template(pattern)
        if not template or not answers or any(value == "" for value in kwargs.values()):
            return None
        question = {
            "frage": template.format(**kwargs),
            "antwort": self._answer_aliases(answers),
            "category": category,
            "difficulty": difficulty,
            "contexts": contexts or ["scheduled", "duel"],
            "id": self._make_id(f"wow:{pattern}:{self.language}:{record_id}"),
        }
        if source:
            source_url = self._source_url(source)
            if source_url:
                question["source_url"] = source_url
                question["source_label"] = self._source_label(source)
        return question

    def _spell_for(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._get("spells", record.get("spell_id"))

    def _class_for(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._get("classes", record.get("class_id"))

    def _race_for(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._get("races", record.get("race_id"))

    def _tree_for(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._get("talent_trees", record.get("tree_id"))

    def _item_for(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._get(
            "items", record.get("item_id") or record.get("creates_item_id")
        )

    def _instance_for(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._get("dungeons", record.get("instance_id"))

    def _profession_for(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._get("professions", record.get("profession_id"))

    def _hc_zones(self) -> list[dict[str, Any]]:
        return [zone for zone in self._records("zones") if zone.get("hardcore_enabled")]

    def _parse_level_range(self, value: str | None) -> tuple[int, int] | None:
        if not value:
            return None
        text = str(value).strip()
        if "-" in text:
            low, high = text.split("-", 1)
            if low.strip().isdigit() and high.strip().isdigit():
                return int(low), int(high)
            return None
        if text.isdigit():
            level = int(text)
            return level, level
        return None

    def _level_fit_payload(
        self, level_range: str | None
    ) -> tuple[str, list[str]] | None:
        parsed = self._parse_level_range(level_range)
        if not parsed:
            return None
        low, high = parsed
        fits = random.choice([True, False])
        if fits:
            level = low if low == high else random.randint(low, high)
            return str(level), ["Ja", "Yes"]
        level = max(1, low - 10) if low > 10 else high + 10
        return str(level), ["Nein", "No"]

    def _quiz_drops(self) -> list[dict[str, Any]]:
        drops = []
        for drop in self._records("instance_drops"):
            item = self._item_for(drop)
            if (
                drop.get("season") == "classic_era"
                and drop.get("mode") == "normal"
                and drop.get("include_in_hardcore_quiz")
                and item
                and not item.get("is_quest_item")
            ):
                drops.append(drop)
        return drops

    def generate(self, context: str = "scheduled"):
        questions = self.generate_all_types(context=context)
        if not questions:
            logger.warning("[WoWQuestionProvider] No valid question generated.")
            return None
        question = random.choice(questions)
        logger.info(f"[WoWQuestionProvider] Generated: {question['frage']}")
        return question

    def generate_race_faction(self):
        records = [race for race in self._records("races") if race.get("faction_id")]
        if not records:
            return None
        race = random.choice(records)
        faction = self._get("factions", race.get("faction_id"))
        return self._question(
            "race_faction",
            race["id"],
            category="Völker",
            answers=[self._text(faction.get("name"))],
            difficulty="easy",
            contexts=["duel"],
            source=race,
            race_name=self._text(race.get("name"), require_lang=True),
        )

    def generate_racial_trait_description(self):
        records = self._records("racial_traits")
        if not records:
            return None
        trait = random.choice(records)
        race = self._race_for(trait)
        spell = self._spell_for(trait)
        return self._question(
            "racial_trait_description",
            trait["id"],
            category="Völker",
            answers=[self._text(race.get("name"))],
            difficulty="medium",
            source=spell,
            description=self._text(spell.get("description"), require_lang=True),
        )

    def generate_racial_trait_translation(self):
        records = self._records("racial_traits")
        if not records:
            return None
        trait = random.choice(records)
        spell = self._spell_for(trait)
        source_lang = self.language
        target_lang = "en" if source_lang == "de" else "de"
        target_label = "Englisch" if target_lang == "en" else "German"
        return self._question(
            "racial_trait_translation",
            trait["id"],
            category="Völker",
            answers=[self._text(spell.get("name"), target_lang, require_lang=True)],
            difficulty="hard",
            source=spell,
            trait_name=self._text(spell.get("name"), source_lang, require_lang=True),
            target_language=target_label,
        )

    def generate_race_class_allowed(self):
        races = self._records("races")
        classes = self._records("classes")
        allowed = {
            (combo.get("race_id"), combo.get("class_id"))
            for combo in self._records("race_classes")
        }
        if not races or not classes or not allowed:
            return None
        all_pairs = [(race["id"], cls["id"]) for race in races for cls in classes]
        blocked = [pair for pair in all_pairs if pair not in allowed]
        pair = random.choice(list(allowed) + blocked)
        race = self._get("races", pair[0])
        cls = self._get("classes", pair[1])
        is_allowed = pair in allowed
        return self._question(
            "race_class_allowed",
            f"{pair[0]}:{pair[1]}",
            category="Klassen",
            answers=["Ja", "Yes"] if is_allowed else ["Nein", "No"],
            difficulty="easy",
            contexts=["duel"],
            source=race,
            race_name=self._text(race.get("name"), require_lang=True),
            class_name=self._text(cls.get("name"), require_lang=True),
        )

    def generate_class_power_type(self):
        records = [cls for cls in self._records("classes") if cls.get("power_type_id")]
        if not records:
            return None
        cls = random.choice(records)
        power = self._get("power_types", cls.get("power_type_id"))
        return self._question(
            "class_power_type",
            cls["id"],
            category="Klassen",
            answers=[self._text(power.get("name"))],
            difficulty="easy",
            contexts=["duel"],
            source=cls,
            class_name=self._text(cls.get("name"), require_lang=True),
        )

    def generate_talent_tree(self):
        records = [
            talent for talent in self._records("talents") if talent.get("tree_id")
        ]
        if not records:
            return None
        talent = random.choice(records)
        spell = self._spell_for(talent)
        tree = self._tree_for(talent)
        cls = self._class_for(talent)
        return self._question(
            "talent_tree",
            talent["id"],
            category="Talente",
            answers=[
                self._text(tree.get("name")),
                talent.get("answers", {}).get("tree"),
            ],
            difficulty="medium",
            source=spell,
            class_name=self._text(cls.get("name"), require_lang=True),
            talent_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_talent_class(self):
        records = self._records("talents")
        if not records:
            return None
        talent = random.choice(records)
        spell = self._spell_for(talent)
        cls = self._class_for(talent)
        return self._question(
            "talent_class",
            talent["id"],
            category="Talente",
            answers=[self._text(cls.get("name"))],
            difficulty="medium",
            source=spell,
            talent_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_talent_description(self):
        records = self._records("talents")
        if not records:
            return None
        talent = random.choice(records)
        spell = self._spell_for(talent)
        tree = self._tree_for(talent)
        cls = self._class_for(talent)
        return self._question(
            "talent_description",
            talent["id"],
            category="Talente",
            answers=[
                self._text(spell.get("name")),
                talent.get("answers", {}).get("name"),
            ],
            difficulty="medium",
            source=spell,
            description=self._text(spell.get("description"), require_lang=True),
            class_name=self._text(cls.get("name"), require_lang=True),
            tree_name=self._text(tree.get("name"), require_lang=True),
        )

    def generate_talent_rank(self):
        records = [talent for talent in self._records("talents") if talent.get("rank")]
        if not records:
            return None
        talent = random.choice(records)
        spell = self._spell_for(talent)
        tree = self._tree_for(talent)
        cls = self._class_for(talent)
        return self._question(
            "talent_rank",
            talent["id"],
            category="Talente",
            answers=[
                self._text(spell.get("name")),
                talent.get("answers", {}).get("name"),
            ],
            difficulty="hard",
            source=spell,
            class_name=self._text(cls.get("name"), require_lang=True),
            tree_name=self._text(tree.get("name"), require_lang=True),
            rank=str(talent["rank"]),
        )

    def generate_ability_class(self):
        records = self._records("abilities")
        if not records:
            return None
        ability = random.choice(records)
        spell = self._spell_for(ability)
        cls = self._class_for(ability)
        return self._question(
            "ability_class",
            ability["id"],
            category="Klassenfähigkeiten",
            answers=[
                self._text(cls.get("name")),
                ability.get("answers", {}).get("class"),
            ],
            difficulty="easy",
            contexts=["duel"],
            source=spell,
            ability_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_ability_required_level(self):
        records = [
            ability
            for ability in self._records("abilities")
            if self._spell_for(ability).get("required_level")
        ]
        if not records:
            return None
        ability = random.choice(records)
        spell = self._spell_for(ability)
        cls = self._class_for(ability)
        level = str(spell["required_level"])
        return self._question(
            "ability_required_level",
            ability["id"],
            category="Klassenfähigkeiten",
            answers=[level, f"Level {level}", f"Stufe {level}"],
            difficulty="medium",
            source=spell,
            class_name=self._text(cls.get("name"), require_lang=True),
            ability_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_ability_description(self):
        records = self._records("abilities")
        if not records:
            return None
        ability = random.choice(records)
        spell = self._spell_for(ability)
        cls = self._class_for(ability)
        return self._question(
            "ability_description",
            ability["id"],
            category="Klassenfähigkeiten",
            answers=[
                self._text(spell.get("name")),
                ability.get("answers", {}).get("name"),
            ],
            difficulty="medium",
            source=spell,
            description=self._text(spell.get("description"), require_lang=True),
            class_name=self._text(cls.get("name"), require_lang=True),
        )

    def generate_ability_cooldown(self):
        records = [
            ability
            for ability in self._records("abilities")
            if self._spell_for(ability).get("cooldown")
        ]
        if not records:
            return None
        ability = random.choice(records)
        spell = self._spell_for(ability)
        cls = self._class_for(ability)
        return self._question(
            "ability_cooldown",
            ability["id"],
            category="Klassenfähigkeiten",
            answers=[
                self._text(spell.get("name")),
                ability.get("answers", {}).get("name"),
            ],
            difficulty="hard",
            source=spell,
            class_name=self._text(cls.get("name"), require_lang=True),
            cooldown=self._text(spell.get("cooldown"), require_lang=True),
        )

    def generate_recipe_profession(self):
        recipes = self._records("profession_recipes")
        if not recipes:
            return None
        recipe = random.choice(recipes)
        spell = self._spell_for(recipe)
        profession = self._profession_for(recipe)
        return self._question(
            "recipe_profession",
            recipe["id"],
            category="Berufe",
            answers=[self._text(profession.get("name"))],
            difficulty="easy",
            source=spell,
            recipe_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_recipe_creates_item(self):
        recipes = self._records("profession_recipes")
        if not recipes:
            return None
        recipe = random.choice(recipes)
        spell = self._spell_for(recipe)
        item = self._get("items", recipe.get("creates_item_id"))
        return self._question(
            "recipe_creates_item",
            recipe["id"],
            category="Berufe",
            answers=[self._text(item.get("name"))],
            difficulty="medium",
            source=spell,
            recipe_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_recipe_required_skill(self):
        recipes = [
            recipe
            for recipe in self._records("profession_recipes")
            if recipe.get("required_skill")
        ]
        if not recipes:
            return None
        recipe = random.choice(recipes)
        spell = self._spell_for(recipe)
        skill = str(recipe["required_skill"])
        return self._question(
            "recipe_required_skill",
            recipe["id"],
            category="Berufe",
            answers=[skill, f"Skill {skill}"],
            difficulty="medium",
            source=spell,
            recipe_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_recipe_learned_from(self):
        recipes = [
            recipe
            for recipe in self._records("profession_recipes")
            if recipe.get("learned_from")
        ]
        if not recipes:
            return None
        recipe = random.choice(recipes)
        spell = self._spell_for(recipe)
        learned_from = recipe["learned_from"]
        return self._question(
            "recipe_learned_from",
            recipe["id"],
            category="Berufe",
            answers=[
                learned_from,
                LEARNED_FROM_LABELS["de"].get(learned_from, learned_from),
                LEARNED_FROM_LABELS["en"].get(learned_from, learned_from),
            ],
            difficulty="medium",
            source=spell,
            recipe_name=self._text(spell.get("name"), require_lang=True),
        )

    def generate_zone_continent(self):
        zones = [zone for zone in self._hc_zones() if zone.get("continent_id")]
        if not zones:
            return None
        zone = random.choice(zones)
        continent = self._get("continents", zone.get("continent_id"))
        return self._question(
            "zone_continent",
            zone["id"],
            category="Gebiete",
            answers=[self._text(continent.get("name"))],
            difficulty="medium",
            source=zone,
            zone_name=self._text(zone.get("name"), require_lang=True),
        )

    def generate_zone_territory(self):
        zones = [zone for zone in self._hc_zones() if zone.get("territory_id")]
        if not zones:
            return None
        zone = random.choice(zones)
        territory = self._get("factions", zone.get("territory_id"))
        return self._question(
            "zone_territory",
            zone["id"],
            category="Gebiete",
            answers=[self._text(territory.get("name"))],
            difficulty="easy",
            source=zone,
            zone_name=self._text(zone.get("name"), require_lang=True),
        )

    def generate_zone_level(self):
        zones = [zone for zone in self._hc_zones() if zone.get("level_range")]
        if not zones:
            return None
        zone = random.choice(zones)
        return self._question(
            "zone_level",
            zone["id"],
            category="Gebiete",
            answers=[zone.get("level_range")],
            difficulty="medium",
            source=zone,
            zone_name=self._text(zone.get("name"), require_lang=True),
        )

    def generate_zone_level_fit(self):
        zones = [zone for zone in self._hc_zones() if zone.get("level_range")]
        if not zones:
            return None
        zone = random.choice(zones)
        payload = self._level_fit_payload(zone.get("level_range"))
        if not payload:
            return None
        level, answers = payload
        return self._question(
            "zone_level_fit",
            zone["id"],
            category="Gebiete",
            answers=answers,
            difficulty="medium",
            source=zone,
            zone_name=self._text(zone.get("name"), require_lang=True),
            level=level,
        )

    def generate_zone_type(self):
        zones = [zone for zone in self._hc_zones() if zone.get("type")]
        if not zones:
            return None
        zone = random.choice(zones)
        zone_type = zone["type"]
        return self._question(
            "zone_type",
            zone["id"],
            category="Gebiete",
            answers=[
                zone_type,
                ZONE_TYPE_LABELS["de"].get(zone_type, zone_type),
                ZONE_TYPE_LABELS["en"].get(zone_type, zone_type),
            ],
            difficulty="medium",
            source=zone,
            zone_name=self._text(zone.get("name"), require_lang=True),
        )

    def generate_instance_level(self):
        records = [
            inst for inst in self._records("dungeons") if inst.get("level_range")
        ]
        if not records:
            return None
        inst = random.choice(records)
        return self._question(
            "instance_level",
            inst["id"],
            category="Instanzen",
            answers=[
                inst.get("level_range"),
                inst.get("answers", {}).get("level_range"),
            ],
            difficulty="easy",
            source=inst,
            instance_name=self._text(inst.get("name"), require_lang=True),
        )

    def generate_instance_level_fit(self):
        records = [
            inst for inst in self._records("dungeons") if inst.get("level_range")
        ]
        if not records:
            return None
        inst = random.choice(records)
        payload = self._level_fit_payload(inst.get("level_range"))
        if not payload:
            return None
        level, answers = payload
        return self._question(
            "instance_level_fit",
            inst["id"],
            category="Instanzen",
            answers=answers,
            difficulty="medium",
            source=inst,
            instance_name=self._text(inst.get("name"), require_lang=True),
            level=level,
        )

    def generate_instance_players(self):
        records = [
            inst for inst in self._records("dungeons") if inst.get("player_count")
        ]
        if not records:
            return None
        inst = random.choice(records)
        players = str(inst["player_count"])
        return self._question(
            "instance_players",
            inst["id"],
            category="Instanzen",
            answers=[players, f"{players} Spieler", f"{players} players"],
            difficulty="easy",
            source=inst,
            instance_name=self._text(inst.get("name"), require_lang=True),
        )

    def generate_instance_location(self):
        records = [
            inst for inst in self._records("dungeons") if inst.get("location_text")
        ]
        if not records:
            return None
        inst = random.choice(records)
        return self._question(
            "instance_location",
            inst["id"],
            category="Instanzen",
            answers=[inst.get("location_text")],
            difficulty="medium",
            source=inst,
            instance_name=self._text(inst.get("name"), require_lang=True),
        )

    def generate_drop_instance(self):
        drops = self._quiz_drops()
        if not drops:
            return None
        drop = random.choice(drops)
        item = self._item_for(drop)
        inst = self._instance_for(drop)
        item_subclass = item.get("item_subclass")
        item_type = ITEM_SUBCLASS_LABELS.get(self.language, {}).get(
            item_subclass, item_subclass
        )
        return self._question(
            "drop_instance",
            drop["id"],
            category="Drops",
            answers=[self._text(inst.get("name")), inst.get("answers", {}).get("name")],
            difficulty="medium",
            source=item,
            item_name=self._text(item.get("name"), require_lang=True),
            item_type=item_type or "",
        )

    def generate_drop_source(self):
        drops = self._quiz_drops()
        if not drops:
            return None
        drop = random.choice(drops)
        item = self._item_for(drop)
        inst = self._instance_for(drop)
        return self._question(
            "drop_source",
            drop["id"],
            category="Drops",
            answers=[drop.get("source_name")],
            difficulty="hard",
            source=item,
            item_name=self._text(item.get("name"), require_lang=True),
            instance_name=self._text(inst.get("name"), require_lang=True),
        )

    def generate_item_quality(self):
        records = [item for item in self._records("items") if item.get("quality")]
        if not records:
            return None
        item = random.choice(records)
        quality = item["quality"]
        return self._question(
            "item_quality",
            item["id"],
            category="Items",
            answers=[
                quality,
                QUALITY_LABELS["de"].get(quality, quality),
                QUALITY_LABELS["en"].get(quality, quality),
            ],
            difficulty="medium",
            source=item,
            item_name=self._text(item.get("name"), require_lang=True),
        )

    def generate_item_subclass(self):
        records = [item for item in self._records("items") if item.get("item_subclass")]
        if not records:
            return None
        item = random.choice(records)
        subclass = item["item_subclass"]
        return self._question(
            "item_subclass",
            item["id"],
            category="Items",
            answers=[
                subclass,
                ITEM_SUBCLASS_LABELS["de"].get(subclass, subclass),
                ITEM_SUBCLASS_LABELS["en"].get(subclass, subclass),
            ],
            difficulty="medium",
            source=item,
            item_name=self._text(item.get("name"), require_lang=True),
        )

    def generate_item_required_level(self):
        records = [
            item for item in self._records("items") if item.get("required_level")
        ]
        if not records:
            return None
        item = random.choice(records)
        level = str(item["required_level"])
        return self._question(
            "item_required_level",
            item["id"],
            category="Items",
            answers=[level, f"Level {level}", f"Stufe {level}"],
            difficulty="medium",
            source=item,
            item_name=self._text(item.get("name"), require_lang=True),
        )

    def generate_dungeon_level(self):
        return self.generate_instance_level()


def get_provider(bot, language):
    return WoWQuestionProvider(bot, language=language)
