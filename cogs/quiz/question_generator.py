# cogs/quiz/question_generator.py

import random
import logging
from .utils import create_permutations_list

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.questions_by_area = self.data_loader.questions_by_area
        self.wcr_units = self.data_loader.wcr_units
        self.wcr_locals = self.data_loader.wcr_locals
        self.language = self.data_loader.language  # Aktuelle Sprache
        logger.info("QuestionGenerator initialized.")

    def generate_question_from_json(self, area):
        """Generiert eine Frage aus der entsprechenden questions-Datei für den angegebenen Bereich."""
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
            q for q in category_questions if q['id'] not in asked_questions
        ]

        if not remaining_questions:
            # Alle Fragen wurden gestellt, zurücksetzen
            self.data_loader.reset_asked_questions(area)
            remaining_questions = category_questions.copy()
            logger.info(f"All questions have been asked for area '{
                        area}'. Resetting asked questions.")

        question_data = random.choice(remaining_questions)
        self.data_loader.mark_question_as_asked(area, question_data['id'])
        logger.info(f"Generated question for area '{area}', category '{
                    category}': {question_data['frage']}")
        return {
            "frage": question_data['frage'],
            "antwort": create_permutations_list([question_data['antwort']]),
            "category": category,
            "id": question_data['id']
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
                    (u for u in lang_data['units']
                     if u['id'] == unit['id']), None
                )
                if unit_locals:
                    for talent in unit_locals.get('talents', []):
                        talents.append({
                            'talent_name': talent['name'],
                            'unit_name': unit_locals['name']
                        })
        if not talents:
            logger.warning("No talents found to generate type_1 question.")
            return None
        talent_info = random.choice(talents)

        # Sprache berücksichtigen
        language = self.data_loader.language
        try:
            template = self.wcr_locals[language]['question_templates']['type_1']
            question_text = template.format(
                talent_name=talent_info['talent_name'])
        except KeyError as e:
            logger.error(f"Missing template for type_1 in language '{
                         language}': {e}")
            return None

        # Korrekte Antworten aus der aktuellen Sprache sammeln
        correct_answers = []
        for unit in units:
            for lang_code, lang_data in locals_data.items():
                unit_locals = next(
                    (u for u in lang_data['units']
                     if u['id'] == unit['id']), None
                )
                if unit_locals and any(talent['name'] == talent_info['talent_name'] for talent in unit_locals.get('talents', [])):
                    correct_answers.append(unit_locals['name'])
        correct_answers = create_permutations_list(correct_answers)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Mechanik'
        }

    def generate_question_type_2(self):
        """Fragetyp 2: [Talentbeschreibung] - Welches Talent ist gesucht?"""
        locals_data = self.wcr_locals
        talents = []
        for lang_code, lang_data in locals_data.items():
            for unit in lang_data.get('units', []):
                for talent in unit.get('talents', []):
                    talents.append({
                        'talent_name': talent['name'],
                        'talent_description': talent['description']
                    })
        if not talents:
            logger.warning("No talents found to generate type_2 question.")
            return None
        talent_info = random.choice(talents)

        # Sprache berücksichtigen
        language = self.data_loader.language
        try:
            template = self.wcr_locals[language]['question_templates']['type_2']
            question_text = template.format(
                talent_description=talent_info['talent_description'])
        except KeyError as e:
            logger.error(f"Missing template for type_2 in language '{
                         language}': {e}")
            return None

        # Korrekte Antworten sammeln
        correct_answers = [
            t['talent_name'] for t in talents if t['talent_description'] == talent_info['talent_description']
        ]
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
        if not units:
            logger.warning("No units found to generate type_3 question.")
            return None
        unit = random.choice(units)

        # Sprache berücksichtigen
        language = self.data_loader.language
        try:
            template = self.wcr_locals[language]['question_templates']['type_3']
            question_text = template.format(unit_name=unit['name'])
        except KeyError as e:
            logger.error(f"Missing template for type_3 in language '{
                         language}': {e}")
            return None

        # Korrekte Antwort sammeln
        faction = unit.get('faction')
        if not faction:
            logger.warning(
                f"Unit '{unit['name']}' has no faction information.")
            return None
        correct_answers = [faction]
        correct_answers = create_permutations_list(correct_answers)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Franchise'
        }

    def generate_question_type_4(self):
        """Fragetyp 4: Wie viel Gold kostet es, den Mini [Mininame] zu spielen?"""
        units = self.wcr_units
        locals_data = self.wcr_locals
        if not units:
            logger.warning("No units found to generate type_4 question.")
            return None
        unit = random.choice(units)

        # Sprache berücksichtigen
        language = self.data_loader.language
        try:
            template = self.wcr_locals[language]['question_templates']['type_4']
            question_text = template.format(unit_name=unit['name'])
        except KeyError as e:
            logger.error(f"Missing template for type_4 in language '{
                         language}': {e}")
            return None

        # Korrekte Antwort sammeln
        cost = unit.get('cost')
        if cost is None:
            logger.warning(f"Unit '{unit['name']}' has no cost information.")
            return None
        correct_answers = [str(cost)]
        correct_answers = create_permutations_list(correct_answers)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Mechanik'
        }

    def generate_question_type_5(self):
        """Fragetyp 5: Welches Mini hat mehr [Statlabel], [Mininame1] oder [Mininame2]?"""
        units = self.wcr_units
        locals_data = self.wcr_locals
        if len(units) < 2:
            logger.warning("Not enough units to generate type_5 question.")
            return None
        unit1, unit2 = random.sample(units, 2)

        # Auswahl eines zufälligen Statlabels
        stat_labels = ['health', 'damage',
                       'attack_speed', 'dps']  # Beispielstatistiken
        stat_label = random.choice(stat_labels)

        # Sprache berücksichtigen
        language = self.data_loader.language
        try:
            template = self.wcr_locals[language]['question_templates']['type_5']
            question_text = template.format(
                stat_label=stat_label,
                unit1=unit1['name'],
                unit2=unit2['name']
            )
        except KeyError as e:
            logger.error(f"Missing template for type_5 in language '{
                         language}': {e}")
            return None

        # Korrekte Antwort bestimmen
        stat1 = unit1.get(stat_label)
        stat2 = unit2.get(stat_label)
        if stat1 is None or stat2 is None:
            logger.warning(f"One of the units '{unit1['name']}' or '{
                           unit2['name']}' lacks '{stat_label}' information.")
            return None

        if stat1 > stat2:
            correct_answers = [unit1['name']]
        elif stat2 > stat1:
            correct_answers = [unit2['name']]
        else:
            correct_answers = [unit1['name'], unit2['name']]  # Beide gleich

        correct_answers = create_permutations_list(correct_answers)
        return {
            'frage': question_text,
            'antwort': correct_answers,
            'category': 'Mechanik'
        }

    # Weitere Fragetypen können hier hinzugefügt werden
