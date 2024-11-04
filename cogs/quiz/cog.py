# cogs/quiz/cog.py
import discord
from discord.ext import commands, tasks
import logging
import random
import asyncio
import datetime
from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .utils import check_answer, create_permutations_list

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_loader = DataLoader()
        self.question_generator = QuestionGenerator(self.data_loader)
        # {area: {'message': message, 'correct_answers': [...], 'end_time': datetime}}
        self.current_questions = {}
        self.wcr_question_count = 0  # Zählt die Anzahl der gestellten WCR-Fragen
        # Anzahl der dynamischen Fragen, bevor eine Frage aus JSON gestellt wird
        self.max_wcr_dynamic_questions = 10
        self.time_window = datetime.timedelta(
            minutes=5)  # Zeitfenster von 5 Minuten

        self.language = 'en'  # Standardmäßig 'en'

        # Konfiguration der Areas mit Channel-ID
        self.areas_config = {
            'wcr': {
                'channel_id': 1290804058281607189,  # Ersetze mit deiner WCR-Kanal-ID
            },
            'd4': {
                'channel_id': 1290804058281607189,  # Ersetze mit deiner D4-Kanal-ID
            },
            # Weitere Areas können hier hinzugefügt werden
        }

        # Start der Quiz-Timer für alle konfigurierten Areas
        for area in self.areas_config:
            self.bot.loop.create_task(self.quiz_scheduler(area))

    async def quiz_scheduler(self, area):
        """Scheduler, der das Zeitfenster verwaltet und die Fragen zu zufälligen Zeiten stellt."""
        await self.bot.wait_until_ready()
        while True:
            # Berechne den Start und das Ende des aktuellen Zeitfensters
            now = datetime.datetime.utcnow()
            next_window_start = now.replace(second=0, microsecond=0)
            next_window_end = next_window_start + self.time_window

            # Logge die Dauer des Zeitfensters
            window_end_str = next_window_end.strftime('%H:%M:%S')
            logger.info(f"Time window for area '{
                        area}' until {window_end_str}.")

            # Berechne die späteste Zeit für die Fragenstellung (Hälfte des Zeitfensters)
            latest_question_time = next_window_start + (self.time_window / 2)

            # Wähle eine zufällige Zeit zwischen jetzt und der Hälfte des Zeitfensters
            question_time = now + \
                random.uniform(
                    0, (latest_question_time - now).total_seconds()) * datetime.timedelta(seconds=1)

            # Warte bis zur Frage
            await asyncio.sleep((question_time - now).total_seconds())

            # Stelle die Frage
            await self.run_quiz(area)

            # Warte bis zum Ende des Zeitfensters
            now = datetime.datetime.utcnow()
            await asyncio.sleep((next_window_end - now).total_seconds())

            # Schließe die Frage, falls sie noch offen ist
            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def run_quiz(self, area):
        config = self.areas_config[area]
        channel = self.bot.get_channel(config['channel_id'])
        if channel is None:
            logger.error(f"Channel with ID {
                config['channel_id']} for area '{area}' not found.")
            return

        logger.info(f"Running quiz for area '{
                    area}' in channel {channel.name}.")

        # Prüfen, ob bereits eine Frage offen ist
        if area in self.current_questions:
            logger.warning(f"A question is already active in area '{area}'.")
            return

        # Frage generieren
        if area == 'wcr':
            if self.wcr_question_count < self.max_wcr_dynamic_questions:
                question_data = self.question_generator.generate_dynamic_wcr_question()
                self.wcr_question_count += 1
            else:
                question_data = self.question_generator.generate_question_from_json(
                    area)
                self.wcr_question_count = 0  # Zurücksetzen des Zählers
        else:
            question_data = self.question_generator.generate_question_from_json(
                area)

        if question_data:
            question_text, correct_answers = question_data['frage'], question_data['antwort']
            category = question_data.get('category', 'Mechanik')

            # Berechne die Endzeit der Frage basierend auf dem aktuellen Zeitfenster
            now = datetime.datetime.utcnow()
            minutes = (now.minute // 5 + 1) * 5
            extra_hours, minutes = divmod(minutes, 60)
            current_window_end = now.replace(
                hour=(now.hour + extra_hours) % 24,
                minute=minutes,
                second=0,
                microsecond=0
            )
            end_time = min(now + self.time_window, current_window_end)
            end_time_str = end_time.strftime('%H:%M:%S')

            message = await channel.send(f"**Quizfrage ({category}):** {question_text}")
            self.current_questions[area] = {
                'message': message,
                'correct_answers': correct_answers,
                'end_time': end_time
            }
            logger.info(f"Question for area '{area}' sent: {
                        question_text} (will end at {end_time_str})")
        else:
            logger.warning(
                f"No question could be generated for area '{area}'.")

    async def close_question(self, area, timed_out=False):
        """Schließt die aktuelle Frage für den angegebenen Bereich."""
        question_info = self.current_questions.pop(area, None)
        if question_info:
            channel = question_info['message'].channel
            if timed_out:
                await channel.send("Zeit abgelaufen! Leider wurde die Frage nicht rechtzeitig beantwortet.")
            else:
                await channel.send("Die Frage wurde erfolgreich beantwortet!")
            logger.info(f"Question in area '{area}' closed.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return  # Ignoriere Nachrichten von Bots

        # Prüfen, ob die Nachricht eine Antwort auf eine aktive Frage ist
        for area, question_info in self.current_questions.items():
            # Überprüfe, ob die Nachricht im selben Kanal wie die Quizfrage gesendet wurde
            if message.channel.id == question_info['message'].channel.id:
                # Überprüfe, ob das Zeitfenster abgelaufen ist
                if datetime.datetime.utcnow() >= question_info['end_time']:
                    await self.close_question(area, timed_out=True)
                    continue  # Zum nächsten Bereich gehen

                # Überprüfe, ob die Nachricht eine Antwort auf die Quizfrage ist
                if message.reference and message.reference.message_id == question_info['message'].id:
                    # Antwort prüfen
                    correct_answers = question_info['correct_answers']
                    if check_answer(message.content, correct_answers):
                        # Punkte hinzufügen
                        user_id = str(message.author.id)
                        scores = self.data_loader.load_scores()
                        scores[user_id] = scores.get(user_id, 0) + 1
                        self.data_loader.save_scores(scores)

                        # Benutzer benachrichtigen
                        await message.channel.send(f"Richtig, {message.author.mention}! Du hast einen Punkt erhalten. 🏆")

                        # Frage schließen
                        await self.close_question(area)

                        # Logge die richtige Antwort des Benutzers
                        logger.info(f"User '{message.author}' answered correctly in area '{
                                    area}' with '{message.content}'.")

                        return  # Verarbeitung beenden
                    else:
                        await message.channel.send(f"Das ist leider nicht korrekt, {message.author.mention}. Versuche es erneut!")

                        # Logge die falsche Antwort des Benutzers
                        logger.info(f"User '{message.author}' answered incorrectly in area '{
                                    area}' with '{message.content}'.")

                        return  # Verarbeitung beenden
                else:
                    continue  # Nachricht ist keine Antwort auf die Quizfrage
        # Wenn die Nachricht nicht relevant war, nichts tun

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_language(self, ctx, language_code):
        """Setzt die Sprache für die Quizfragen."""
        self.language = language_code
        self.data_loader.set_language(language_code)
        self.question_generator = QuestionGenerator(self.data_loader)
        await ctx.send(f"Sprache wurde auf '{language_code}' gesetzt.")
