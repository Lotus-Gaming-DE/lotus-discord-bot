# cogs/quiz/question_generator.py
import random
import logging

logger = logging.getLogger(__name__)


class QuestionGenerator:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.questions_by_area = self.data_loader.load_questions()
        logger.info("Questions loaded and initialized for generator.")

    def generate_question(self):
        area = 'wcr'  # Beschränkung auf den Bereich "WCR"
        category = "Mechanik"

        # Prüfen, ob der Bereich und die Kategorie vorhanden sind
        if area not in self.questions_by_area:
            logger.error(f"Area '{area}' not found in loaded questions.")
            raise ValueError(f"Keine Fragen für den Bereich '{
                             area}' gefunden.")
        if category not in self.questions_by_area[area]:
            logger.error(f"Category '{category}' not found in area '{area}'.")
            raise ValueError(f"Keine Fragen für die Kategorie '{
                             category}' im Bereich '{area}' gefunden.")

        # Auswahl einer zufälligen Frage aus dem "Mechanik"-Bereich
        question_data = random.choice(self.questions_by_area[area][category])
        question_text = question_data.get('frage')
        correct_answer = question_data.get('antwort')

        # Sicherstellen, dass Frage und Antwort vorhanden sind
        if not question_text or not correct_answer:
            logger.error(f"Invalid question data found in area '{
                         area}', category '{category}'. Data: {question_data}")
            raise ValueError("Frage oder Antwort fehlt in den Daten.")

        logger.info(f"Generated question for area '{
                    area}', category '{category}': {question_text}")
        return {
            "frage": question_text,
            # Antwort als Liste mit Kleinbuchstaben für Flexibilität
            "antwort": [correct_answer.lower()]
        }
