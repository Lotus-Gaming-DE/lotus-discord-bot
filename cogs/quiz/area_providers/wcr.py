import random

from log_setup import get_logger
import hashlib
from ..utils import create_permutations_list
from .base import DynamicQuestionProvider

logger = get_logger(__name__)


class WCRQuestionProvider(DynamicQuestionProvider):
    question_generators = [
        "generate_type_1",
        "generate_type_2",
        "generate_type_3",
        "generate_type_4",
        "generate_type_5",
    ]

    def __init__(self, bot, language="de"):
        """Initialize the provider and load data from ``bot.data``."""
        units_data = bot.data["wcr"].get("units", [])
        # ``units.json`` may wrap the list of units in a top level key
        if isinstance(units_data, dict) and "units" in units_data:
            units_data = units_data["units"]
        self.units = units_data
        self.locals = bot.data["wcr"]["locals"]
        self.templates = bot.data.get("quiz", {}).get("templates", {}).get("wcr", {})
        self.language = language

    def get_unit_name(self, unit_id: int, lang: str) -> str:
        try:
            units = self.locals.get(lang, {}).get("units", [])
            return next(
                (u["name"] for u in units if u["id"] == unit_id),
                f"[Unbekannt {unit_id}]",
            )
        except Exception:
            return f"[Unbekannt {unit_id}]"

    def _make_id(self, text: str) -> int:
        """Return a stable integer ID based on a text key."""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        return int(digest, 16)

    def generate(self):
        questions = []
        for name in self.question_generators:
            func = getattr(self, name)
            q = func()
            if q:
                questions.append(q)

        if not questions:
            logger.warning("[WCRQuestionProvider] Keine gültige Frage generiert.")
            return None

        question = random.choice(questions)
        logger.info(f"[WCRQuestionProvider] Generated: {question['frage']}")
        return question

    def generate_all_types(self) -> list[dict]:
        """Generate one question for every available type."""
        return super().generate_all_types()

    def generate_type_1(self):
        talents = []
        for unit in self.units:
            for lang_data in self.locals.values():
                unit_loc = next(
                    (u for u in lang_data["units"] if u["id"] == unit["id"]), None
                )
                if not unit_loc:
                    continue
                for talent in unit_loc.get("talents", []):
                    talents.append(
                        {"talent_name": talent["name"], "unit_name": unit_loc["name"]}
                    )
        if not talents:
            return None
        pick = random.choice(talents)
        template = self.templates.get(self.language, {}).get("type_1")
        if not template:
            return None
        question_text = template.format(talent_name=pick["talent_name"])
        correct = [
            t["unit_name"] for t in talents if t["talent_name"] == pick["talent_name"]
        ]
        return {
            "frage": question_text,
            "antwort": create_permutations_list(correct),
            "category": "Mechanik",
            "id": self._make_id(f"type1:{self.language}:{pick['talent_name']}"),
        }

    def generate_type_2(self):
        talents = []
        for lang_data in self.locals.values():
            for unit in lang_data.get("units", []):
                for talent in unit.get("talents", []):
                    talents.append(
                        {
                            "talent_name": talent["name"],
                            "talent_description": talent["description"],
                        }
                    )
        if not talents:
            return None
        pick = random.choice(talents)
        template = self.templates.get(self.language, {}).get("type_2")
        if not template:
            return None
        question_text = template.format(talent_description=pick["talent_description"])
        correct = [
            t["talent_name"]
            for t in talents
            if t["talent_description"] == pick["talent_description"]
        ]
        return {
            "frage": question_text,
            "antwort": create_permutations_list(correct),
            "category": "Mechanik",
            "id": self._make_id(f"type2:{self.language}:{pick['talent_description']}"),
        }

    def generate_type_3(self):
        if not self.units:
            return None
        unit = random.choice(self.units)
        template = self.templates.get(self.language, {}).get("type_3")
        if not template:
            return None
        question_text = template.format(
            unit_name=self.get_unit_name(unit["id"], self.language)
        )
        faction_id = unit.get("faction_id")
        factions = (
            self.locals.get(self.language, {}).get("categories", {}).get("factions", [])
        )
        faction = next((f["name"] for f in factions if f["id"] == faction_id), None)
        if not faction:
            return None
        return {
            "frage": question_text,
            "antwort": create_permutations_list([faction]),
            "category": "Franchise",
            "id": self._make_id(f"type3:{self.language}:{unit['id']}"),
        }

    def generate_type_4(self):
        if not self.units:
            return None
        unit = random.choice(self.units)
        template = self.templates.get(self.language, {}).get("type_4")
        if not template:
            return None
        cost = unit.get("cost")
        if cost is None:
            return None
        question_text = template.format(
            unit_name=self.get_unit_name(unit["id"], self.language)
        )
        return {
            "frage": question_text,
            "antwort": create_permutations_list([str(cost)]),
            "category": "Mechanik",
            "id": self._make_id(f"type4:{self.language}:{unit['id']}"),
        }

    def generate_type_5(self):
        stat_keys = ["health", "damage", "attack_speed", "dps"]
        stat = random.choice(stat_keys)
        units_with_stat = [
            u for u in self.units if u.get("stats", {}).get(stat) is not None
        ]
        if len(units_with_stat) < 2:
            return None
        u1, u2 = random.sample(units_with_stat, 2)
        template = self.templates.get(self.language, {}).get("type_5")
        if not template:
            return None
        v1 = u1.get("stats", {}).get(stat)
        v2 = u2.get("stats", {}).get(stat)
        if v1 is None or v2 is None:
            return None
        winners = (
            [self.get_unit_name(u1["id"], self.language)]
            if v1 > v2
            else (
                [self.get_unit_name(u2["id"], self.language)]
                if v2 > v1
                else [
                    self.get_unit_name(u1["id"], self.language),
                    self.get_unit_name(u2["id"], self.language),
                ]
            )
        )
        question_text = template.format(
            stat_label=stat,
            unit1=self.get_unit_name(u1["id"], self.language),
            unit2=self.get_unit_name(u2["id"], self.language),
        )
        return {
            "frage": question_text,
            "antwort": create_permutations_list(winners),
            "category": "Mechanik",
            "id": self._make_id(
                f"type5:{self.language}:{min(u1['id'], u2['id'])}:{max(u1['id'], u2['id'])}:{stat}"
            ),
        }


def get_provider(bot, language):
    return WCRQuestionProvider(bot, language=language)
