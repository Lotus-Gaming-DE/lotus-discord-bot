# cogs/quiz_cog.py
import discord
from discord.ext import commands, tasks
import json
import random
import logging
import os

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.SCORES_FILE = './data/scores.json'
        self.QUESTIONS_FILE = './data/questions.json'
        self.ASKED_QUESTIONS_FILE = './data/asked_questions.json'
        self.user_scores = self.load_scores()
        self.questions_by_area = self.load_questions()
        self.current_questions = {}  # Speichert die aktuellen Fragen pro Bereich
        self.areas_config = {
            'wcr': {
                'channel_id': 123456789012345678,  # Ersetze mit deiner Kanal-ID
                'interval_hours': 0.1,
            },
            'd4': {
                'channel_id': 123456789012345678,  # Ersetze mit deiner Kanal-ID
                'interval_hours': 0.1,
            },
            # Weitere Bereiche hinzufügen
        }
        for area in self.areas_config:
            self.start_quiz_task(area)

    def load_scores(self):
        if os.path.exists(self.SCORES_FILE):
            with open(self.SCORES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {}

    def save_scores(self):
        with open(self.SCORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.user_scores, f, ensure_ascii=False, indent=4)

    def load_questions(self):
        try:
            with open(self.QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                questions_by_area = json.load(f)
        except FileNotFoundError:
            logger.error(
                f"Die Datei {self.QUESTIONS_FILE} wurde nicht gefunden.")
            questions_by_area = {}
        return questions_by_area

    def get_asked_questions(self, area, category):
        if os.path.exists(self.ASKED_QUESTIONS_FILE):
            with open(self.ASKED_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                asked_questions = json.load(f)
        else:
            asked_questions = {}
        return asked_questions.get(area, {}).get(category, [])

    def mark_question_as_asked(self, area, category, question_text):
        if os.path.exists(self.ASKED_QUESTIONS_FILE):
            with open(self.ASKED_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                asked_questions = json.load(f)
        else:
            asked_questions = {}

        if area not in asked_questions:
            asked_questions[area] = {}
        if category not in asked_questions[area]:
            asked_questions[area][category] = []

        asked_questions[area][category].append(question_text)

        with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(asked_questions, f, ensure_ascii=False, indent=4)

    def reset_asked_questions(self, area, category):
        if os.path.exists(self.ASKED_QUESTIONS_FILE):
            with open(self.ASKED_QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                asked_questions = json.load(f)
        else:
            asked_questions = {}

        if area in asked_questions and category in asked_questions[area]:
            asked_questions[area][category] = []

        with open(self.ASKED_QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(asked_questions, f, ensure_ascii=False, indent=4)

    def start_quiz_task(self, area):
        config = self.areas_config[area]
        interval = config['interval_hours']

        @tasks.loop(hours=interval)
        async def quiz_loop():
            await self.run_quiz(area)

        @quiz_loop.before_loop
        async def before_quiz():
            await self.bot.wait_until_ready()

        quiz_loop.start()

    async def run_quiz(self, area):
        config = self.areas_config[area]
        channel = self.bot.get_channel(config['channel_id'])
        if channel is None:
            logger.error(f"Konnte Kanal mit ID {
                         config['channel_id']} nicht finden.")
            return

        area_questions = self.questions_by_area.get(area)
        if not area_questions:
            logger.error(f"Keine Fragen für den Bereich '{area}' gefunden.")
            return

        # Auswahl einer Kategorie
        category = random.choice(list(area_questions.keys()))
        category_questions = area_questions[category]

        # Hole die Liste der bereits gestellten Fragen für diesen Bereich und Kategorie
        asked_questions = self.get_asked_questions(area, category)

        # Filtere die Fragen, die noch nicht gestellt wurden
        remaining_questions = [
            q for q in category_questions if q['frage'] not in asked_questions]

        if not remaining_questions:
            # Alle Fragen in dieser Kategorie wurden gestellt, zurücksetzen
            self.reset_asked_questions(area, category)
            remaining_questions = category_questions.copy()

        frage = random.choice(remaining_questions)

        # Markiere die Frage als gestellt
        self.mark_question_as_asked(area, category, frage['frage'])

        # Speichere die aktuelle Frage für diesen Bereich
        self.current_questions[area] = frage

        question_message = await channel.send(f"**Kategorie: {category}**\n{frage['frage']}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or message.author.bot:
            return  # Ignoriere Nachrichten vom Bot selbst und anderen Bots

        # Überprüfe, ob die Nachricht in einem der Quiz-Kanäle gesendet wurde
        for area, config in self.areas_config.items():
            if message.channel.id == config['channel_id']:
                current_question = self.current_questions.get(area)
                if current_question:
                    richtige_antworten = current_question['antworten']
                    if message.content.lower() in [ans.lower() for ans in richtige_antworten]:
                        await message.channel.send(f"Glückwunsch {message.author.mention}, das ist korrekt!")
                        logger.info(
                            f"{message.author} hat die richtige Antwort gegeben.")
                        # Punkte hinzufügen
                        user_id = str(message.author.id)
                        self.user_scores.setdefault(user_id, 0)
                        self.user_scores[user_id] += 1
                        self.save_scores()
                        # Aktuelle Frage entfernen
                        self.current_questions[area] = None
                    else:
                        # Optionale Rückmeldung bei falscher Antwort
                        pass
                break  # Wir haben den passenden Bereich gefunden, weitere Iteration nicht nötig


async def setup(bot):
    await bot.add_cog(QuizCog(bot))
