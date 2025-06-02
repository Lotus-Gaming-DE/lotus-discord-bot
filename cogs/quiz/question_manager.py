# cogs/quiz/question_manager.py

import logging
import datetime
import discord

from .views import AnswerButtonView

logger = logging.getLogger(__name__)


class QuestionManager:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot

    async def prepare_question(self, area: str, end_time: datetime.datetime):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            logger.warning(
                f"[QuestionManager] Channel für '{area}' nicht gefunden.")
            return

        if area in self.cog.current_questions:
            logger.info(f"[QuestionManager] Frage für '{area}' läuft bereits.")
            return

        cid = channel.id

        if not self.cog.channel_initialized[cid]:
            self.cog.channel_initialized[cid] = True
            logger.info(
                f"[QuestionManager] Channel '{channel.name}' ({area}) initialisiert – überspringe Aktivitätsprüfung.")
        elif self.cog.message_counter[cid] < 10:
            logger.info(
                f"[QuestionManager] Nachrichtenzähler für '{area}': {self.cog.message_counter[cid]}/10 – warte auf Aktivität.")
            self.cog.awaiting_activity[cid] = (area, end_time)
            return

        logger.info(
            f"[QuestionManager] Bedingungen erfüllt – sende Frage für '{area}'.")
        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        qg = cfg["question_generator"]

        if area == "wcr" and self.cog.wcr_question_count < self.cog.max_wcr_dynamic_questions:
            qd = qg.generate_dynamic_question("wcr")
            self.cog.wcr_question_count += 1
        else:
            qd = qg.generate_question_from_json(area)
            if area == "wcr":
                self.cog.wcr_question_count = 0

        if not qd:
            logger.warning(
                f"[QuestionManager] Keine Frage generiert für '{area}'.")
            return

        frage_text = qd["frage"]
        correct_answers = qd["antwort"] if isinstance(
            qd["antwort"], list) else [qd["antwort"]]

        embed = discord.Embed(
            title=f"Quiz für {area.upper()}",
            description=frage_text,
            color=discord.Color.blue()
        )
        embed.add_field(name="Kategorie", value=qd.get(
            "category", "–"), inline=False)
        embed.set_footer(text="Klicke auf 'Antworten', um zu antworten.")

        view = AnswerButtonView(area, correct_answers, self.cog)
        sent_msg = await channel.send(embed=embed, view=view)
        logger.debug(
            f"[QuestionManager] Nachricht ID {sent_msg.id} an Channel {channel.id} gesendet.")

        qinfo = {
            "message_id": sent_msg.id,
            "end_time": end_time.isoformat(),
            "answers": correct_answers,
            "frage": frage_text
        }
        self.cog.current_questions[area] = {
            "message_id": sent_msg.id,
            "end_time": end_time,
            "answers": correct_answers
        }
        self.cog.answered_users[area].clear()
        self.cog.message_counter[channel.id] = 0
        self.cog.awaiting_activity.pop(channel.id, None)
        self.cog.state.set_active_question(area, qinfo)

        logger.info(
            f"[QuestionManager] Frage gesendet in '{area}': {frage_text}")
