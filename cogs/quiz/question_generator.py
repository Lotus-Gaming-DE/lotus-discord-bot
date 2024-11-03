# cogs/quiz/question_generator.py
import random
import logging
from .data_loader import DataLoader
from .utils import create_permutations_list

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.questions_by_area = self.data_loader.questions_by_area
        self.wcr_units = self.data_loader.wcr_units
        self.wcr_locals = self.data_loader.wcr_locals
        logger.info("QuestionGenerator initialized.")

    def generate_question_from_json(self, area):
        """Generiert eine Frage aus questions.json für den angegebenen Bereich."""
        area_questions = self.questions_by_area.get(area)
        if not area_questions:
            logger.error(f"Area '{area}' not found in loaded questions.")
            return None

        # Wähle eine Kategorie zufällig aus
        category = random.choice(list(area_questions.keys()))
        category_questions = area_questions[category]

        # Gestellte Fragen laden
        asked_questions = self.data_loader.load_asked_questions().get(area, [])

        # Filtere bereits gestellte Fragen
        remaining_questions = [
            q for q in category_questions if q['frage'] not in asked_questions]

        if not remaining_questions:
            # Alle Fragen wurden gestellt, zurücksetzen
            self.data_loader.reset_asked_questions(area)
            remaining_questions = category_questions.copy()
            logger.info(f"All questions have been asked for area '{
                        area}'. Resetting asked questions.")

        question_data = random.choice(remaining_questions)
        self.data_loader.mark_question_as_asked(area, question_data['frage'])
        logger.info(f"Generated question for area '{area}', category '{
                    category}': {question_data['frage']}")
        return {
            "frage": question_data['frage'],
            "antwort": create_permutations_list([question_data['antwort']]),
            "category": category
        }

    def generate_dynamic_wcr_question(self):
        """Generiert eine dynamische WCR-Frage gemäß den angegebenen Vorlagen."""
        question_types = [
            self.generate_question_type_1,
            self.generate_question_type_2,
            self.generate_question_type_3,
            self.generate_question_type_4,
            self.generate_question_type_5
        ]

        max_attempts = 10
        for attempt in range(max_attempts):
            question_func = random.choice(question_types)
            question_data = question_func()
            if question_data:
                logger.info(f"Generated dynamic WCR question: {
                            question_data['frage']}")
                return question_data
        logger.warning("Failed to generate dynamic WCR question.")
        return None

    def generate_question_type_1(self):
        """Fragetyp 1: Welches Mini kann das Talent [Talentname] erlernen?"""
        units = self.wcr_units
        locals_data = self.wcr_locals
        talents = []
        for unit in units:
            for lang_code, lang_data in locals_data.items():
                unit_locals = next(
                    (u for u in lang_data['units'] if u['id'] == unit['id']), None)
                if unit_locals:
                    for talent in unit_locals.get('talents', []):
                        talents.append({
                            'talent_name': talent['name'],
                            'unit_name': unit_locals['name']
                        })
        if not talents:
            return None
        talent_info = random.choice(talents)
        question_text = f"Welches Mini kann das Talent '{
            talent_info['talent_name']}' erlernen?"
        # Korrekte Antworten aus allen Sprachen sammeln
        correct_answers = []
        for lang_data in locals_data.values():
            for unit in lang_data['units']:
                if any(talent['name'] == talent_info['talent_name'] for talent in unit.get('talents', [])):
                    correct_answers.append(unit['name'])
        correct_answers = create_permutations_list(correct_answers)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Mechanik'
        }

    # Die anderen Fragegeneratoren werden ähnlich angepasst, um Antworten aus allen Sprachen zu berücksichtigen

    def generate_question_type_2(self):
        """Fragetyp 2: [Talentbeschreibung] - Welches Talent ist gesucht?"""
        locals_data = self.wcr_locals
        talents = []
        for lang_data in locals_data.values():
            for unit in lang_data.get('units', []):
                for talent in unit.get('talents', []):
                    talents.append({
                        'talent_name': talent['name'],
                        'talent_description': talent['description']
                    })
        if not talents:
            return None
        talent_info = random.choice(talents)
        question_text = f"\"{
            talent_info['talent_description']}\" - Welches Talent ist gesucht?"
        # Korrekte Antworten aus allen Sprachen sammeln
        correct_answers = [t['talent_name']
                           for t in talents if t['talent_description'] == talent_info['talent_description']]
        correct_answers = create_permutations_list(correct_answers)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Mechanik'
        }

    def generate_question_type_3(self):
        """Fragetyp 3: Zu welcher Fraktion gehört der Mini [Mininame]?"""
        units = self.wcr_units
        locals_data = self.wcr_locals
        factions = {}
        for lang_data in locals_data.values():
            for faction in lang_data['categories']['factions']:
                factions.setdefault(faction['id'], []).append(faction['name'])
        unit = random.choice(units)
        unit_names = []
        for lang_data in locals_data.values():
            unit_locals = next(
                (u for u in lang_data['units'] if u['id'] == unit['id']), None)
            if unit_locals:
                unit_names.append(unit_locals['name'])
        faction_names = factions.get(unit['faction_id'], [])
        question_text = f"Zu welcher Fraktion gehört der Mini '{
            unit_names[0]}'?"
        correct_answers = create_permutations_list(faction_names)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Mechanik'
        }

    def generate_question_type_4(self):
        """Fragetyp 4: Wie viel Gold kostet es den Mini [Mininame] zu spielen?"""
        units = self.wcr_units
        locals_data = self.wcr_locals
        unit = random.choice(units)
        unit_names = []
        for lang_data in locals_data.values():
            unit_locals = next(
                (u for u in lang_data['units'] if u['id'] == unit['id']), None)
            if unit_locals:
                unit_names.append(unit_locals['name'])
        cost = unit.get('cost')
        question_text = f"Wie viel Gold kostet es, den Mini '{
            unit_names[0]}' zu spielen?"
        correct_answer = str(cost)
        return {
            'frage': question_text,
            'antwort': [correct_answer],
            'category': 'Mechanik'
        }

    def generate_question_type_5(self):
        """Fragetyp 5: Welches Mini hat mehr [Stat/Statlabel], [Mininame1] oder [Mininame2]?"""
        units = self.wcr_units
        locals_data = self.wcr_locals
        stat_labels = {}
        for lang_data in locals_data.values():
            stat_labels.update(lang_data.get('stat_labels', {}))
        stats_list = ['damage', 'health',
                      'attack_speed', 'range']  # Verfügbare Stats
        stat = random.choice(stats_list)
        stat_label = stat_labels.get(stat, stat.capitalize())
        # Wähle zwei Einheiten, die den gewählten Stat haben
        valid_units = [unit for unit in units if stat in unit.get('stats', {})]
        if len(valid_units) < 2:
            return None
        unit1, unit2 = random.sample(valid_units, 2)
        unit1_names = []
        unit2_names = []
        for lang_data in locals_data.values():
            unit1_locals = next(
                (u for u in lang_data['units'] if u['id'] == unit1['id']), None)
            unit2_locals = next(
                (u for u in lang_data['units'] if u['id'] == unit2['id']), None)
            if unit1_locals:
                unit1_names.append(unit1_locals['name'])
            if unit2_locals:
                unit2_names.append(unit2_locals['name'])
        value1 = unit1['stats'][stat]
        value2 = unit2['stats'][stat]
        if value1 == value2:
            # Bei Gleichstand erneut versuchen
            return None
        if value1 > value2:
            correct_answers = unit1_names
        else:
            correct_answers = unit2_names
        question_text = f"Welches Mini hat mehr {stat_label}, '{
            unit1_names[0]}' oder '{unit2_names[0]}'?"
        correct_answers = create_permutations_list(correct_answers)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Mechanik'
        }
