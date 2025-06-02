# cogs/quiz/cog.py

import logging
import random
import asyncio
import datetime
from collections import defaultdict

import discord
from discord.ext import commands

from .views import AnswerButtonView
from .question_state import QuestionStateManager

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.current_questions: dict[str, dict] = {}
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        self.message_counter: dict[int, int] = defaultdict(int)
        self.channel_initialized: dict[int, bool] = defaultdict(bool)
        self.awaiting_activity: dict[int, tuple[str, datetime.datetime]] = {}

        self.max_wcr_dynamic_questions = 5
        self.wcr_question_count = 0
        self.time_window = datetime.timedelta(minutes=15)

        self.state = QuestionStateManager("data/pers/quiz/question_state.json")

        for area in self.bot.quiz_data.keys():
            self.bot.loop.create_task(self.quiz_scheduler(area))

        self.bot.loop.create_task(self._initialize_message_counters())
        self._restore_active_questions()

    def _restore_active_questions(self):
        for area, cfg in self.bot.quiz_data.items():
            active = self.state.get_active_question(area)
            if not active:
                continue
            try:
                end_time = datetime.datetime.fromisoformat(active["end_time"])
                if end_time > datetime.datetime.utcnow():
                    logger.info(
                        f"[QuizCog] Wiederhergestellte Frage in '{area}' läuft bis {end_time}.")
                    self.bot.loop.create_task(
                        self.repost_question(area, active))
                else:
                    self.state.clear_active_question(area)
            except Exception as e:
                logger.error(
                    f"[QuizCog] Fehler beim Wiederherstellen von '{area}': {e}", exc_info=True)

    async def _auto_close(self, area: str, delay: float):
        await asyncio.sleep(delay)
        if area in self.current_questions:
            await self.close_question(area, timed_out=True)

    async def _initialize_message_counters(self):
        await self.bot.wait_until_ready()

        for area, cfg in self.bot.quiz_data.items():
            channel_id = cfg["channel_id"]
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                logger.warning(
                    f"[QuizCog] Channel-ID {channel_id} für '{area}' nicht gefunden: {e}")
                continue

            try:
                messages = []
                async for msg in channel.history(limit=20):
                    messages.append(msg)

                quiz_index = next((i for i, msg in enumerate(messages)
                                   if msg.author.id == self.bot.user.id and msg.embeds
                                   and msg.embeds[0].title.startswith(f"Quiz für {area.upper()}")
                                   ), None)

                if quiz_index is not None:
                    real_messages = [
                        m for m in messages[:quiz_index] if not m.author.bot]
                    self.message_counter[channel.id] = len(real_messages)
                else:
                    self.message_counter[channel.id] = 10

                self.channel_initialized[channel.id] = True
            except Exception as e:
                logger.error(
                    f"[QuizCog] Fehler beim Initialisieren von {channel.name}: {e}", exc_info=True)

    async def quiz_scheduler(self, area: str):
        await self.bot.wait_until_ready()
        if area not in self.bot.quiz_data:
            return

        while True:
            now = datetime.datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + self.time_window

            latest = window_start + (self.time_window / 2)
            delta = max((latest - now).total_seconds(), 0)
            next_time = now + \
                datetime.timedelta(seconds=random.uniform(0, delta))
            delay = random.uniform(0, self.time_window.total_seconds() / 2)

            logger.info(
                f"[QuizCog] Nächstes Zeitfenster für '{area}': Frage wird gegen {next_time + datetime.timedelta(seconds=delay)} gepostet.")

            await asyncio.sleep((next_time - now).total_seconds())
            await asyncio.sleep(delay)

            if area not in self.bot.quiz_data:
                return

            await self.prepare_question(area, window_end)

            await asyncio.sleep(max((window_end - datetime.datetime.utcnow()).total_seconds(), 0))

            cid = self.bot.quiz_data[area]["channel_id"]
            self.awaiting_activity.pop(cid, None)
            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def prepare_question(self, area: str, end_time: datetime.datetime):
        if area not in self.bot.quiz_data:
            return

        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            return

        if area in self.current_questions:
            return

        if not self.channel_initialized[channel.id]:
            self.channel_initialized[channel.id] = True
        elif self.message_counter[channel.id] < 10:
            self.awaiting_activity[channel.id] = (area, end_time)
            return

        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        qg = cfg["question_generator"]

        if area == "wcr" and self.wcr_question_count < self.max_wcr_dynamic_questions:
            qd = qg.generate_dynamic_question("wcr")
            self.wcr_question_count += 1
        else:
            qd = qg.generate_question_from_json(area)
            if area == "wcr":
                self.wcr_question_count = 0

        if not qd:
            return

        frage_text = qd["frage"]
        correct_answers = qd["antwort"] if isinstance(
            qd["antwort"], list) else [qd["antwort"]]
        data_loader = cfg["data_loader"]

        embed = discord.Embed(
            title=f"Quiz für {area.upper()}",
            description=frage_text,
            color=discord.Color.blue()
        )
        embed.add_field(name="Kategorie", value=qd.get(
            "category", "–"), inline=False)
        embed.set_footer(text="Klicke auf 'Antworten', um zu antworten.")

        view = AnswerButtonView(area, correct_answers, self)
        sent_msg = await channel.send(embed=embed, view=view)

        qinfo = {
            "message_id": sent_msg.id,
            "end_time": end_time.isoformat(),
            "answers": correct_answers
        }
        self.current_questions[area] = {
            "message_id": sent_msg.id,
            "end_time": end_time,
            "answers": correct_answers
        }
        self.answered_users[area].clear()
        self.message_counter[channel.id] = 0
        self.awaiting_activity.pop(channel.id, None)
        self.state.set_active_question(area, qinfo)

        logger.info(f"[QuizCog] Frage gesendet in '{area}': {frage_text}")
        await asyncio.sleep(max((end_time - datetime.datetime.utcnow()).total_seconds(), 0))
        await self.close_question(area, timed_out=True)

    async def repost_question(self, area: str, qinfo: dict):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        correct_answers = qinfo["answers"] if isinstance(
            qinfo["answers"], list) else [qinfo["answers"]]

        embed = discord.Embed(
            title=f"Quiz für {area.upper()} (wiederhergestellt)",
            description="(Frage nicht gespeichert)",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Klicke auf 'Antworten', um zu antworten.")

        view = AnswerButtonView(area, correct_answers, self)

        try:
            msg = await channel.fetch_message(qinfo["message_id"])
            await msg.edit(embed=embed, view=view)
            logger.info(
                f"[QuizCog] Frage in {area} wurde erfolgreich wiederhergestellt.")
        except discord.NotFound:
            logger.warning(
                f"[QuizCog] Ursprüngliche Nachricht in {area} wurde gelöscht – neue wird gesendet.")
            msg = await channel.send(embed=embed, view=view)
            qinfo["message_id"] = msg.id
            self.state.set_active_question(area, qinfo)
        except Exception as e:
            logger.error(
                f"[QuizCog] Fehler beim Wiederherstellen von {area}: {e}", exc_info=True)
            return

        end_time = datetime.datetime.fromisoformat(qinfo["end_time"])
        self.current_questions[area] = {
            "message_id": qinfo["message_id"],
            "end_time": end_time,
            "answers": correct_answers
        }
        self.answered_users[area].clear()

        await asyncio.sleep((end_time - datetime.datetime.utcnow()).total_seconds())
        await self.close_question(area, timed_out=True)

    async def close_question(self, area: str, timed_out: bool = False, winner: discord.User = None, correct_answer: str = None):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if area not in self.current_questions:
            return

        qinfo = self.current_questions.pop(area)
        self.state.clear_active_question(area)

        try:
            msg = await channel.fetch_message(qinfo["message_id"])
            embed = msg.embeds[0]
            embed.color = discord.Color.red()

            footer = "⏰ Zeit abgelaufen!" if timed_out else "✅ Richtig beantwortet!"
            if winner:
                footer += f" • {winner.display_name} hat gewonnen."
            if not timed_out and winner is None and correct_answer is None:
                footer = "✋ Frage durch Mod beendet."
            embed.set_footer(text=footer)

            ans_text = ", ".join(qinfo["answers"]) if isinstance(
                qinfo["answers"], list) else str(qinfo["answers"])
            embed.add_field(name="Richtige Antwort",
                            value=ans_text.strip(), inline=False)

            await msg.edit(embed=embed, view=None)
        except Exception as e:
            logger.warning(
                f"[QuizCog] Fehler beim Schließen der Frage in '{area}': {e}")

        self.channel_initialized[cfg["channel_id"]] = False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        cid = message.channel.id
        self.message_counter[cid] += 1

        if cid in self.awaiting_activity and self.message_counter[cid] >= 10:
            area, end_time = self.awaiting_activity[cid]
            await self.ask_question(area, end_time)
