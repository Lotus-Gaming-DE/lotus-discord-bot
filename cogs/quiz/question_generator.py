import random
import logging
from .utils import create_permutations_list

logger = logging.getLogger(__name__)  # z.B. "cogs.quiz.question_generator"


class QuestionGenerator:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.questions_by_area = data_loader.questions_by_area
        self.wcr_units = data_loader.wcr_units
        self.wcr_locals = data_loader.wcr_locals
        self.language = data_loader.language
        logger.info("QuestionGenerator initialized.")

    def get_unit_name(self, unit_id: int, lang: str) -> str:
        """Gibt den Namen einer Einheit basierend auf Sprache und ID zurück."""
        try:
            units = self.wcr_locals.get(lang, {}).get("units", [])
            return next((u["name"] for u in units if u["id"] == unit_id), f"[Unbekannt {unit_id}]")
        except Exception:
            return f"[Unbekannt {unit_id}]"

    def generate_question_from_json(self, area):
        area_questions = self.questions_by_area.get(area)
        if not area_questions:
            logger.error(
                f"[QuestionGenerator] Area '{area}' not found in loaded questions.")
            return None

        category = random.choice(list(area_questions.keys()))
        category_questions = area_questions[category]
        asked = self.data_loader.load_asked_questions().get(area, [])
        remaining = [q for q in category_questions if q["id"] not in asked]

        if not remaining:
            self.data_loader.reset_asked_questions(area)
            remaining = category_questions.copy()
            logger.info(
                f"[QuestionGenerator] All questions asked for area '{area}'. Resetting.")

        question_data = random.choice(remaining)
        self.data_loader.mark_question_as_asked(area, question_data["id"])

        logger.info(
            f"[QuestionGenerator] Generated question for area '{area}', category '{category}': {question_data['frage']}")
        return {
            "frage": question_data["frage"],
            "antwort": create_permutations_list([question_data["antwort"]]),
            "category": category,
            "id": question_data["id"],
        }

    def generate_dynamic_wcr_question(self):
        types = [
            self.generate_question_type_1,
            self.generate_question_type_2,
            self.generate_question_type_3,
            self.generate_question_type_4,
            self.generate_question_type_5,
        ]
        for attempt in range(10):
            func = random.choice(types)
            q = func()
            if q:
                logger.info(
                    f"[QuestionGenerator] Generated dynamic WCR question: {q['frage']}")
                return q
        logger.warning(
            "[QuestionGenerator] Failed to generate dynamic WCR question after 10 attempts.")
        return None

    def generate_question_type_1(self):
        units = self.wcr_units
        locals_data = self.wcr_locals
        talents = []

        for unit in units:
            for lang_code, lang_data in locals_data.items():
                unit_loc = next(
                    (u for u in lang_data["units"] if u["id"] == unit["id"]), None)
                if not unit_loc:
                    continue
                for talent in unit_loc.get("talents", []):
                    talents.append({
                        "talent_name": talent["name"],
                        "unit_name": unit_loc["name"],
                    })

        if not talents:
            logger.warning(
                "[QuestionGenerator] No talents found for type_1 question.")
            return None

        pick = random.choice(talents)
        template = self.wcr_locals.get(self.language, {}).get(
            "question_templates", {}).get("type_1")
        if not template:
            logger.error(
                f"[QuestionGenerator] Missing template 'type_1' for language '{self.language}'.")
            return None

        question_text = template.format(talent_name=pick["talent_name"])
        correct = [u["unit_name"]
                   for u in talents if u["talent_name"] == pick["talent_name"]]
        answers = create_permutations_list(correct)

        return {
            "frage": question_text,
            "antwort": answers,
            "category": "Mechanik",
        }

    def generate_question_type_2(self):
        talents = []
        for lang_data in self.wcr_locals.values():
            for unit in lang_data.get("units", []):
                for talent in unit.get("talents", []):
                    talents.append({
                        "talent_name": talent["name"],
                        "talent_description": talent["description"],
                    })

        if not talents:
            logger.warning(
                "[QuestionGenerator] No talents found for type_2 question.")
            return None

        pick = random.choice(talents)
        template = self.wcr_locals.get(self.language, {}).get(
            "question_templates", {}).get("type_2")
        if not template:
            logger.error(
                f"[QuestionGenerator] Missing template 'type_2' for language '{self.language}'.")
            return None

        question_text = template.format(
            talent_description=pick["talent_description"])
        correct = [t["talent_name"]
                   for t in talents if t["talent_description"] == pick["talent_description"]]
        answers = create_permutations_list(correct)

        return {
            "frage": question_text,
            "antwort": answers,
            "category": "Mechanik",
        }

    def generate_question_type_3(self):
        if not self.wcr_units:
            logger.warning(
                "[QuestionGenerator] No units found for type_3 question.")
            return None

        unit = random.choice(self.wcr_units)
        template = self.wcr_locals.get(self.language, {}).get(
            "question_templates", {}).get("type_3")
        if not template:
            logger.error(
                f"[QuestionGenerator] Missing template 'type_3' for language '{self.language}'.")
            return None

        question_text = template.format(
            unit_name=self.get_unit_name(unit["id"], self.language))
        faction = unit.get("faction")
        if not faction:
            logger.warning(
                f"[QuestionGenerator] Unit '{unit['id']}' has no faction.")
            return None

        answers = create_permutations_list([faction])
        return {
            "frage": question_text,
            "antwort": answers,
            "category": "Franchise",
        }

    def generate_question_type_4(self):
        if not self.wcr_units:
            logger.warning(
                "[QuestionGenerator] No units found for type_4 question.")
            return None

        unit = random.choice(self.wcr_units)
        template = self.wcr_locals.get(self.language, {}).get(
            "question_templates", {}).get("type_4")
        if not template:
            logger.error(
                f"[QuestionGenerator] Missing template 'type_4' for language '{self.language}'.")
            return None

        question_text = template.format(
            unit_name=self.get_unit_name(unit["id"], self.language))
        cost = unit.get("cost")
        if cost is None:
            logger.warning(
                f"[QuestionGenerator] Unit '{unit['id']}' has no cost info.")
            return None

        answers = create_permutations_list([str(cost)])
        return {
            "frage": question_text,
            "antwort": answers,
            "category": "Mechanik",
        }

    def generate_question_type_5(self):
        if len(self.wcr_units) < 2:
            logger.warning(
                "[QuestionGenerator] Not enough units for type_5 question.")
            return None

        u1, u2 = random.sample(self.wcr_units, 2)
        stat_keys = ["health", "damage", "attack_speed", "dps"]
        stat = random.choice(stat_keys)

        template = self.wcr_locals.get(self.language, {}).get(
            "question_templates", {}).get("type_5")
        if not template:
            logger.error(
                f"[QuestionGenerator] Missing template 'type_5' for language '{self.language}'.")
            return None

        name1 = self.get_unit_name(u1["id"], self.language)
        name2 = self.get_unit_name(u2["id"], self.language)
        question_text = template.format(
            stat_label=stat, unit1=name1, unit2=name2)

        v1 = u1.get(stat)
        v2 = u2.get(stat)
        if v1 is None or v2 is None:
            logger.warning(f"[QuestionGenerator] Units missing stat '{stat}'.")
            return None

        if v1 > v2:
            winners = [name1]
        elif v2 > v1:
            winners = [name2]
        else:
            winners = [name1, name2]

        answers = create_permutations_list(winners)
        return {
            "frage": question_text,
            "antwort": answers,
            "category": "Mechanik",
        }
