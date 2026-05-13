from __future__ import annotations

import argparse
import asyncio
import copy
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiohttp
from unidecode import unidecode

from lotus_bot.bot import load_json, load_wow_data
from lotus_bot.cogs.quiz.area_providers.wow_validation import assert_valid_wow_data

WOWHEAD_BASE = "https://www.wowhead.com/classic"
DEFAULT_DATA_PATH = Path("data/wow/classic_hc")
DEFAULT_CACHE_PATH = Path("data/pers/wow_import_cache")
INSTANCE_TABLES = ("dungeons", "zones", "items", "instance_drops")
ALL_TABLES = (
    "abilities",
    "classes",
    "continents",
    "dungeons",
    "factions",
    "instance_drops",
    "items",
    "power_types",
    "profession_recipes",
    "professions",
    "races",
    "racial_traits",
    "spell_categories",
    "spells",
    "talent_trees",
    "talents",
    "zones",
)
SLICE_ORDER = ("base", "zones", "spells", "professions", "instances")
CLASSIC_INSTANCE_IDS = [
    796,
    719,
    209,
    491,
    718,
    1584,
    1583,
    1581,
    722,
    2100,
    1176,
    1337,
    721,
    717,
    2437,
    1477,
    2557,
    2057,
    2017,
    3456,
    1977,
    2717,
    2677,
    3428,
    3429,
    2159,
]

CLASS_IDS = {
    1: "warrior",
    2: "paladin",
    3: "hunter",
    4: "rogue",
    5: "priest",
    7: "shaman",
    8: "mage",
    9: "warlock",
    11: "druid",
}

RACE_IDS = {
    1: "human",
    2: "orc",
    3: "dwarf",
    4: "night_elf",
    5: "undead",
    6: "tauren",
    7: "gnome",
    8: "troll",
}

RACE_CLASS_IDS = {
    "human": ["mage", "paladin", "priest", "rogue", "warlock", "warrior"],
    "orc": ["hunter", "rogue", "shaman", "warlock", "warrior"],
    "dwarf": ["hunter", "paladin", "priest", "rogue", "warrior"],
    "night_elf": ["druid", "hunter", "priest", "rogue", "warrior"],
    "undead": ["mage", "priest", "rogue", "warlock", "warrior"],
    "tauren": ["druid", "hunter", "shaman", "warrior"],
    "gnome": ["mage", "rogue", "warlock", "warrior"],
    "troll": ["hunter", "mage", "priest", "rogue", "shaman", "warrior"],
}

CLASS_SLUGS = {
    "warrior": "warrior",
    "paladin": "paladin",
    "hunter": "hunter",
    "rogue": "rogue",
    "priest": "priest",
    "shaman": "shaman",
    "mage": "mage",
    "warlock": "warlock",
    "druid": "druid",
}

TALENT_TREES = {
    "warrior": ["arms", "fury", "protection"],
    "paladin": ["holy", "protection", "retribution"],
    "hunter": ["beast-mastery", "marksmanship", "survival"],
    "rogue": ["assassination", "combat", "subtlety"],
    "priest": ["discipline", "holy", "shadow"],
    "shaman": ["elemental", "enhancement", "restoration"],
    "mage": ["arcane", "fire", "frost"],
    "warlock": ["affliction", "demonology", "destruction"],
    "druid": ["balance", "feral-combat", "restoration"],
}

PROFESSIONS = {
    "alchemy": {"type": "primary", "de": "Alchemie", "en": "Alchemy"},
    "blacksmithing": {"type": "primary", "de": "Schmiedekunst", "en": "Blacksmithing"},
    "enchanting": {"type": "primary", "de": "Verzauberkunst", "en": "Enchanting"},
    "engineering": {"type": "primary", "de": "Ingenieurskunst", "en": "Engineering"},
    "herbalism": {"type": "primary", "de": "Kräuterkunde", "en": "Herbalism"},
    "leatherworking": {
        "type": "primary",
        "de": "Lederverarbeitung",
        "en": "Leatherworking",
    },
    "mining": {"type": "primary", "de": "Bergbau", "en": "Mining"},
    "skinning": {"type": "primary", "de": "Kürschnerei", "en": "Skinning"},
    "tailoring": {"type": "primary", "de": "Schneiderei", "en": "Tailoring"},
    "cooking": {"type": "secondary", "de": "Kochkunst", "en": "Cooking"},
    "first-aid": {"type": "secondary", "de": "Erste Hilfe", "en": "First Aid"},
    "fishing": {"type": "secondary", "de": "Angeln", "en": "Fishing"},
}

PROFESSION_SKILLLINE_IDS = {
    "alchemy": 171,
    "blacksmithing": 164,
    "cooking": 185,
    "enchanting": 333,
    "engineering": 202,
    "first-aid": 129,
    "fishing": 356,
    "herbalism": 182,
    "leatherworking": 165,
    "mining": 186,
    "skinning": 393,
    "tailoring": 197,
}

RECIPE_PROFESSION_IDS = {
    "alchemy",
    "blacksmithing",
    "cooking",
    "enchanting",
    "engineering",
    "leatherworking",
    "mining",
    "tailoring",
}

PROFESSION_SPELL_PATHS = {
    "cooking": "/spells/secondary-skills",
}

RECIPE_ITEM_PROFESSION_IDS = {
    "alchemy",
    "blacksmithing",
    "cooking",
    "enchanting",
    "engineering",
    "leatherworking",
    "tailoring",
}

RECIPE_ITEM_PREFIXES = (
    "Recipe:",
    "Formula:",
    "Plans:",
    "Schematic:",
    "Pattern:",
)

ALLIANCE_SIDE = 1

ZONE_LIST_URLS = {
    "eastern_kingdoms": "/zones/eastern-kingdoms",
    "kalimdor": "/zones/kalimdor",
}

SPELL_CATEGORIES = {
    "talent": {"de": "Talent", "en": "Talent"},
    "class_ability": {"de": "Klassenfähigkeit", "en": "Class Ability"},
    "racial_trait": {"de": "Volksfähigkeit", "en": "Racial Trait"},
    "profession": {"de": "Beruf", "en": "Profession"},
}

QUALITY_BY_ID = {
    0: "poor",
    1: "common",
    2: "uncommon",
    3: "rare",
    4: "epic",
    5: "legendary",
}

ITEM_CLASS_BY_ID = {
    0: "consumable",
    2: "weapon",
    4: "armor",
    12: "quest",
}

ITEM_SUBCLASS_BY_CLASS = {
    0: {1: "potion", 2: "elixir", 3: "flask", 5: "food_drink"},
    2: {
        0: "axe",
        1: "axe",
        2: "bow",
        3: "gun",
        4: "mace",
        5: "mace",
        6: "polearm",
        7: "sword",
        8: "sword",
        10: "staff",
        13: "fist_weapon",
        15: "dagger",
        16: "thrown",
        18: "crossbow",
        19: "wand",
        20: "fishing_pole",
    },
    4: {
        -8: "shirt",
        -6: "cloak",
        -5: "off_hand",
        -4: "trinket",
        -3: "amulet",
        -2: "ring",
        0: "miscellaneous",
        1: "cloth",
        2: "leather",
        3: "mail",
        4: "plate",
        6: "shield",
    },
    12: {0: "quest"},
}

SLOT_BY_ID = {
    1: "head",
    2: "neck",
    3: "shoulder",
    5: "chest",
    6: "waist",
    7: "legs",
    8: "feet",
    9: "wrist",
    10: "hands",
    11: "finger",
    12: "trinket",
    13: "one_hand",
    15: "ranged",
    16: "back",
    17: "two_hand",
    20: "chest",
    21: "main_hand",
    22: "off_hand",
    23: "held_in_off_hand",
    26: "ranged",
    28: "relic",
}

ARMOR_SLOT_IDS = {1, 3, 5, 6, 7, 8, 9, 10, 16, 20, 23}
WEAPON_SLOT_IDS = {13, 15, 17, 21, 22, 26}

TERRITORY_BY_LABEL = {
    "allianz": "alliance",
    "alliance": "alliance",
    "horde": "horde",
    "umkämpft": "contested",
    "umkampft": "contested",
    "contested": "contested",
    "sanktuario": "sanctuary",
    "sanctuary": "sanctuary",
}

INSTANCE_TYPE_BY_LABEL = {
    "dungeon": "dungeon",
    "schlachtzug": "raid",
    "raid": "raid",
}


@dataclass
class ImportResult:
    data: dict[str, list[dict[str, Any]]]
    added: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import curated WoW Classic HC data.")
    parser.add_argument(
        "--slice",
        choices=["base", "zones", "spells", "professions", "instances", "all"],
        required=True,
    )
    parser.add_argument("--ids", default="", help="Comma separated Wowhead zone IDs")
    parser.add_argument("--data-path", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--limit-drops", type=int, default=None)
    parser.add_argument("--limit-records", type=int, default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--preview", action="store_true", help="Default; kept for clarity"
    )
    return parser.parse_args(argv)


async def run_import(args: argparse.Namespace) -> ImportResult:
    current = load_managed_tables(Path(args.data_path))
    strip_legacy_source_urls(current)
    fetcher = WowheadFetcher(
        cache_path=Path(getattr(args, "cache_path", DEFAULT_CACHE_PATH)),
        use_cache=not getattr(args, "no_cache", False),
    )
    result = ImportResult(data=copy.deepcopy(current))

    for slice_name in _selected_slices(args.slice):
        if slice_name == "base":
            slice_result = import_base(result.data)
        elif slice_name == "zones":
            pages = await fetcher.fetch_localized_paths(ZONE_LIST_URLS.values())
            slice_result = import_zones(
                result.data,
                pages,
                limit_records=getattr(args, "limit_records", None),
            )
        elif slice_name == "spells":
            pages = await fetcher.fetch_localized_paths(spell_list_paths())
            slice_result = import_spells(
                result.data,
                pages,
                limit_records=getattr(args, "limit_records", None),
            )
        elif slice_name == "professions":
            pages = await fetcher.fetch_localized_paths(profession_list_paths())
            recipe_item_ids = recipe_item_ids_from_pages(pages)
            pages.update(await fetcher.fetch_localized_items(recipe_item_ids))
            slice_result = import_professions(
                result.data,
                pages,
                limit_records=getattr(args, "limit_records", None),
            )
        else:
            wowhead_ids = _instance_ids(args.ids)
            pages = await fetcher.fetch_instance_pages(wowhead_ids)
            slice_result = import_instances(
                result.data, pages, limit_drops=args.limit_drops
            )
        result = _combine_results(slice_result, result)

    strip_legacy_source_urls(result.data)
    assert_valid_wow_data(result.data)
    if args.write:
        write_tables(result.data, Path(args.data_path), ALL_TABLES)
        assert_valid_wow_data(load_wow_data(args.data_path))

    return result


def _selected_slices(slice_name: str) -> tuple[str, ...]:
    return SLICE_ORDER if slice_name == "all" else (slice_name,)


def _instance_ids(raw_ids: str) -> list[int]:
    if not raw_ids.strip():
        return CLASSIC_INSTANCE_IDS
    return [int(part.strip()) for part in raw_ids.split(",") if part.strip()]


def _combine_results(new: ImportResult, previous: ImportResult) -> ImportResult:
    for table, count in previous.added.items():
        new.added[table] = new.added.get(table, 0) + count
    for table, count in previous.updated.items():
        new.updated[table] = new.updated.get(table, 0) + count
    new.warnings = previous.warnings + new.warnings
    return new


class WowheadFetcher:
    def __init__(
        self,
        *,
        cache_path: Path = DEFAULT_CACHE_PATH,
        use_cache: bool = True,
        delay_seconds: float = 0.3,
    ) -> None:
        self.cache_path = cache_path
        self.use_cache = use_cache
        self.delay_seconds = delay_seconds

    async def fetch_instance_pages(
        self, wowhead_ids: list[int]
    ) -> dict[int, dict[str, str]]:
        pages: dict[int, dict[str, str]] = {}
        for wowhead_id in wowhead_ids:
            pages[wowhead_id] = {
                "de": await self.fetch_url(_zone_url(wowhead_id, "de")),
                "en": await self.fetch_url(_zone_url(wowhead_id, "en")),
            }
        return pages

    async def fetch_localized_paths(
        self,
        paths: list[str] | tuple[str, ...] | Any,
    ) -> dict[str, dict[str, str]]:
        pages: dict[str, dict[str, str]] = {}
        for path in paths:
            pages[str(path)] = {
                "de": await self.fetch_url(_path_url(str(path), "de")),
                "en": await self.fetch_url(_path_url(str(path), "en")),
            }
        return pages

    async def fetch_localized_items(
        self, item_ids: list[int]
    ) -> dict[str, dict[str, str]]:
        pages: dict[str, dict[str, str]] = {}
        missing: list[tuple[int, str]] = []
        for item_id in item_ids:
            url = _item_url(item_id, "en")
            cached = self._read_cache(url)
            if cached is None:
                missing.append((item_id, url))
                continue
            pages[_item_page_key(item_id)] = {"de": cached, "en": cached}

        if missing:
            semaphore = asyncio.Semaphore(8)
            async with aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0 LotusGamingDEBot/1.0"}
            ) as session:
                tasks = [
                    self._fetch_item_page(session, semaphore, item_id, url)
                    for item_id, url in missing
                ]
                for item_id, page in await asyncio.gather(*tasks):
                    if page:
                        pages[_item_page_key(item_id)] = {"de": page, "en": page}
        return pages

    async def _fetch_item_page(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        item_id: int,
        url: str,
    ) -> tuple[int, str | None]:
        async with semaphore:
            try:
                text = await self._fetch_text(session, url)
            except RuntimeError:
                return item_id, None
            self._write_cache(url, text)
            return item_id, text

    async def fetch_url(self, url: str) -> str:
        cached = self._read_cache(url)
        if cached is not None:
            return cached
        async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 LotusGamingDEBot/1.0"}
        ) as session:
            text = await self._fetch_text(session, url)
        self._write_cache(url, text)
        await asyncio.sleep(self.delay_seconds)
        return text

    async def _fetch_text(self, session: aiohttp.ClientSession, url: str) -> str:
        last_error = ""
        for attempt in range(3):
            async with session.get(url) as response:
                text = await response.text()
                if response.status == 200:
                    return text
                last_error = f"HTTP {response.status} {url} {text[:200]}"
                if response.status not in {403, 429, 500, 502, 503, 504}:
                    break
            await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Wowhead request failed: {last_error}")

    def _cache_file(self, url: str) -> Path:
        return self.cache_path / f"{slugify(url)}.html"

    def _read_cache(self, url: str) -> str | None:
        if not self.use_cache:
            return None
        path = self._cache_file(url)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def _write_cache(self, url: str, text: str) -> None:
        if not self.use_cache:
            return
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self._cache_file(url).write_text(text, encoding="utf-8")


async def _fetch_text(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url) as response:
        if response.status != 200:
            text = await response.text()
            raise RuntimeError(
                f"Wowhead request failed: HTTP {response.status} {url} {text[:200]}"
            )
        return await response.text()


def import_base(current: dict[str, list[dict[str, Any]]]) -> ImportResult:
    data = copy.deepcopy(current)
    result = ImportResult(data=data)
    races = []
    for race in data.get("races", []):
        updated_race = copy.deepcopy(race)
        updated_race["class_ids"] = RACE_CLASS_IDS.get(updated_race.get("id"), [])
        races.append(updated_race)
    records = {
        "classes": data.get("classes", []),
        "races": races,
        "factions": data.get("factions", []),
        "power_types": data.get("power_types", []),
        "spell_categories": [
            {"id": key, "name": value} for key, value in SPELL_CATEGORIES.items()
        ],
        "continents": data.get("continents", []),
    }
    for table, rows in records.items():
        added, updated = merge_records(data.setdefault(table, []), rows)
        result.added[table] = added
        result.updated[table] = updated
    strip_legacy_source_urls(data)
    return result


def import_zones(
    current: dict[str, list[dict[str, Any]]],
    pages: dict[str, dict[str, str]],
    *,
    limit_records: int | None = None,
) -> ImportResult:
    data = copy.deepcopy(current)
    result = ImportResult(data=data)
    zones: list[dict[str, Any]] = []
    for continent_id, path in ZONE_LIST_URLS.items():
        localized = pages[path]
        de_rows = extract_listview_data(localized["de"], "zones")
        en_rows = {
            row["id"]: row for row in extract_listview_data(localized["en"], "zones")
        }
        for row in de_rows:
            if int(row.get("instance", 0)) != 0:
                continue
            zone = normalize_zone(row, en_rows.get(row["id"], {}), continent_id)
            zones.append(zone)
            if limit_records and len(zones) >= limit_records:
                break
        if limit_records and len(zones) >= limit_records:
            break
    added, updated = merge_records(data.setdefault("zones", []), zones)
    result.added["zones"] = added
    result.updated["zones"] = updated
    strip_legacy_source_urls(data)
    return result


def import_spells(
    current: dict[str, list[dict[str, Any]]],
    pages: dict[str, dict[str, str]],
    *,
    limit_records: int | None = None,
) -> ImportResult:
    data = copy.deepcopy(current)
    result = ImportResult(data=data)
    spells: list[dict[str, Any]] = []
    talents: list[dict[str, Any]] = []
    abilities: list[dict[str, Any]] = []
    racial_traits: list[dict[str, Any]] = []
    talent_trees: list[dict[str, Any]] = []

    for class_id, trees in TALENT_TREES.items():
        class_slug = CLASS_SLUGS[class_id]
        for tree_slug in trees:
            path = f"/spells/talents/{class_slug}/{tree_slug}"
            localized = pages[path]
            tree_id = f"{class_id}.{slugify(tree_slug)}"
            tree_name = _tree_name(localized, tree_slug)
            talent_trees.append(
                {"id": tree_id, "class_id": class_id, "name": tree_name}
            )
            de_rows = extract_spell_rows(localized["de"])
            en_rows = {row["id"]: row for row in extract_spell_rows(localized["en"])}
            de_spell_data = extract_gatherer_spell_data(localized["de"])
            en_spell_data = extract_gatherer_spell_data(localized["en"])
            for row in de_rows:
                if not _is_classic_era_spell(row):
                    continue
                en_row = en_rows.get(row["id"], {})
                spell = normalize_spell(
                    row,
                    en_row,
                    "talent",
                    de_spell_data.get(row["id"], {}),
                    en_spell_data.get(row["id"], {}),
                )
                spells.append(spell)
                talents.append(
                    {
                        "id": f"{class_id}.{slugify(str(en_row.get('name') or row.get('name')))}.{row['id']}",
                        "spell_id": spell["id"],
                        "class_id": class_id,
                        "tree_id": tree_id,
                        "hardcore_valid": True,
                        "rank": _rank_number(row.get("rank")),
                        "answers": {
                            "name": _localized_answers(spell["name"]),
                            "tree": _localized_answers(tree_name),
                        },
                    }
                )
                if limit_records and len(talents) >= limit_records:
                    break
            if limit_records and len(talents) >= limit_records:
                break
        if limit_records and len(talents) >= limit_records:
            break

    for class_id, class_slug in CLASS_SLUGS.items():
        path = f"/spells/abilities/{class_slug}"
        localized = pages[path]
        de_rows = extract_spell_rows(localized["de"])
        en_rows = {row["id"]: row for row in extract_spell_rows(localized["en"])}
        de_spell_data = extract_gatherer_spell_data(localized["de"])
        en_spell_data = extract_gatherer_spell_data(localized["en"])
        for row in de_rows:
            if not _is_classic_era_spell(row):
                continue
            en_row = en_rows.get(row["id"], {})
            spell = normalize_spell(
                row,
                en_row,
                "class_ability",
                de_spell_data.get(row["id"], {}),
                en_spell_data.get(row["id"], {}),
            )
            spells.append(spell)
            abilities.append(
                {
                    "id": f"{class_id}.{slugify(str(en_row.get('name') or row.get('name')))}.{row['id']}",
                    "spell_id": spell["id"],
                    "class_id": class_id,
                    "hardcore_valid": True,
                    "answers": {
                        "class": _class_answers(data, class_id),
                        "name": _localized_answers(spell["name"]),
                    },
                }
            )
            if limit_records and len(abilities) >= limit_records:
                break
        if limit_records and len(abilities) >= limit_records:
            break

    localized = pages["/spells/racial-traits"]
    de_rows = extract_spell_rows(localized["de"])
    en_rows = {row["id"]: row for row in extract_spell_rows(localized["en"])}
    de_spell_data = extract_gatherer_spell_data(localized["de"])
    en_spell_data = extract_gatherer_spell_data(localized["en"])
    for row in de_rows:
        if not _is_classic_era_spell(row):
            continue
        en_row = en_rows.get(row["id"], {})
        race_ids = [RACE_IDS[race] for race in row.get("races", []) if race in RACE_IDS]
        if not race_ids:
            continue
        spell = normalize_spell(
            row,
            en_row,
            "racial_trait",
            de_spell_data.get(row["id"], {}),
            en_spell_data.get(row["id"], {}),
        )
        spells.append(spell)
        for race_id in race_ids:
            racial_traits.append(
                {
                    "id": f"{race_id}.{slugify(str(en_row.get('name') or row.get('name')))}",
                    "race_id": race_id,
                    "spell_id": spell["id"],
                    "hardcore_valid": True,
                }
            )
        if limit_records and len(racial_traits) >= limit_records:
            break

    for table, rows in {
        "spells": spells,
        "talents": talents,
        "abilities": abilities,
        "racial_traits": racial_traits,
        "talent_trees": talent_trees,
    }.items():
        added, updated = merge_records(data.setdefault(table, []), rows)
        result.added[table] = added
        result.updated[table] = updated
    strip_legacy_source_urls(data)
    return result


def import_professions(
    current: dict[str, list[dict[str, Any]]],
    pages: dict[str, dict[str, str]],
    *,
    limit_records: int | None = None,
) -> ImportResult:
    data = copy.deepcopy(current)
    result = ImportResult(data=data)
    professions = [
        {
            "id": key,
            "name": {"de": value["de"], "en": value["en"]},
            "type": value["type"],
        }
        for key, value in PROFESSIONS.items()
    ]
    spells: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    recipes_by_spell: dict[str, dict[str, Any]] = {}
    recipe_items_by_spell = recipe_items_by_spell_id(pages)
    recipe_items_by_name = recipe_items_by_recipe_name(pages)

    for profession_id in sorted(RECIPE_PROFESSION_IDS):
        path = profession_spell_path(profession_id)
        localized = pages[path]
        de_rows = extract_spell_rows(localized["de"])
        en_rows = {row["id"]: row for row in extract_spell_rows(localized["en"])}
        de_spell_data = extract_gatherer_spell_data(localized["de"])
        en_spell_data = extract_gatherer_spell_data(localized["en"])
        de_item_data = extract_gatherer_item_data(localized["de"])
        en_item_data = extract_gatherer_item_data(localized["en"])
        for row in de_rows:
            if not _is_classic_era_spell(row):
                continue
            if not _is_profession_recipe_row(row):
                continue
            recipe_profession_id = _profession_from_skillline(row)
            if recipe_profession_id != profession_id:
                continue
            en_row = en_rows.get(row["id"], {})
            spell = normalize_spell(
                row,
                en_row,
                "profession",
                de_spell_data.get(row["id"], {}),
                en_spell_data.get(row["id"], {}),
            )
            item = None
            if "creates" in row:
                item_id = int((row.get("creates") or [0])[0])
                item = normalize_created_item(
                    row,
                    en_row,
                    de_item_data.get(item_id, {}),
                    en_item_data.get(item_id, {}),
                    recipe_profession_id,
                )
            recipe_items = list(recipe_items_by_spell.get(spell["id"], []))
            recipe_items.extend(
                recipe_items_by_name.get(
                    (
                        recipe_profession_id,
                        _recipe_name_key(spell["name"].get("en", "")),
                    ),
                    [],
                )
            )
            recipe_items = _dedupe_recipe_items(recipe_items)
            recipe_item = _primary_recipe_item(recipe_items)
            recipe = {
                "id": f"{recipe_profession_id}.{slugify(str(en_row.get('name') or row.get('name')))}",
                "profession_id": recipe_profession_id,
                "skillline_id": PROFESSION_SKILLLINE_IDS[recipe_profession_id],
                "spell_id": spell["id"],
                "creates_item_id": item["id"] if item else None,
                "required_skill": int(row.get("learnedat") or 0),
                "learned_from": _learned_from(row, recipe_item),
                "hardcore_valid": True,
                "source_urls": spell["source_urls"],
            }
            if recipe_item:
                recipe.update(recipe_item)
                recipe["recipe_items"] = recipe_items
            existing = recipes_by_spell.get(spell["id"])
            if existing and existing["profession_id"] != recipe_profession_id:
                result.warnings.append(
                    f"Skipped ambiguous recipe {spell['id']} for "
                    f"{existing['profession_id']} and {recipe_profession_id}."
                )
                recipes_by_spell.pop(spell["id"], None)
                continue
            spells.append(spell)
            if item:
                items.append(item)
            recipes_by_spell[spell["id"]] = recipe
            if limit_records and len(recipes_by_spell) >= limit_records:
                break
        if limit_records and len(recipes_by_spell) >= limit_records:
            break

    recipes = sorted(recipes_by_spell.values(), key=lambda row: row["id"])

    for table, rows in {
        "professions": professions,
        "spells": spells,
        "items": items,
    }.items():
        added, updated = merge_records(data.setdefault(table, []), rows)
        result.added[table] = added
        result.updated[table] = updated
    old_recipes = data.get("profession_recipes", [])
    data["profession_recipes"] = recipes
    result.added["profession_recipes"] = len(
        {row["id"] for row in recipes} - {row["id"] for row in old_recipes}
    )
    result.updated["profession_recipes"] = len(recipes)
    strip_legacy_source_urls(data)
    return result


def import_instances(
    current: dict[str, list[dict[str, Any]]],
    pages: dict[int, dict[str, str]],
    *,
    limit_drops: int | None = None,
) -> ImportResult:
    data = copy.deepcopy(current)
    changes = ImportResult(data=data)

    for wowhead_id, localized_pages in pages.items():
        records = parse_instance_page(
            wowhead_id, localized_pages, limit_drops=limit_drops
        )
        for table in INSTANCE_TABLES:
            added, updated = merge_records(
                data.setdefault(table, []), records.get(table, [])
            )
            changes.added[table] = changes.added.get(table, 0) + added
            changes.updated[table] = changes.updated.get(table, 0) + updated

    strip_legacy_source_urls(data)
    return changes


def parse_instance_page(
    wowhead_id: int,
    localized_pages: dict[str, str],
    *,
    limit_drops: int | None = None,
) -> dict[str, list[dict[str, Any]]]:
    de_page = localized_pages["de"]
    en_page = localized_pages["en"]
    de_info = extract_infobox(de_page)
    en_info = extract_infobox(en_page)
    de_name = extract_title_name(de_page)
    en_name = _clean_text(en_info.get("Name") or extract_title_name(en_page))
    instance_type = _instance_type(de_info.get("Instanzart") or en_info.get("Type"))
    instance_id = f"instance.{slugify(en_name)}"
    level_range = _level_range(de_info.get("Stufe") or en_info.get("Level"))

    records: dict[str, list[dict[str, Any]]] = {
        "dungeons": [
            {
                "id": instance_id,
                "zone_id": f"zone.{wowhead_id}",
                "wowhead_id": wowhead_id,
                "type": instance_type,
                "name": {"de": de_name, "en": en_name},
                "level_range": level_range,
                "territory_id": _territory_id(
                    de_info.get("Territorium") or en_info.get("Territory")
                ),
                "player_count": _int_or_none(
                    de_info.get("Anzahl an Spielern") or en_info.get("Players")
                ),
                "hardcore_enabled": instance_type in {"dungeon", "raid"},
                "source_urls": {
                    "de": _zone_url(wowhead_id, "de"),
                    "en": _zone_url(wowhead_id, "en"),
                },
                "answers": {
                    "level_range": _level_answers(level_range),
                    "name": [de_name, en_name],
                },
            }
        ],
        "zones": [],
        "items": [],
        "instance_drops": [],
    }

    de_drops = extract_drop_listview(de_page)
    en_drops = {drop["id"]: drop for drop in extract_drop_listview(en_page)}
    accepted_drops = []
    for drop in de_drops:
        if not _is_classic_normal_drop(drop):
            continue
        if _is_quest_item(drop):
            continue
        accepted_drops.append(drop)
        if limit_drops and len(accepted_drops) >= limit_drops:
            break

    for drop in accepted_drops:
        item_id = int(drop["id"])
        en_drop = en_drops.get(item_id, {})
        records["items"].append(normalize_item(drop, en_drop))
        records["instance_drops"].append(
            normalize_drop(instance_id, wowhead_id, drop, en_drop)
        )

    return records


def extract_infobox(page: str) -> dict[str, str]:
    match = re.search(r'WH\.markup\.printHtml\("((?:\\.|[^"\\])*)"', page)
    if not match:
        return {}
    markup = json.loads(f'"{match.group(1)}"')
    values: dict[str, str] = {}
    for item in re.findall(r"\[li\](.*?)\[/li\]", markup):
        text = _clean_text(item)
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def extract_title_name(page: str) -> str:
    match = re.search(
        r"<title>(.*?) - Zone - (?:World of Warcraft: Classic|Classic World of Warcraft)</title>",
        page,
        re.S,
    )
    if not match:
        return ""
    return html.unescape(match.group(1)).strip()


def extract_drop_listview(page: str) -> list[dict[str, Any]]:
    start = page.find("new Listview({template: 'item', id: 'drops'")
    if start == -1:
        return []
    data_pos = page.find("data:", start)
    if data_pos == -1:
        return []
    array_start = page.find("[", data_pos)
    if array_start == -1:
        return []
    array_end = _matching_json_array_end(page, array_start)
    if array_end == -1:
        return []
    data = json.loads(page[array_start : array_end + 1])
    return data if isinstance(data, list) else []


def extract_listview_data(page: str, listview_id: str) -> list[dict[str, Any]]:
    json_data = extract_listpage_json(page, listview_id)
    if json_data is not None:
        return json_data
    start = page.find(f"id: '{listview_id}'")
    if start == -1:
        start = page.find(f'id: "{listview_id}"')
    if start == -1:
        return []
    data_pos = page.rfind("data:", 0, start)
    if data_pos == -1:
        data_pos = page.find("data:", start)
    array_start = page.find("[", data_pos)
    if array_start == -1:
        return []
    array_end = _matching_json_array_end(page, array_start)
    if array_end == -1:
        return []
    return json.loads(_jsonish_to_json(page[array_start : array_end + 1]))


def extract_listpage_json(page: str, listview_id: str) -> list[dict[str, Any]] | None:
    match = re.search(
        r'<script type="application/json" id="data\.page\.listPage\.listviews">(.*?)</script>',
        page,
        re.S,
    )
    if not match:
        return None
    views = json.loads(match.group(1))
    for view in views:
        if view.get("id") == listview_id:
            data = view.get("data", [])
            return data if isinstance(data, list) else []
    return None


def extract_spell_rows(page: str) -> list[dict[str, Any]]:
    raw = extract_js_var_array(page, "listviewspells")
    return json.loads(_jsonish_to_json(raw)) if raw else []


def extract_item_rows(page: str) -> list[dict[str, Any]]:
    raw = extract_js_var_array(page, "listviewitems")
    return json.loads(_jsonish_to_json(raw)) if raw else []


def extract_gatherer_spell_data(page: str) -> dict[int, dict[str, Any]]:
    return extract_gatherer_data(page, 6)


def extract_gatherer_item_data(page: str) -> dict[int, dict[str, Any]]:
    return extract_gatherer_data(page, 3)


def extract_gatherer_data(page: str, type_id: int) -> dict[int, dict[str, Any]]:
    marker = f"WH.Gatherer.addData({type_id},"
    start = page.find(marker)
    if start == -1:
        return {}
    object_start = page.find("{", start)
    if object_start == -1:
        return {}
    object_end = _matching_json_object_end(page, object_start)
    if object_end == -1:
        return {}
    data = json.loads(_jsonish_to_json(page[object_start : object_end + 1]))
    return {int(key): value for key, value in data.items()}


def extract_js_var_array(page: str, var_name: str) -> str | None:
    start = page.find(f"var {var_name} =")
    if start == -1:
        return None
    array_start = page.find("[", start)
    if array_start == -1:
        return None
    array_end = _matching_json_array_end(page, array_start)
    if array_end == -1:
        return None
    return page[array_start : array_end + 1]


def normalize_zone(
    de_row: dict[str, Any],
    en_row: dict[str, Any],
    continent_id: str,
) -> dict[str, Any]:
    wowhead_id = int(de_row["id"])
    zone = {
        "id": f"zone.{wowhead_id}",
        "wowhead_id": wowhead_id,
        "name": {
            "de": str(de_row.get("name") or ""),
            "en": str(en_row.get("name") or de_row.get("name") or ""),
        },
        "continent_id": continent_id,
        "territory_id": _territory_from_wowhead(de_row.get("territory")),
        "type": "outdoor_zone",
        "hardcore_enabled": True,
        "source_urls": {
            "de": _zone_url(wowhead_id, "de"),
            "en": _zone_url(wowhead_id, "en"),
        },
    }
    min_level = int(de_row.get("minlevel") or 0)
    max_level = int(de_row.get("maxlevel") or 0)
    if min_level and max_level:
        zone["level_range"] = (
            f"{min_level}-{max_level}" if min_level != max_level else str(max_level)
        )
    return zone


def normalize_spell(
    de_row: dict[str, Any],
    en_row: dict[str, Any],
    category_id: str,
    de_spell_data: dict[str, Any],
    en_spell_data: dict[str, Any],
) -> dict[str, Any]:
    wowhead_id = int(de_row["id"])
    name = {
        "de": str(de_spell_data.get("name_dede") or de_row.get("name") or ""),
        "en": str(
            en_spell_data.get("name_enus")
            or en_row.get("name")
            or de_row.get("name")
            or ""
        ),
    }
    description = {
        "de": _description(de_spell_data, name["de"]),
        "en": _description(en_spell_data, name["en"]),
    }
    spell = {
        "id": f"spell.{wowhead_id}",
        "wowhead_id": wowhead_id,
        "category_id": category_id,
        "name": name,
        "description": description,
        "source_urls": {
            "de": _spell_url(wowhead_id, "de"),
            "en": _spell_url(wowhead_id, "en"),
        },
    }
    if de_row.get("level"):
        spell["required_level"] = int(de_row["level"])
    rank = de_row.get("rank") or de_spell_data.get("rank_dede")
    if rank:
        spell["rank"] = str(rank)
    return spell


def normalize_created_item(
    de_row: dict[str, Any],
    en_row: dict[str, Any],
    de_item_data: dict[str, Any] | None = None,
    en_item_data: dict[str, Any] | None = None,
    profession_id: str | None = None,
) -> dict[str, Any]:
    creates = de_row.get("creates") or []
    item_id = int(creates[0])
    de_item_data = de_item_data or {}
    en_item_data = en_item_data or {}
    quality = int(de_item_data.get("quality") or de_row.get("quality", 1))
    equip = _first_mapping(de_item_data.get("jsonequip"), en_item_data.get("jsonequip"))
    slot_id = _int_or_zero(
        equip.get("slotbak") or de_row.get("slotbak") or de_row.get("slot")
    )
    item_class, item_subclass = _created_item_type(
        de_row, en_row, de_item_data, en_item_data, profession_id, slot_id
    )
    item = {
        "id": f"item.{item_id}",
        "wowhead_id": item_id,
        "name": {
            "de": str(de_item_data.get("name_dede") or de_row.get("name") or ""),
            "en": str(
                en_item_data.get("name_enus")
                or en_row.get("name")
                or de_row.get("name")
                or ""
            ),
        },
        "quality": QUALITY_BY_ID.get(quality, "common"),
        "item_class": item_class,
        "item_subclass": item_subclass,
        "is_quest_item": False,
        "source_urls": {
            "de": _item_url(item_id, "de"),
            "en": _item_url(item_id, "en"),
        },
    }
    if slot_id:
        item["slot"] = SLOT_BY_ID.get(slot_id, "miscellaneous")
        item["inventory_type"] = SLOT_BY_ID.get(slot_id, "miscellaneous")
    required_level = _int_or_zero(equip.get("reqlevel"))
    if required_level:
        item["required_level"] = required_level
    item_level = _int_or_zero(de_item_data.get("level") or en_item_data.get("level"))
    if item_level:
        item["item_level"] = item_level
    return item


def normalize_recipe_source_item(
    de_row: dict[str, Any],
    en_row: dict[str, Any],
    profession_id: str,
) -> dict[str, Any]:
    item_id = int(en_row["id"])
    return {
        "recipe_item_id": f"item.{item_id}",
        "recipe_item_name": {
            "de": str(de_row.get("name") or en_row.get("name") or ""),
            "en": str(en_row.get("name") or de_row.get("name") or ""),
        },
        "recipe_item_sources": _source_labels(en_row.get("source", [])),
        "recipe_item_side": _side_label(en_row.get("side")),
        "recipe_item_required_skill": int(
            en_row.get("skill") or de_row.get("skill") or 0
        ),
        "recipe_item_profession_id": profession_id,
        "recipe_item_source_urls": {
            "de": _item_url(item_id, "de"),
            "en": _item_url(item_id, "en"),
        },
    }


def normalize_item(de_drop: dict[str, Any], en_drop: dict[str, Any]) -> dict[str, Any]:
    item_id = int(de_drop["id"])
    item_class_id = int(de_drop.get("classs", -1))
    subclass_id = int(de_drop.get("subclass", 0))
    slot_id = int(de_drop.get("slotbak", de_drop.get("slot", 0)))
    item = {
        "id": f"item.{item_id}",
        "wowhead_id": item_id,
        "name": {
            "de": str(de_drop.get("name") or ""),
            "en": str(en_drop.get("name") or de_drop.get("name") or ""),
        },
        "quality": QUALITY_BY_ID.get(int(de_drop.get("quality", 1)), "common"),
        "slot": SLOT_BY_ID.get(slot_id, "miscellaneous"),
        "inventory_type": SLOT_BY_ID.get(slot_id, "miscellaneous"),
        "item_class": ITEM_CLASS_BY_ID.get(item_class_id, "miscellaneous"),
        "item_subclass": ITEM_SUBCLASS_BY_CLASS.get(item_class_id, {}).get(
            subclass_id, "miscellaneous"
        ),
        "is_quest_item": _is_quest_item(de_drop),
        "source_urls": {
            "de": _item_url(item_id, "de"),
            "en": _item_url(item_id, "en"),
        },
    }
    if "reqlevel" in de_drop:
        item["required_level"] = int(de_drop["reqlevel"])
    if "level" in de_drop:
        item["item_level"] = int(de_drop["level"])
    return item


def normalize_drop(
    instance_id: str,
    instance_wowhead_id: int,
    de_drop: dict[str, Any],
    en_drop: dict[str, Any],
) -> dict[str, Any]:
    item_id = int(de_drop["id"])
    source_de = _first_source_name(de_drop)
    source_en = _first_source_name(en_drop) or source_de
    return {
        "id": f"drop.{slugify(instance_id.removeprefix('instance.'))}.{slugify(str(en_drop.get('name') or de_drop.get('name')))}",
        "instance_id": instance_id,
        "item_id": f"item.{item_id}",
        "source_name": {"de": source_de, "en": source_en},
        "mode": "normal",
        "season": "classic_era",
        "include_in_hardcore_quiz": instance_wowhead_id != 3277,
    }


def merge_records(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> tuple[int, int]:
    index = {record["id"]: position for position, record in enumerate(existing)}
    wowhead_index = {
        record["wowhead_id"]: position
        for position, record in enumerate(existing)
        if record.get("wowhead_id") is not None
    }
    added = 0
    updated = 0
    for record in incoming:
        record_id = record["id"]
        wowhead_id = record.get("wowhead_id")
        position = index.get(record_id)
        if position is None and wowhead_id is not None:
            position = wowhead_index.get(wowhead_id)
        if position is not None:
            if existing[position] != record:
                previous_id = existing[position]["id"]
                existing[position] = record
                index.pop(previous_id, None)
                index[record_id] = position
                if wowhead_id is not None:
                    wowhead_index[wowhead_id] = position
                updated += 1
        else:
            existing.append(record)
            index[record_id] = len(existing) - 1
            if wowhead_id is not None:
                wowhead_index[wowhead_id] = len(existing) - 1
            added += 1
    existing.sort(key=lambda row: str(row["id"]))
    return added, updated


def write_tables(
    data: dict[str, list[dict[str, Any]]],
    base_path: Path,
    tables: tuple[str, ...] = ALL_TABLES,
) -> None:
    base_path.mkdir(parents=True, exist_ok=True)
    strip_legacy_source_urls(data)
    legacy_race_classes = base_path / "race_classes.json"
    if legacy_race_classes.exists():
        legacy_race_classes.unlink()
    for table in tables:
        path = base_path / f"{table}.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data.get(table, []), handle, ensure_ascii=False, indent=2)
            handle.write("\n")


def load_managed_tables(base_path: Path) -> dict[str, list[dict[str, Any]]]:
    return {table: load_json(base_path / f"{table}.json") for table in ALL_TABLES}


def strip_legacy_source_urls(data: dict[str, list[dict[str, Any]]]) -> None:
    for records in data.values():
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict):
                record.pop("source_url", None)


def print_report(result: ImportResult, *, wrote: bool) -> None:
    mode = "write" if wrote else "preview"
    print(f"WoW import {mode} complete.")
    for table in ALL_TABLES:
        if not result.added.get(table, 0) and not result.updated.get(table, 0):
            continue
        print(
            f"- {table}: +{result.added.get(table, 0)} "
            f"/ ~{result.updated.get(table, 0)}"
        )
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")


def _matching_json_array_end(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for pos in range(start, len(text)):
        char = text[pos]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return pos
    return -1


def _matching_json_object_end(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for pos in range(start, len(text)):
        char = text[pos]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return pos
    return -1


def _clean_text(value: str) -> str:
    text = re.sub(r"\[/?[^\]]+\]", "", value)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _jsonish_to_json(value: str) -> str:
    text = re.sub(r"([,{])([A-Za-z_][A-Za-z0-9_]*):", r'\1"\2":', value)
    text = text.replace(":undefined", ":null")
    return text


def spell_list_paths() -> list[str]:
    paths = ["/spells/racial-traits"]
    for class_id, class_slug in CLASS_SLUGS.items():
        paths.append(f"/spells/abilities/{class_slug}")
        paths.extend(
            f"/spells/talents/{class_slug}/{tree_slug}"
            for tree_slug in TALENT_TREES[class_id]
        )
    return paths


def profession_list_paths() -> list[str]:
    return sorted(
        {
            profession_spell_path(profession_id)
            for profession_id in RECIPE_PROFESSION_IDS
        }
        | {
            profession_recipe_item_path(profession_id)
            for profession_id in RECIPE_ITEM_PROFESSION_IDS
        }
    )


def profession_spell_path(profession_id: str) -> str:
    return PROFESSION_SPELL_PATHS.get(
        profession_id, f"/spells/professions/{profession_id}"
    )


def profession_recipe_item_path(profession_id: str) -> str:
    return f"/items/recipes/{profession_id}"


def recipe_item_ids_from_pages(pages: dict[str, dict[str, str]]) -> list[int]:
    item_ids: set[int] = set()
    for profession_id in RECIPE_ITEM_PROFESSION_IDS:
        path = profession_recipe_item_path(profession_id)
        localized = pages.get(path)
        if not localized:
            continue
        for row in extract_item_rows(localized["en"]):
            if _is_horde_recipe_item(row):
                item_ids.add(int(row["id"]))
    return sorted(item_ids)


def recipe_items_by_spell_id(
    pages: dict[str, dict[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    recipe_items: dict[str, list[dict[str, Any]]] = {}
    for profession_id in RECIPE_ITEM_PROFESSION_IDS:
        path = profession_recipe_item_path(profession_id)
        localized = pages.get(path)
        if not localized:
            continue
        de_rows = {
            int(row["id"]): row
            for row in extract_item_rows(localized["de"])
            if _is_horde_recipe_item(row)
        }
        en_rows = [
            row
            for row in extract_item_rows(localized["en"])
            if _is_horde_recipe_item(row)
        ]
        for en_row in en_rows:
            item_id = int(en_row["id"])
            detail = pages.get(_item_page_key(item_id), {})
            spell_ids = _recipe_item_craft_spell_ids(detail.get("en", ""))
            de_row = de_rows.get(item_id, en_row)
            for spell_id in spell_ids:
                candidate = normalize_recipe_source_item(de_row, en_row, profession_id)
                recipe_items.setdefault(spell_id, []).append(candidate)
    return recipe_items


def recipe_items_by_recipe_name(
    pages: dict[str, dict[str, str]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    recipe_items: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for profession_id in RECIPE_ITEM_PROFESSION_IDS:
        path = profession_recipe_item_path(profession_id)
        localized = pages.get(path)
        if not localized:
            continue
        de_rows = {
            int(row["id"]): row
            for row in extract_item_rows(localized["de"])
            if _is_horde_recipe_item(row)
        }
        for en_row in extract_item_rows(localized["en"]):
            if not _is_horde_recipe_item(en_row):
                continue
            item_id = int(en_row["id"])
            candidate = normalize_recipe_source_item(
                de_rows.get(item_id, en_row), en_row, profession_id
            )
            key = (profession_id, _recipe_item_name_key(str(en_row.get("name") or "")))
            recipe_items.setdefault(key, []).append(candidate)
    return recipe_items


def _tree_name(localized: dict[str, str], tree_slug: str) -> dict[str, str]:
    de_title = re.search(r"<title>Classic - (.*?) [^-]+ Talente", localized["de"])
    en_title = re.search(r"<title>Classic - (.*?) [^-]+ Talents", localized["en"])
    return {
        "de": (
            _clean_text(de_title.group(1))
            if de_title
            else tree_slug.replace("-", " ").title()
        ),
        "en": (
            _clean_text(en_title.group(1))
            if en_title
            else tree_slug.replace("-", " ").title()
        ),
    }


def _localized_answers(value: dict[str, str]) -> list[str]:
    return sorted({text for text in value.values() if text})


def _class_answers(data: dict[str, list[dict[str, Any]]], class_id: str) -> list[str]:
    for record in data.get("classes", []):
        if record.get("id") == class_id:
            answers = _localized_answers(record.get("name", {}))
            gender_name = record.get("gender_name", {})
            if isinstance(gender_name, dict):
                for localized in gender_name.values():
                    if isinstance(localized, dict):
                        answers.extend(localized.values())
            return sorted(set(answers))
    return [class_id]


def _rank_number(value: Any) -> int | None:
    if not value:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def _description(spell_data: dict[str, Any], fallback_name: str) -> str:
    for key in ("description_dede", "description_enus", "description"):
        text = _clean_text(str(spell_data.get(key) or ""))
        if text:
            return text
    return fallback_name


def _learned_from(
    row: dict[str, Any], recipe_item: dict[str, Any] | None = None
) -> str:
    if recipe_item:
        return "recipe"
    sources = row.get("source", [])
    if sources and 6 not in sources:
        return "recipe"
    return "trainer"


def _is_profession_recipe_row(row: dict[str, Any]) -> bool:
    if "creates" in row:
        return True
    # Enchanting enchant spells apply an effect directly to gear, so Wowhead does
    # not expose a created item. They still are learnable recipes/formulas.
    return bool(row.get("reagents")) and _profession_from_skillline(row) == "enchanting"


def _is_horde_recipe_item(row: dict[str, Any]) -> bool:
    try:
        item_id = int(row.get("id") or 0)
    except (TypeError, ValueError):
        return False
    if item_id >= 100000:
        return False
    if int(row.get("side") or 0) == ALLIANCE_SIDE:
        return False
    return str(row.get("name") or "").startswith(RECIPE_ITEM_PREFIXES)


def _recipe_item_craft_spell_ids(page: str) -> list[str]:
    spell_data = extract_gatherer_spell_data(page)
    return [f"spell.{spell_id}" for spell_id in sorted(spell_data) if spell_id < 100000]


def _item_page_key(item_id: int) -> str:
    return f"/item={item_id}"


def _source_labels(sources: Any) -> list[str]:
    labels = {
        1: "crafted",
        2: "drop",
        3: "pvp",
        4: "quest",
        5: "vendor",
        6: "trainer",
        16: "world_drop",
        21: "pickpocketed",
    }
    if not isinstance(sources, list):
        return []
    return [labels.get(int(source), str(source)) for source in sources]


def _side_label(side: Any) -> str:
    if int(side or 0) == 2:
        return "horde"
    return "neutral"


def _recipe_source_priority(recipe_item: dict[str, Any]) -> int:
    return 1 if recipe_item.get("recipe_item_side") == "horde" else 0


def _primary_recipe_item(recipe_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(recipe_items, key=_recipe_source_priority, default=None)


def _dedupe_recipe_items(recipe_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in recipe_items:
        item_id = str(item.get("recipe_item_id") or "")
        if item_id:
            by_id[item_id] = item
    return sorted(
        by_id.values(), key=lambda item: str(item.get("recipe_item_id") or "")
    )


def _recipe_item_name_key(name: str) -> str:
    cleaned = name.strip()
    for prefix in RECIPE_ITEM_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    return _recipe_name_key(cleaned)


def _recipe_name_key(name: str) -> str:
    aliases = {
        "mithril headed trout": "mithril head trout",
    }
    key = _norm(name)
    return aliases.get(key, key)


def _norm(value: Any) -> str:
    return unidecode(str(value or "")).casefold().strip()


def _profession_from_skillline(row: dict[str, Any]) -> str | None:
    skills = {int(skill) for skill in row.get("skill", []) if str(skill).isdigit()}
    matches = [
        profession_id
        for profession_id, skillline_id in PROFESSION_SKILLLINE_IDS.items()
        if profession_id in RECIPE_PROFESSION_IDS and skillline_id in skills
    ]
    return matches[0] if len(matches) == 1 else None


def _created_item_type(
    de_row: dict[str, Any],
    en_row: dict[str, Any],
    de_item_data: dict[str, Any],
    en_item_data: dict[str, Any],
    profession_id: str | None,
    slot_id: int,
) -> tuple[str, str]:
    item_class_id = _int_or_none_value(
        de_item_data.get("classs"),
        en_item_data.get("classs"),
        de_row.get("classs"),
        en_row.get("classs"),
    )
    subclass_id = _int_or_none_value(
        de_item_data.get("subclass"),
        en_item_data.get("subclass"),
        de_row.get("subclass"),
        en_row.get("subclass"),
    )
    if item_class_id is not None and subclass_id is not None:
        return (
            ITEM_CLASS_BY_ID.get(item_class_id, "miscellaneous"),
            ITEM_SUBCLASS_BY_CLASS.get(item_class_id, {}).get(
                subclass_id, "miscellaneous"
            ),
        )

    name = " ".join(
        str(value or "")
        for value in (
            de_item_data.get("name_dede"),
            en_item_data.get("name_enus"),
            de_row.get("name"),
            en_row.get("name"),
        )
    ).casefold()
    if slot_id in ARMOR_SLOT_IDS:
        return "armor", _crafted_armor_subclass(profession_id, name, slot_id)
    if slot_id in WEAPON_SLOT_IDS:
        return "weapon", _crafted_weapon_subclass(name)
    if profession_id == "alchemy":
        return "consumable", _alchemy_subclass(name)
    if profession_id == "cooking":
        return "consumable", "food_drink"
    if profession_id == "enchanting":
        return "trade_goods", "enchanting"
    if profession_id in {"blacksmithing", "engineering", "mining"}:
        return "trade_goods", profession_id
    return "miscellaneous", "miscellaneous"


def _crafted_armor_subclass(profession_id: str | None, name: str, slot_id: int) -> str:
    if slot_id == 16:
        return "cloak"
    if slot_id == 23:
        return "off_hand"
    if profession_id == "tailoring":
        return "cloth"
    if profession_id == "leatherworking":
        if any(token in name for token in ("mail", "chain", "kette", "schuppen")):
            return "mail"
        return "leather"
    if profession_id == "blacksmithing":
        if "plate" in name or "platte" in name:
            return "plate"
        return "mail"
    return "miscellaneous"


def _crafted_weapon_subclass(name: str) -> str:
    keywords = {
        "dagger": ("dagger", "dolch"),
        "axe": ("axe", "axt"),
        "mace": ("mace", "streitkolben", "hammer"),
        "sword": ("sword", "schwert", "klinge"),
        "staff": ("staff", "stab"),
        "gun": ("gun", "gewehr"),
    }
    for subclass, tokens in keywords.items():
        if any(token in name for token in tokens):
            return subclass
    return "miscellaneous"


def _alchemy_subclass(name: str) -> str:
    if "elixir" in name or "elixier" in name:
        return "elixir"
    if "flask" in name or "fläschchen" in name or "flaschchen" in name:
        return "flask"
    if "potion" in name or "trank" in name:
        return "potion"
    return "consumable"


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _int_or_none_value(*values: Any) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _territory_from_wowhead(value: Any) -> str:
    return {0: "contested", 1: "horde", 2: "alliance"}.get(int(value or 0), "contested")


def _instance_type(value: str | None) -> str:
    normalized = slugify(value or "")
    return INSTANCE_TYPE_BY_LABEL.get(normalized, "dungeon")


def _territory_id(value: str | None) -> str:
    normalized = slugify(value or "")
    return TERRITORY_BY_LABEL.get(normalized, "contested")


def _level_range(value: str | None) -> str:
    if not value:
        return "60"
    match = re.search(r"(\d+)\s*(?:-|–|bis|to)?\s*(\d+)?", value)
    if not match:
        return "60"
    low = match.group(1)
    high = match.group(2)
    return f"{low}-{high}" if high else low


def _level_answers(level_range: str) -> list[str]:
    if "-" not in level_range:
        return [level_range, f"Level {level_range}", f"Stufe {level_range}"]
    low, high = level_range.split("-", 1)
    return [level_range, f"{low} bis {high}", f"{low} to {high}"]


def _int_or_none(value: str | None) -> int:
    if not value:
        return 0
    numbers = [int(match) for match in re.findall(r"\d+", value)]
    return max(numbers) if numbers else 0


_CLASSIC_DROP_MODES = {1, 9}


def _is_classic_normal_drop(drop: dict[str, Any]) -> bool:
    modes = drop.get("modes", {}).get("mode", [])
    return not modes or bool(_CLASSIC_DROP_MODES.intersection(modes))


def _is_quest_item(drop: dict[str, Any]) -> bool:
    return int(drop.get("classs", -1)) == 12


def _is_classic_era_spell(row: dict[str, Any]) -> bool:
    return int(row.get("id", 0)) < 100000


def _first_source_name(drop: dict[str, Any]) -> str:
    sources = drop.get("sourcemore")
    if isinstance(sources, list) and sources:
        return str(sources[0].get("n") or "")
    return ""


def _zone_url(wowhead_id: int, language: str) -> str:
    if language == "de":
        return f"{WOWHEAD_BASE}/de/zone={wowhead_id}"
    return f"{WOWHEAD_BASE}/zone={wowhead_id}"


def _path_url(path: str, language: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    if language == "de":
        return f"{WOWHEAD_BASE}/de{clean_path}"
    return f"{WOWHEAD_BASE}{clean_path}"


def _item_url(wowhead_id: int, language: str) -> str:
    if language == "de":
        return f"{WOWHEAD_BASE}/de/item={wowhead_id}"
    return f"{WOWHEAD_BASE}/item={wowhead_id}"


def _spell_url(wowhead_id: int, language: str) -> str:
    if language == "de":
        return f"{WOWHEAD_BASE}/de/spell={wowhead_id}"
    return f"{WOWHEAD_BASE}/spell={wowhead_id}"


def slugify(value: str) -> str:
    text = unidecode(str(value)).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    result = asyncio.run(run_import(args))
    print_report(result, wrote=args.write)


if __name__ == "__main__":  # pragma: no cover
    main()
