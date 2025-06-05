# cogs/quiz/question_manager.py

import datetime
import discord

from log_setup import get_logger

from .views import AnswerButtonView
from .question_state import QuestionInfo



class QuestionManager:
    def __init__(self, cog) -> None:
        """Manage sending and tracking of quiz questions."""
        self.cog = cog
        self.bot = cog.bot

    async def prepare_question(self, area: str, end_time: datetime.datetime) -> None:
        """Check conditions and schedule a question for ``area``."""
        logger = get_logger(__name__, area=area)
        cfg = self.bot.quiz_data[area]

        if not cfg.active:
            logger.info(
                f"[QuestionManager] Area '{area}' ist inaktiv – keine Frage stellen.")
            return

        channel = self.bot.get_channel(cfg.channel_id)
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
            threshold = cfg.activity_threshold
            if self.cog.tracker.get(cid) < threshold:
                logger.info(
                    f"[QuestionManager] Nachrichtenzähler für '{area}': {self.cog.tracker.get(cid)}/{threshold} – warte auf Aktivität."
                )
                self.cog.awaiting_activity[cid] = (area, end_time)
                return

        logger.info(
            f"[QuestionManager] Bedingungen erfüllt – sende Frage für '{area}'.")
        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime) -> None:
        """Post a question immediately and store its state."""
        logger = get_logger(__name__, area=area)
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg.channel_id)
        qg = cfg.question_generator

        language = cfg.language
        question = qg.generate(area, language=language)
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

        qinfo = QuestionInfo(
            message_id=sent_msg.id,
            end_time=end_time,
            answers=correct_answers,
            frage=frage_text,
            category=question.get("category", "–"),
        )
        self.cog.current_questions[area] = qinfo
        self.cog.answered_users[area].clear()
        self.cog.tracker.reset(channel.id)
        self.cog.awaiting_activity.pop(channel.id, None)
        self.cog.state.set_active_question(area, qinfo)

        logger.info(
            f"[QuestionManager] Frage gesendet in '{area}': {frage_text}")
