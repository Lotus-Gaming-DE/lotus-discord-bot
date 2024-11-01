import json
import os


class DataLoader:
    QUESTIONS_FILE = './data/questions.json'
    SCORES_FILE = './data/scores.json'
    ASKED_QUESTIONS_FILE = './data/asked_questions.json'

    def load_questions(self):
        if os.path.exists(self.QUESTIONS_FILE):
            with open(self.QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def load_scores(self):
        if os.path.exists(self.SCORES_FILE):
            with open(self.SCORES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_scores(self, scores):
        with open(self.SCORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(scores, f, ensure_ascii=False, indent=4)

    def load_asked_questions(self):
        if os.path.exists(self.ASKED_QUESTIONS_FILE):
            with open(self.ASKED_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def mark_question_as_asked(self, area, question_text):
        asked_questions = self.load_asked_questions()
        if area not in asked_questions:
            asked_questions[area] = []
        asked_questions[area].append(question_text)

        with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(asked_questions, f, ensure_ascii=False, indent=4)

    def reset_asked_questions(self, area):
        asked_questions = self.load_asked_questions()
        if area in asked_questions:
            asked_questions[area] = []

        with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(asked_questions, f, ensure_ascii=False, indent=4)
