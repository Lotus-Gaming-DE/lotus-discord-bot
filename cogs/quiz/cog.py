# cogs/quiz/cog.py

import discord
from discord.ext import commands, tasks
import logging
import random
import asyncio
import datetime
from collections import defaultdict
from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .utils import check_answer, create_permutations_list

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.area_data = {}
        self.current_questions = {}
        self.answered_users = defaultdict(set)  # user pro area
        # channel_id -> nachrichtenzähler
        self.message_counter = defaultdict(int)
        self.wcr_question_count = 0
        self.max_wcr_dynamic_questions = 200
        self.time_window = datetime.timedelta(hours=0.25)

        self.areas_config = {
            'wcr': {
                'channel_id': 1303261310103851008,
                'language': 'de'
            },
            'd4': {
                'channel_id': 1290804058281607189,
                'language': 'de'
            },
        }

        for area, config in self.areas_config.items():
            data_loader = DataLoader()
            data_loader.set_language(config['language'])
            question_generator = QuestionGenerator(data_loader)
            self.area_data[area] = {
                'data_loader': data_loader,
                'question_generator': question_generator
            }
            self.bot.loop.create_task(self.quiz_scheduler(area))

    async def quiz_scheduler(self, area):
        await self.bot.wait_until_ready()
        while True:
            now = datetime.datetime.utcnow()
            next_window_start = now.replace(second=0, microsecond=0)
            next_window_end = next_window_start + self.time_window

            logger.info(
                f"Time window for area '{area}' until {next_window_end.strftime('%H:%M:%S')}.")

            latest_question_time = next_window_start + (self.time_window / 2)
            delta_seconds = (latest_question_time - now).total_seconds()
            question_time = now + \
                datetime.timedelta(seconds=random.uniform(0, delta_seconds))

            sleep_time = (question_time - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

            await self.run_quiz(area, next_window_end)

            now = datetime.datetime.utcnow()
            sleep_until_end = (next_window_end - now).total_seconds()
            if sleep_until_end > 0:
                await asyncio.sleep(sleep_until_end)

            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def run_quiz(self, area, end_time):
        config = self.areas_config[area]
        channel = self.bot.get_channel(config['channel_id'])
        if channel is None:
            logger.error(
                f"Channel with ID {config['channel_id']} for area '{area}' not found.")
            return

        # Nur wenn genügend echte Nachrichten geschrieben wurden
        if self.message_counter[channel.id] < 10:
            logger.info(
                f"Zu wenig Aktivität in Channel {channel.id}, Frage in Area '{area}' übersprungen.")
            return

        data_loader = self.area_data[area]['data_loader']
        question_generator = self.area_data[area]['question_generator']

        if area in self.current_questions:
            logger.warning(f"A question is already active in area '{area}'.")
            return

        if area == 'wcr':
            if self.wcr_question_count < self.max_wcr_dynamic_questions:
                question_data = question_generator.generate_dynamic_wcr_question()
                self.wcr_question_count += 1
            else:
                question_data = question_generator.generate_question_from_json(
                    area)
                self.wcr_question_count = 0
        else:
            question_data = question_generator.generate_question_from_json(
                area)

        if question_data:
            question_text, correct_answers = question_data['frage'], question_data['antwort']
            category = question_data.get('category', 'Mechanik')
            end_time_str = end_time.strftime('%H:%M:%S')

            message = await channel.send(f"**Quizfrage ({category}):** {question_text}")
            self.current_questions[area] = {
                'message': message,
                'correct_answers': correct_answers,
                'end_time': end_time
            }
            self.answered_users[area].clear()
            self.message_counter[channel.id] = 0
            logger.info(
                f"Question for area '{area}' sent: {question_text} (will end at {end_time_str})")
        else:
            logger.warning(
                f"No question could be generated for area '{area}'.")

    async def close_question(self, area, timed_out=False):
        question_info = self.current_questions.pop(area, None)
        if question_info:
            channel = question_info['message'].channel
            if timed_out:
                await channel.send("⏰ Zeit abgelaufen! Leider wurde die Frage nicht rechtzeitig beantwortet.")
            else:
                await channel.send("✅ Die Frage wurde erfolgreich beantwortet!")
            logger.info(f"Question in area '{area}' closed.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id

        for area, question_info in list(self.current_questions.items()):
            if message.channel.id == question_info['message'].channel.id:
                if datetime.datetime.utcnow() >= question_info['end_time']:
                    await self.close_question(area, timed_out=True)
                    continue

                # User darf nur einmal antworten
                if message.author.id in self.answered_users[area]:
                    await message.channel.send(f"Sorry {message.author.mention}, du hast deinen Versuch bereits gehabt.", delete_after=5)
                    return

                # Nur Antworten auf die ursprüngliche Frage zählen
                if message.reference and message.reference.message_id == question_info['message'].id:
                    correct_answers = question_info['correct_answers']
                    if check_answer(message.content, correct_answers):
                        user_id = str(message.author.id)
                        scores = self.area_data[area]['data_loader'].load_scores(
                        )
                        scores[user_id] = scores.get(user_id, 0) + 1
                        self.area_data[area]['data_loader'].save_scores(scores)

                        await message.channel.send(f"🏆 Richtig, {message.author.mention}! Du hast einen Punkt erhalten.")
                        await self.close_question(area)
                        logger.info(
                            f"User '{message.author}' answered correctly in area '{area}' with '{message.content}'.")
                        return
                    else:
                        await message.channel.send(f"❌ Das ist leider nicht korrekt, {message.author.mention}.")
                        logger.info(
                            f"User '{message.author}' answered incorrectly in area '{area}' with '{message.content}'.")
                        self.answered_users[area].add(message.author.id)
                        return

                # Andere Nachricht im Quiz-Channel → nicht zählen
                return

        # Falls keine aktive Frage im Channel: Nur "echte" Aktivität zählen
        self.message_counter[channel_id] += 1
        logger.debug(
            f"Aktive Nachricht von {message.author} in {message.channel.name} gezählt.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_language(self, ctx, area: str, language_code: str):
        if area not in self.areas_config:
            await ctx.send(f"Area '{area}' existiert nicht.")
            return

        if language_code not in self.area_data[area]['data_loader'].wcr_locals:
            await ctx.send(f"Sprache '{language_code}' ist für Area '{area}' nicht verfügbar.")
            return

        self.area_data[area]['data_loader'].set_language(language_code)
        await ctx.send(f"Sprache für Area '{area}' wurde auf '{language_code}' gesetzt.")
