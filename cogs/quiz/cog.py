import logging
import random
import asyncio
import datetime
import os
from collections import defaultdict

import discord
from discord.ext import commands

from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .utils import check_answer

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    """Core quiz logic: scheduling, asking and checking answers."""

    def __init__(self, bot: commands.Bot):
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

        # load areas from environment variables
        env_areas = {"wcr": "quiz_c_wcr",
                     "d4": "quiz_c_d4", "ptcgp": "quiz_c_ptcgp"}
        for area, env_var in env_areas.items():
            cid_str = os.getenv(env_var)
            if not cid_str:
                logger.warning(
                    f"[QuizCog] env var '{env_var}' not set, skipping area '{area}'"
                )
                continue
            try:
                channel_id = int(cid_str)
            except ValueError:
                logger.error(
                    f"[QuizCog] invalid channel ID in '{env_var}': {cid_str}"
                )
                continue

            loader = DataLoader()
            loader.set_language("de")
            generator = QuestionGenerator(loader)
            self.area_data[area] = {
                "channel_id": channel_id,
                "language": "de",
                "data_loader": loader,
                "question_generator": generator
            }

            self.bot.loop.create_task(self.quiz_scheduler(area))

        self.bot.loop.create_task(self._initialize_message_counters())

    async def _initialize_message_counters(self):
        for area, cfg in self.area_data.items():
            channel_id = cfg["channel_id"]
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                logger.warning(
                    f"[QuizCog] Channel-ID {channel_id} für Area '{area}' nicht gefunden.")
                continue

            question = self.current_questions.get(area)
            if question:
                if datetime.datetime.utcnow() > question["end_time"]:
                    logger.info(
                        f"[QuizCog] Removing expired question for '{area}' during startup (silent)")
                    self.current_questions.pop(area, None)
                else:
                    logger.info(
                        f"[QuizCog] Found previous quiz question in {channel.name}")

            try:
                count = 0
                async for msg in channel.history(limit=20):
                    if msg.author.bot:
                        continue
                    count += 1
                self.message_counter[channel.id] = count
                # WICHTIG: immer initialisieren
                self.channel_initialized[channel.id] = True
                logger.info(
                    f"[QuizCog] Initialized message counter for {channel.name}: {count}")
            except discord.Forbidden:
                logger.error(
                    f"[QuizCog] Missing permissions to read history in {channel.name}")
            except Exception as e:
                logger.error(
                    f"[QuizCog] Error initializing message counter for {channel.name}: {e}", exc_info=True)

    async def quiz_scheduler(self, area: str):
        await self.bot.wait_until_ready()
        while True:
            now = datetime.datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + self.time_window
            logger.info(
                f"[QuizCog] time window for '{area}' until {window_end.strftime('%H:%M:%S')}"
            )

            latest = window_start + (self.time_window / 2)
            delta = (latest - now).total_seconds()
            next_time = now + \
                datetime.timedelta(seconds=random.uniform(
                    0, delta)) if delta > 0 else now

            await asyncio.sleep(max((next_time - now).total_seconds(), 0))
            await self.prepare_question(area, window_end)

            await asyncio.sleep(max((window_end - datetime.datetime.utcnow()).total_seconds(), 0))
            cid = self.area_data[area]["channel_id"]
            self.awaiting_activity.pop(cid, None)

            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def prepare_question(self, area: str, end_time: datetime.datetime):
        cfg = self.area_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if channel is None:
            logger.error(
                f"[QuizCog] channel {cfg['channel_id']} not found for area '{area}'")
            return

        if area in self.current_questions:
            logger.warning(f"[QuizCog] question already active in '{area}'")
            return

        cid = channel.id
        if not self.channel_initialized[cid]:
            self.channel_initialized[cid] = True
            logger.info(
                f"[QuizCog] first start in channel {channel.name}, skipping activity check")
        elif self.message_counter[cid] < 10:
            logger.info(
                f"[QuizCog] low activity in {channel.name}, postponing question for '{area}'")
            self.awaiting_activity[cid] = (area, end_time)
            return

        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime):
        cfg = self.area_data[area]
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
            logger.warning(
                f"[QuizCog] could not generate question for '{area}'")
            return

        message = await channel.send(f"**Quizfrage ({qd.get('category', 'Mechanik')}):** {qd['frage']}")
        self.current_questions[area] = {
            "message": message,
            "correct_answers": qd["antwort"],
            "end_time": end_time
        }
        self.answered_users[area].clear()
        self.message_counter[channel.id] = 0
        self.awaiting_activity.pop(channel.id, None)

        logger.info(f"[QuizCog] question sent for '{area}': {qd['frage']}")

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
            f"[QuizCog] question closed for '{area}'{' (timeout)' if timed_out else ''}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        cid = message.channel.id
        self.message_counter[cid] += 1

        if message.reference:
            ref_id = message.reference.message_id
            active_ids = [
                q["message"].id for q in self.current_questions.values()]
            if ref_id not in active_ids:
                try:
                    ref = await message.channel.fetch_message(ref_id)
                    if ref.author.id == self.bot.user.id and ref.content.startswith("**Quizfrage"):
                        await message.channel.send(
                            f"❌ {message.author.mention}, diese Frage ist nicht mehr aktiv.",
                            delete_after=5
                        )
                        return
                except discord.NotFound:
                    pass

        if cid in self.awaiting_activity and self.message_counter[cid] >= 10:
            area, end_time = self.awaiting_activity[cid]
            await self.ask_question(area, end_time)

        for area, info in list(self.current_questions.items()):
            if message.channel.id != info["message"].channel.id:
                continue

            if datetime.datetime.utcnow() >= info["end_time"]:
                await self.close_question(area, timed_out=True)
                continue

            uid = message.author.id
            if uid in self.answered_users[area]:
                await message.channel.send(
                    f"⚠️ {message.author.mention}, du hast deinen Versuch bereits gehabt.",
                    delete_after=5
                )
                return

            if message.reference and message.reference.message_id == info["message"].id:
                if check_answer(message.content, info["correct_answers"]):
                    user_key = str(uid)
                    scores = self.area_data[area]["data_loader"].load_scores()
                    scores[user_key] = scores.get(user_key, 0) + 1
                    self.area_data[area]["data_loader"].save_scores(scores)
                    await message.channel.send(
                        f"🏆 Richtig, {message.author.mention}! Du hast einen Punkt erhalten."
                    )
                    await self.close_question(area)
                    logger.info(
                        f"[QuizCog] {message.author} answered correctly in '{area}': {message.content}")
                    return
                else:
                    await message.channel.send(
                        f"❌ Das ist leider nicht korrekt, {message.author.mention}.",
                        delete_after=5
                    )
                    logger.info(
                        f"[QuizCog] {message.author} answered incorrectly in '{area}': {message.content}")
                    self.answered_users[area].add(uid)
                    return

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def set_language(self, ctx: commands.Context, area: str, language_code: str):
        if area not in self.area_data:
            await ctx.send(f"❌ Area '{area}' existiert nicht.")
            return

        loader = self.area_data[area]["data_loader"]
        if language_code not in loader.wcr_locals:
            await ctx.send(f"❌ Sprache '{language_code}' ist nicht verfügbar.")
            return

        loader.set_language(language_code)
        await ctx.send(f"🌐 Sprache für Area '{area}' auf '{language_code}' gesetzt.")
