# cogs/quiz/cog.py

import discord
from discord.ext import commands
import logging
import random
import asyncio
import datetime
import os
from collections import defaultdict
from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .utils import check_answer

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.area_data = {}
        self.current_questions = {}
        self.answered_users = defaultdict(set)
        self.message_counter = defaultdict(int)
        self.channel_initialized = defaultdict(bool)
        self.awaiting_activity = {}
        self.wcr_question_count = 0
        self.max_wcr_dynamic_questions = 200
        self.time_window = datetime.timedelta(hours=0.25)

        # Dynamisch konfigurierte Areas über Umgebungsvariablen
        self.areas_config = {}

        env_areas = {
            "wcr": "quiz_c_wcr",
            "d4": "quiz_c_d4",
            "ptcgp": "quiz_c_ptcgp"
        }

        for area, env_var in env_areas.items():
            channel_id_str = os.getenv(env_var)
            if channel_id_str is None:
                logger.warning(
                    f"⚠️ Umgebungsvariable '{env_var}' nicht gesetzt – Area '{area}' wird übersprungen.")
                continue

            try:
                channel_id = int(channel_id_str)
            except ValueError:
                logger.error(
                    f"❌ Ungültige Channel-ID in Umgebungsvariable '{env_var}': {channel_id_str}")
                continue

            self.areas_config[area] = {
                "channel_id": channel_id,
                "language": "de"
            }

        # Initialisiere die Fragegeneratoren pro aktiver Area
        for area, config in self.areas_config.items():
            data_loader = DataLoader()
            data_loader.set_language(config['language'])
            question_generator = QuestionGenerator(data_loader)
            self.area_data[area] = {
                "data_loader": data_loader,
                "question_generator": question_generator
            }

            # Starte Quiz-Loop für die Area
            self.bot.loop.create_task(self.quiz_scheduler(area))

       # 🔁 ZÄHLER INITIALISIEREN
        self.bot.loop.create_task(self._initialize_message_counters())

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

            await self.prepare_question(area, next_window_end)

            # Warte bis zum Ende des Zeitfensters
            now = datetime.datetime.utcnow()
            sleep_until_end = (next_window_end - now).total_seconds()
            if sleep_until_end > 0:
                await asyncio.sleep(sleep_until_end)

            # Zeitfenster vorbei → offene Fragen verwerfen
            self.awaiting_activity.pop(
                self.areas_config[area]['channel_id'], None)

            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def _initialize_message_counters(self):
        await self.bot.wait_until_ready()

        for area, config in self.areas_config.items():
            channel_id = config["channel_id"]
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue

            counter = 0
            async for msg in channel.history(limit=20):
                if msg.author.id == self.bot.user.id and msg.content.startswith("**Quizfrage"):
                    # Quizfrage gefunden – eventuell beim Neustart offen geblieben
                    logger.info(
                        f"💬 Frühere Quizfrage erkannt in Channel {channel.name}.")

                    # Prüfen, ob diese Frage noch aktiv ist
                    if area not in self.current_questions:
                        self.current_questions[area] = {
                            "message": msg,
                            "correct_answers": [],
                            "end_time": datetime.datetime.utcnow()  # Dummy-Wert
                        }
                        await self.close_question(area, timed_out=True)

                    break  # Abbruch: keine weiteren Nachrichten zählen

                if not msg.author.bot:
                    counter += 1
                    if counter >= 10:
                        break

            self.message_counter[channel_id] = counter
            logger.info(
                f"📊 Initialisierte Nachrichtenzahl für {channel.name}: {counter}")

    async def prepare_question(self, area, end_time):
        config = self.areas_config[area]
        channel = self.bot.get_channel(config['channel_id'])
        if channel is None:
            logger.error(
                f"Channel mit ID {config['channel_id']} für Area '{area}' nicht gefunden.")
            return

        if area in self.current_questions:
            logger.warning(f"In Area '{area}' ist bereits eine Frage aktiv.")
            return

        if not self.channel_initialized[channel.id]:
            self.channel_initialized[channel.id] = True
            logger.info(
                f"Erster Start in Channel {channel.id} – Frage wird gestellt ohne Nachrichtenprüfung.")
        elif self.message_counter[channel.id] < 10:
            logger.info(
                f"Aktivität zu gering in Channel {channel.id} – Frage für Area '{area}' wird zurückgestellt.")
            self.awaiting_activity[channel.id] = (area, end_time)
            return

        await self.ask_question(area, end_time)

    async def ask_question(self, area, end_time):
        config = self.areas_config[area]
        channel = self.bot.get_channel(config['channel_id'])
        question_generator = self.area_data[area]['question_generator']

        if area == 'wcr' and self.wcr_question_count < self.max_wcr_dynamic_questions:
            question_data = question_generator.generate_dynamic_wcr_question()
            self.wcr_question_count += 1
        else:
            question_data = question_generator.generate_question_from_json(
                area)
            if area == 'wcr':
                self.wcr_question_count = 0

        if question_data:
            question_text, correct_answers = question_data['frage'], question_data['antwort']
            category = question_data.get('category', 'Mechanik')
            message = await channel.send(f"**Quizfrage ({category}):** {question_text}")
            self.current_questions[area] = {
                'message': message,
                'correct_answers': correct_answers,
                'end_time': end_time
            }
            self.answered_users[area].clear()
            self.message_counter[channel.id] = 0
            self.awaiting_activity.pop(channel.id, None)
            logger.info(f"Frage für Area '{area}' gesendet: {question_text}")
        else:
            logger.warning(f"Konnte keine Frage für Area '{area}' generieren.")

    async def close_question(self, area, timed_out=False):
        question_info = self.current_questions.pop(area, None)
        if question_info:
            channel = question_info['message'].channel
            if timed_out:
                await channel.send("⏰ Zeit abgelaufen! Leider wurde die Frage nicht rechtzeitig beantwortet.")
            else:
                await channel.send("✅ Die Frage wurde erfolgreich beantwortet!")
            logger.info(f"Frage in Area '{area}' geschlossen.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        self.message_counter[channel_id] += 1

        # Wenn auf eine alte, nicht mehr aktive Quizfrage geantwortet wurde
        if message.reference:
            ref_id = message.reference.message_id
            active_message_ids = [
                q["message"].id for q in self.current_questions.values()
            ]
            if ref_id not in active_message_ids:
                try:
                    referenced = await message.channel.fetch_message(ref_id)

                    # Nur reagieren, wenn es sich um eine vom Bot stammende Quizfrage handelt
                    if (
                        referenced.author.id == self.bot.user.id and
                        referenced.content.startswith("**Quizfrage")
                    ):
                        await message.channel.send(
                            f"❌ {message.author.mention}, diese Frage ist nicht mehr aktiv.",
                            delete_after=5
                        )
                        return
                except discord.NotFound:
                    pass

        # Nachgelagerte Prüfung für zurückgestellte Fragen
        if channel_id in self.awaiting_activity:
            if self.message_counter[channel_id] >= 10:
                area, end_time = self.awaiting_activity[channel_id]
                await self.ask_question(area, end_time)

        for area, question_info in list(self.current_questions.items()):
            if message.channel.id == question_info['message'].channel.id:
                if datetime.datetime.utcnow() >= question_info['end_time']:
                    await self.close_question(area, timed_out=True)
                    continue

                if message.author.id in self.answered_users[area]:
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, du hast deinen Versuch bereits gehabt.",
                        delete_after=5
                    )
                    return

                if message.reference and message.reference.message_id == question_info['message'].id:
                    correct_answers = question_info['correct_answers']
                    if check_answer(message.content, correct_answers):
                        user_id = str(message.author.id)
                        scores = self.area_data[area]['data_loader'].load_scores(
                        )
                        scores[user_id] = scores.get(user_id, 0) + 1
                        self.area_data[area]['data_loader'].save_scores(scores)
                        await message.channel.send(
                            f"🏆 Richtig, {message.author.mention}! Du hast einen Punkt erhalten."
                        )
                        await self.close_question(area)
                        logger.info(
                            f"User '{message.author}' hat korrekt geantwortet in Area '{area}': '{message.content}'"
                        )
                        return
                    else:
                        await message.channel.send(
                            f"❌ Das ist leider nicht korrekt, {message.author.mention}.",
                            delete_after=5
                        )
                        logger.info(
                            f"User '{message.author}' hat falsch geantwortet in Area '{area}': '{message.content}'"
                        )
                        self.answered_users[area].add(message.author.id)
                        return

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
