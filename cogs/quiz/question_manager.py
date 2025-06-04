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

        if not cfg.get("active"):
            logger.info(
                f"[QuestionManager] Area '{area}' ist inaktiv – keine Frage stellen.")
            return

        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            logger.warning(
                f"[QuestionManager] Channel für '{area}' nicht gefunden.")
            return

        if area in self.cog.current_questions:
            logger.info(f"[QuestionManager] Frage für '{area}' läuft bereits.")
            return

        cid = channel.id

        if not self.cog.tracker.is_initialized(cid):
            self.cog.tracker.set_initialized(cid)
            logger.info(
                f"[QuestionManager] Channel '{channel.name}' ({area}) initialisiert – überspringe Aktivitätsprüfung.")
        else:
            threshold = cfg.get("activity_threshold", 10)
            if self.cog.tracker.get(cid) < threshold:
                logger.info(
                    f"[QuestionManager] Nachrichtenzähler für '{area}': {self.cog.tracker.get(cid)}/{threshold} – warte auf Aktivität."
                )
                self.cog.awaiting_activity[cid] = (area, end_time)
                return

        logger.info(
            f"[QuestionManager] Bedingungen erfüllt – sende Frage für '{area}'.")
        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        qg = cfg["question_generator"]

        max_dyn = cfg.get("max_dynamic_questions", 5)
        question = qg.generate(area, max_dynamic=max_dyn)
        if not question:
            logger.warning(
                f"[QuestionManager] Keine Frage generiert für '{area}'.")
            return

        frage_text = question["frage"]
        correct_answers = question["antwort"] if isinstance(
            question["antwort"], list) else [question["antwort"]]

        embed = discord.Embed(
            title=f"Quiz für {area.upper()}",
            description=frage_text,
            color=discord.Color.blue()
        )
        embed.add_field(name="Kategorie", value=question.get(
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
            "frage": frage_text,
            "category": question.get("category", "–")
        }
        self.cog.current_questions[area] = {
            "message_id": sent_msg.id,
            "end_time": end_time,
            "answers": correct_answers
        }
        self.cog.answered_users[area].clear()
        self.cog.tracker.reset(channel.id)
        self.cog.awaiting_activity.pop(channel.id, None)
        self.cog.state.set_active_question(area, qinfo)

        logger.info(
            f"[QuestionManager] Frage gesendet in '{area}': {frage_text}")
