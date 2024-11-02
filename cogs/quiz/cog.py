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

        # WCR-spezifische Logik für dynamisch generierte Fragen
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
        logger.info(f"Quiz task for area '{
                    area}' started with interval {interval} hours.")

    async def run_quiz(self, area):
        config = self.areas_config[area]
        channel = self.bot.get_channel(config['channel_id'])
        if channel is None:
            logger.error(f"Channel with ID {
                         config['channel_id']} for area '{area}' not found.")
            return

        logger.info(f"Running quiz for area '{
                    area}' in channel {channel.name}.")

        if area == 'wcr':
            question_data = self.generate_unique_wcr_question()
        else:
            question_data = self.generate_unique_question(area)

        if question_data:
            question_text, correct_answers = question_data['frage'], question_data['antwort']
            self.current_questions[area] = correct_answers
            await channel.send(f"**Quizfrage für {area}:** {question_text}")
            logger.info(f"Question for area '{area}' sent: {question_text}")
        else:
            logger.warning(
                f"No question could be generated for area '{area}'.")

    def generate_unique_question(self, area):
        logger.info(f"Generating unique question for area '{area}'.")

        area_questions = self.data_loader.load_questions().get(area, {})
        if not area_questions:
            logger.error(f"No questions found for area '{area}'.")
            return None

        category = random.choice(list(area_questions.keys()))
        category_questions = area_questions[category]
        asked_questions = self.data_loader.load_asked_questions().get(area, [])

        remaining_questions = [
            q for q in category_questions if q['frage'] not in asked_questions
        ]
        logger.debug(f"Remaining questions for area '{area}': {
                     [q['frage'] for q in remaining_questions]}")

        if not remaining_questions:
            self.data_loader.reset_asked_questions(area)
            remaining_questions = category_questions.copy()
            logger.info(f"All questions have been asked for area '{
                        area}'. Resetting asked questions.")

        question = random.choice(remaining_questions)
        self.data_loader.mark_question_as_asked(area, question['frage'])
        logger.info(f"Selected question for area '{
                    area}': {question['frage']}")
        return question

    def generate_unique_wcr_question(self):
        max_attempts = 20
        logger.info("Generating unique WCR question.")

        for attempt in range(max_attempts):
            question_data = self.question_generator.generate_question()
            question_text = question_data['frage']
            logger.debug(f"Attempt {
                         attempt + 1}/{max_attempts}: Generated WCR question - {question_text}")

            if question_text not in self.recent_wcr_questions:
                self.recent_wcr_questions.append(question_text)
                if len(self.recent_wcr_questions) > 10:
                    removed_question = self.recent_wcr_questions.pop(0)
                    logger.debug(f"Removed oldest question from recent WCR questions: {
                                 removed_question}")
                logger.info(f"Unique WCR question selected: {question_text}")
                return question_data

        logger.warning(
            "Could not generate a unique WCR question after maximum attempts.")
        return None

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
                        f"{message.author} answered correctly for area '{area}'.")
                    del self.current_questions[area]
                break
