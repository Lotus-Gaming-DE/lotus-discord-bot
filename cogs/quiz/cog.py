# cogs/quiz/cog.py

import logging
import random
import asyncio
import datetime
from collections import defaultdict

import discord
from discord.ext import commands

from .utils import check_answer

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.current_questions = {}
        self.answered_users = defaultdict(set)
        self.message_counter = defaultdict(int)
        self.channel_initialized = defaultdict(bool)
        self.awaiting_activity = {}
        self.wcr_question_count = 0
        self.max_wcr_dynamic_questions = 200
        self.time_window = datetime.timedelta(minutes=15)

        # Starte Scheduler für alle Areas aus quiz_data
        for area, cfg in bot.quiz_data.items():
            self.bot.loop.create_task(self.quiz_scheduler(area))

        self.bot.loop.create_task(self._initialize_message_counters())

    async def _initialize_message_counters(self):
        for area, cfg in self.bot.quiz_data.items():
            channel_id = cfg["channel_id"]
            channel = await self.bot.fetch_channel(channel_id)
            if not channel:
                logger.warning(
                    f"[QuizCog] Channel-ID {channel_id} für Area '{area}' nicht gefunden.")
                continue

            question = self.current_questions.get(area)
            if question and datetime.datetime.utcnow() > question["end_time"]:
                logger.info(
                    f"[QuizCog] Entferne abgelaufene Frage für '{area}' beim Start.")
                self.current_questions.pop(area, None)
                self.channel_initialized[channel.id] = True
                continue

            count = 0
            try:
                async for msg in channel.history(limit=20):
                    if msg.author.bot:
                        continue
                    if msg.content.startswith("**Quizfrage"):
                        break
                    count += 1
                self.message_counter[channel.id] = count
                logger.info(
                    f"[QuizCog] Nachrichtenzähler für {channel.name} gesetzt: {count}")
            except discord.Forbidden:
                logger.error(
                    f"[QuizCog] Keine Berechtigung, um History in {channel.name} zu lesen.")
            except Exception as e:
                logger.error(
                    f"[QuizCog] Fehler beim Lesen des Verlaufs in {channel.name}: {e}", exc_info=True)

    async def quiz_scheduler(self, area: str):
        await self.bot.wait_until_ready()
        while True:
            now = datetime.datetime.utcnow()
            window_end = now.replace(
                second=0, microsecond=0) + self.time_window
            logger.info(
                f"[QuizCog] time window for '{area}' until {window_end.strftime('%H:%M:%S')}")
            delay = random.uniform(0, (self.time_window.total_seconds() / 2))
            await asyncio.sleep(delay)
            await self.prepare_question(area, window_end)
            await asyncio.sleep(max((window_end - datetime.datetime.utcnow()).total_seconds(), 0))
            cid = self.bot.quiz_data[area]["channel_id"]
            self.awaiting_activity.pop(cid, None)
            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def prepare_question(self, area: str, end_time: datetime.datetime):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            logger.error(
                f"[QuizCog] Channel für Area '{area}' nicht gefunden.")
            return
        if area in self.current_questions:
            logger.warning(f"[QuizCog] Frage für '{area}' läuft bereits.")
            return

        cid = channel.id
        if not self.channel_initialized[cid]:
            self.channel_initialized[cid] = True
            logger.info(
                f"[QuizCog] Erster Start in {channel.name}, überspringe Aktivitätsprüfung.")
        elif self.message_counter[cid] < 10:
            logger.info(
                f"[QuizCog] Zu wenig Aktivität in {channel.name}, verschiebe Frage.")
            self.awaiting_activity[cid] = (area, end_time)
            return

        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        qg = cfg["question_generator"]

        if area == "wcr" and self.wcr_question_count < self.max_wcr_dynamic_questions:
            qd = qg.generate_dynamic_wcr_question()
            self.wcr_question_count += 1
        else:
            qd = qg.generate_question_from_json(area)
            if area == "wcr":
                self.wcr_question_count = 0

        if not qd:
            logger.warning(f"[QuizCog] Keine Frage generiert für '{area}'.")
            return

        msg = await channel.send(f"**Quizfrage ({qd.get('category', 'Allgemein')}):** {qd['frage']}")
        self.current_questions[area] = {
            "message": msg,
            "correct_answers": qd["antwort"],
            "end_time": end_time
        }
        self.answered_users[area].clear()
        self.message_counter[channel.id] = 0
        self.awaiting_activity.pop(channel.id, None)
        logger.info(f"[QuizCog] Frage gesendet in '{area}': {qd['frage']}")

    async def close_question(self, area: str, timed_out: bool = False):
        info = self.current_questions.pop(area, None)
        if not info:
            return
        channel = info["message"].channel
        if timed_out:
            await channel.send("⏰ Zeit abgelaufen! Leider wurde die Frage nicht rechtzeitig beantwortet.")
        else:
            await channel.send("✅ Die Frage wurde erfolgreich beantwortet!")
        logger.info(
            f"[QuizCog] Frage beendet in '{area}'{' (Timeout)' if timed_out else ''}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        cid = message.channel.id
        self.message_counter[cid] += 1
        logger.debug(
            f"[QuizCog] Counter für {message.channel.name}: {self.message_counter[cid]}")

        if message.reference:
            ref_id = message.reference.message_id
            for area, q in self.current_questions.items():
                if q["message"].id == ref_id:
                    if datetime.datetime.utcnow() >= q["end_time"]:
                        await self.close_question(area, timed_out=True)
                        return
                    uid = message.author.id
                    if uid in self.answered_users[area]:
                        await message.channel.send(
                            f"⚠️ {message.author.mention}, du hast deinen Versuch bereits gehabt.",
                            delete_after=5
                        )
                        return
                    if check_answer(message.content, q["correct_answers"]):
                        scores = self.bot.quiz_data[area]["data_loader"].load_scores(
                        )
                        scores[str(uid)] = scores.get(str(uid), 0) + 1
                        self.bot.quiz_data[area]["data_loader"].save_scores(
                            scores)
                        await message.channel.send(f"🏆 Richtig, {message.author.mention}! Du hast einen Punkt erhalten.")
                        await self.close_question(area)
                        return
                    else:
                        self.answered_users[area].add(uid)
                        await message.channel.send(f"❌ Das ist leider nicht korrekt, {message.author.mention}.", delete_after=5)
                        return

        # verspätete Freigabe
        if cid in self.awaiting_activity and self.message_counter[cid] >= 10:
            area, end_time = self.awaiting_activity[cid]
            await self.ask_question(area, end_time)
