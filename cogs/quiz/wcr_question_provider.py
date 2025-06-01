import random
import logging
from .utils import create_permutations_list

logger = logging.getLogger(__name__)


class WCRQuestionProvider:
    def __init__(self, units, locals_data, language="de"):
        self.units = units
        self.locals = locals_data
        self.language = language

    def get_unit_name(self, unit_id: int, lang: str) -> str:
        try:
            units = self.locals.get(lang, {}).get("units", [])
            return next((u["name"] for u in units if u["id"] == unit_id), f"[Unbekannt {unit_id}]")
        except Exception:
            return f"[Unbekannt {unit_id}]"

    def generate(self):
        types = [
            self.generate_type_1,
            self.generate_type_2,
            self.generate_type_3,
            self.generate_type_4,
            self.generate_type_5,
        ]
        for _ in range(10):
            func = random.choice(types)
            q = func()
            if q:
                logger.info(f"[WCRQuestionProvider] Generated: {q['frage']}")
                return q
        logger.warning(
            "[WCRQuestionProvider] Failed to generate question after 10 attempts.")
        return None

    def generate_type_1(self):
        talents = []
        for unit in self.units:
            for lang_data in self.locals.values():
                unit_loc = next(
                    (u for u in lang_data["units"] if u["id"] == unit["id"]), None)
                if not unit_loc:
                    continue
                for talent in unit_loc.get("talents", []):
                    talents.append(
                        {"talent_name": talent["name"], "unit_name": unit_loc["name"]})
        if not talents:
            return None
        pick = random.choice(talents)
        template = self.locals.get(self.language, {}).get(
            "question_templates", {}).get("type_1")
        if not template:
            return None
        question_text = template.format(talent_name=pick["talent_name"])
        correct = [t["unit_name"]
                   for t in talents if t["talent_name"] == pick["talent_name"]]
        return {
            "frage": question_text,
            "antwort": create_permutations_list(correct),
            "category": "Mechanik"
        }

    def generate_type_2(self):
        talents = []
        for lang_data in self.locals.values():
            for unit in lang_data.get("units", []):
                for talent in unit.get("talents", []):
                    talents.append({
                        "talent_name": talent["name"],
                        "talent_description": talent["description"],
                    })
        if not talents:
            return None
        pick = random.choice(talents)
        template = self.locals.get(self.language, {}).get(
            "question_templates", {}).get("type_2")
        if not template:
            return None
        question_text = template.format(
            talent_description=pick["talent_description"])
        correct = [t["talent_name"]
                   for t in talents if t["talent_description"] == pick["talent_description"]]
        return {
            "frage": question_text,
            "antwort": create_permutations_list(correct),
            "category": "Mechanik"
        }

    def generate_type_3(self):
        if not self.units:
            return None
        unit = random.choice(self.units)
        template = self.locals.get(self.language, {}).get(
            "question_templates", {}).get("type_3")
        if not template:
            return None
        question_text = template.format(
            unit_name=self.get_unit_name(unit["id"], self.language))
        faction = unit.get("faction")
        if not faction:
            return None
        return {
            "frage": question_text,
            "antwort": create_permutations_list([faction]),
            "category": "Franchise"
        }

    def generate_type_4(self):
        if not self.units:
            return None
        unit = random.choice(self.units)
        template = self.locals.get(self.language, {}).get(
            "question_templates", {}).get("type_4")
        if not template:
            return None
        cost = unit.get("cost")
        if cost is None:
            return None
        question_text = template.format(
            unit_name=self.get_unit_name(unit["id"], self.language))
        return {
            "frage": question_text,
            "antwort": create_permutations_list([str(cost)]),
            "category": "Mechanik"
        }

    def generate_type_5(self):
        if len(self.units) < 2:
            return None
        u1, u2 = random.sample(self.units, 2)
        stat_keys = ["health", "damage", "attack_speed", "dps"]
        stat = random.choice(stat_keys)
        template = self.locals.get(self.language, {}).get(
            "question_templates", {}).get("type_5")
        if not template:
            return None
        v1, v2 = u1.get(stat), u2.get(stat)
        if v1 is None or v2 is None:
            return None
        winners = [self.get_unit_name(u1["id"], self.language)] if v1 > v2 else [
            self.get_unit_name(u2["id"], self.language)] if v2 > v1 else [
            self.get_unit_name(u1["id"], self.language),
            self.get_unit_name(u2["id"], self.language)]
        question_text = template.format(
            stat_label=stat,
            unit1=self.get_unit_name(u1["id"], self.language),
            unit2=self.get_unit_name(u2["id"], self.language)
        )
        return {
            "frage": question_text,
            "antwort": create_permutations_list(winners),
            "category": "Mechanik"
        }
