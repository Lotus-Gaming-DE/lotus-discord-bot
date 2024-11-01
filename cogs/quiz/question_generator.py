# cogs/quiz/question_generator.py
import random


class QuestionGenerator:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.questions_by_area = self.data_loader.load_questions()

    def generate_question(self):
        area = 'wcr'  # Beschränkung auf den Bereich "WCR"
        category = "Mechanik"

        if area not in self.questions_by_area or category not in self.questions_by_area[area]:
            raise ValueError(f"Keine Fragen für den Bereich '{
                             area}' und Kategorie '{category}' gefunden.")

        # Auswahl einer zufälligen Frage aus dem "Mechanik"-Bereich
        question_data = random.choice(self.questions_by_area[area][category])

        # Frage und mögliche Antworten aus den Daten extrahieren
        question_text = question_data['frage']
        correct_answer = question_data['antwort']

        return {
            "frage": question_text,
            # Antwort als Liste mit Kleinbuchstaben für Flexibilität
            "antwort": [correct_answer.lower()]
        }
