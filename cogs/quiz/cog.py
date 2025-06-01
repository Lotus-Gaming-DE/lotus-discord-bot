# cogs/quiz/cog.py

import logging
import random
import asyncio
import datetime
from collections import defaultdict

import discord
from discord.ext import commands

from .utils import check_answer
from .wcr_question_provider import WCRQuestionProvider

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_questions: dict[str, dict] = {}
        self.message_counter: dict[int, int] = defaultdict(int)
        self.awaiting_activity: dict[int, tuple[str, datetime.datetime]] = {}
        self.channel_initialized: dict[int, bool] = defaultdict(bool)

        self.max_wcr_dynamic_questions = 5
        self.wcr_question_count = 0
        self.answered_users: dict[str, set[int]] = defaultdict(set)

        self.bot.loop.create_task(self._initialize_message_counters())

    async def _initialize_message_counters(self):
        for area, cfg in self.bot.quiz_data.items():
            channel_id = cfg["channel_id"]
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                logger.warning(
                    f"[QuizCog] Channel-ID {channel_id} für Area '{area}' nicht gefunden: {e}")
                continue

            question = self.current_questions.get(area)
            if question and datetime.datetime.utcnow() > question["end_time"]:
                logger.info(
                    f"[QuizCog] Entferne abgelaufene Frage für '{area}' beim Start.")
                self.current_questions.pop(area, None)
                self.channel_initialized[channel.id] = True

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("[QuizCog] Cog bereit.")

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
            logger.warning(f"[QuizCog] Keine Frage generiert für '{area}'.")
            return

        frage_text = qd["frage"]
        antworten = qd["antwort"]

        embed = discord.Embed(
            title=f"Quiz für {area.upper()}",
            description=frage_text,
            color=discord.Color.blue()
        )
        embed.add_field(name="Kategorie", value=qd.get(
            "category", "–"), inline=False)
        answer_list = "\n".join(f"- {a}" for a in antworten)
        embed.add_field(name="Antwortmöglichkeiten",
                        value=answer_list, inline=False)
        embed.set_footer(text="Schicke deine Antwort als Textnachricht!")

        sent_msg = await channel.send(embed=embed)

        self.current_questions[area] = {
            "message_id": sent_msg.id,
            "end_time": end_time,
            "answers": set(antworten)
        }
        self.answered_users[area].clear()

        now = datetime.datetime.utcnow()
        verbleibende = (end_time - now).total_seconds()
        await asyncio.sleep(verbleibende)
        await self.close_question(area, timed_out=True)

    async def close_question(self, area: str, timed_out: bool = False):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if area not in self.current_questions:
            return

        qinfo = self.current_questions[area]
        try:
            msg = await channel.fetch_message(qinfo["message_id"])
            footer = " ⏰ Zeit abgelaufen!" if timed_out else " ✅ Richtig beantwortet!"
            embed = msg.embeds[0]
            embed.color = discord.Color.red()
            embed.set_footer(text=embed.footer.text + footer)
            await msg.edit(embed=embed)
        except Exception as e:
            logger.warning(
                f"[QuizCog] Beim Schließen der Frage für '{area}' ist ein Fehler aufgetreten: {e}")

        self.current_questions.pop(area, None)
        self.channel_initialized[cfg["channel_id"]] = False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        cid = message.channel.id
        self.message_counter[cid] += 1
        logger.debug(
            f"[QuizCog] Counter für {message.channel.name}: {self.message_counter[cid]}")

        for area, qinfo in self.current_questions.items():
            if cid == self.bot.quiz_data[area]["channel_id"]:
                uid = message.author.id
                if uid in self.answered_users[area]:
                    return

                eingabe = message.content.strip()
                if eingabe.lower() in (a.lower() for a in qinfo["answers"]):
                    data_loader = self.bot.quiz_data[area]["data_loader"]
                    scores = data_loader.load_scores()
                    scores[str(uid)] = scores.get(str(uid), 0) + 1
                    data_loader.save_scores(scores)

                    await message.channel.send(
                        f"🏆 Richtig, {message.author.mention}! Du hast einen Punkt erhalten."
                    )
                    await self.close_question(area)
                    return
                else:
                    self.answered_users[area].add(uid)
                    await message.channel.send(
                        f"❌ Das ist leider nicht korrekt, {message.author.mention}.", delete_after=5
                    )
                    return

        if cid in self.awaiting_activity and self.message_counter[cid] >= 10:
            area, end_time = self.awaiting_activity[cid]
            await self.ask_question(area, end_time)
