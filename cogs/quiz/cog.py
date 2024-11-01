import discord
from discord.ext import commands, tasks
import logging
import random
from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .utils import check_answer

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_loader = DataLoader()
        self.question_generator = QuestionGenerator(self.data_loader)
        self.current_questions = {}

        # WCR-Spezifische Logik für dynamisch generierte Fragen
        self.recent_wcr_questions = []

        # Konfiguration der Areas mit Channel-ID und Intervall in Stunden
        self.areas_config = {
            'wcr': {
                'channel_id': 1290804058281607189,  # Beispiel ID ersetzen
                'interval_hours': 0.1,
            },
            'd4': {
                'channel_id': 1290804058281607189,  # Beispiel ID ersetzen
                'interval_hours': 0.1,
            },
            # Weitere Areas können hier hinzugefügt werden
        }

        # Start der Quiz-Timer für alle konfigurierten Areas
        for area in self.areas_config:
            self.start_quiz_task(area)

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

        if area == 'wcr':
            question_data = self.generate_unique_wcr_question()
        else:
            question_data = self.generate_unique_question(area)

        if question_data:
            question_text, correct_answers = question_data['frage'], question_data['antwort']
            self.current_questions[area] = correct_answers
            await channel.send(f"**Quizfrage für {area}:** {question_text}")

    def generate_unique_question(self, area):
        area_questions = self.data_loader.load_questions().get(area, {})

        if not area_questions:
            logger.error(f"Keine Fragen für den Bereich '{area}' gefunden.")
            return None

        # Auswahl einer Kategorie
        category = random.choice(list(area_questions.keys()))
        category_questions = area_questions[category]
        asked_questions = self.data_loader.load_asked_questions().get(area, [])

        remaining_questions = [
            q for q in category_questions if q['frage'] not in asked_questions
        ]

        if not remaining_questions:
            # Alle Fragen wurden einmal gestellt, zurücksetzen
            self.data_loader.reset_asked_questions(area)
            remaining_questions = category_questions.copy()

        question = random.choice(remaining_questions)
        self.data_loader.mark_question_as_asked(area, question['frage'])
        return question

    def generate_unique_wcr_question(self):
        question_data = self.question_generator.generate_question()
        question_text = question_data['frage']

        if question_text in self.recent_wcr_questions:
            # Erneut generieren, um Dopplung zu vermeiden
            return self.generate_unique_wcr_question()

        # Speichert die Frage und entfernt die älteste, wenn mehr als 10 Fragen gespeichert sind
        self.recent_wcr_questions.append(question_text)
        if len(self.recent_wcr_questions) > 10:
            self.recent_wcr_questions.pop(0)

        return question_data

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return  # Ignoriere Nachrichten von Bots

        # Prüfen, ob die Nachricht in einem Quiz-Channel gesendet wurde
        for area, config in self.areas_config.items():
            if message.channel.id == config['channel_id']:
                correct_answers = self.current_questions.get(area)
                if correct_answers and check_answer(message.content, correct_answers):
                    await message.channel.send(f"Richtig, {message.author.mention}!")
                    logger.info(
                        f"{message.author} hat die richtige Antwort gegeben.")
                    # Entferne die aktuelle Frage, nachdem sie beantwortet wurde
                    del self.current_questions[area]
                break  # Bereich gefunden, weitere Iteration nicht nötig
