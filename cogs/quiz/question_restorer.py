import logging
import datetime
import discord

from .views import AnswerButtonView

logger = logging.getLogger(__name__)


class QuestionRestorer:
    def __init__(self, bot, state_manager):
        self.bot = bot
        self.state = state_manager

    def restore_all(self):
        for area, cfg in self.bot.quiz_data.items():
            active = self.state.get_active_question(area)
            if not active:
                continue
            try:
                end_time = datetime.datetime.fromisoformat(active["end_time"])
                if end_time > datetime.datetime.utcnow():
                    logger.info(
                        f"[Restorer] Wiederhergestellte Frage in '{area}' läuft bis {end_time}."
                    )
                    self.bot.loop.create_task(
                        self.repost_question(area, active))
                else:
                    self.state.clear_active_question(area)
            except Exception as e:
                logger.error(
                    f"[Restorer] Fehler beim Wiederherstellen von '{area}': {e}", exc_info=True
                )

    async def repost_question(self, area: str, qinfo: dict):
        cfg = self.bot.quiz_data[area]
        channel = await self.bot.fetch_channel(cfg["channel_id"])

        if not channel:
            logger.error(f"[Restorer] Channel für '{area}' nicht verfügbar.")
            return

        try:
            try:
                msg = await channel.fetch_message(qinfo["message_id"])
            except discord.NotFound:
                logger.warning(
                    f"[Restorer] Ursprüngliche Nachricht für '{area}' nicht mehr vorhanden – lösche Zustand.")
                self.state.clear_active_question(area)
                return

            if msg.embeds and (
                msg.embeds[0].color == discord.Color.red()
                or "Zeit abgelaufen" in msg.embeds[0].footer.text
                or "hat richtig geantwortet" in msg.embeds[0].footer.text
            ):
                logger.info(
                    f"[Restorer] Frage in '{area}' war bereits rot markiert oder hatte Footer – wird nicht wiederhergestellt.")
                self.state.clear_active_question(area)
                return

            correct_answers = qinfo["answers"] if isinstance(
                qinfo["answers"], list) else [qinfo["answers"]]
            frage_text = qinfo.get("frage", "Frage nicht gespeichert")

            embed = discord.Embed(
                title=f"Quiz für {area.upper()} (wiederhergestellt)",
                description=frage_text,
                color=discord.Color.blue(),
            )
            embed.set_footer(text="Klicke auf 'Antworten', um zu antworten.")

            view = AnswerButtonView(
                area=area, correct_answers=correct_answers, cog=self.bot.quiz_cog)
            await msg.edit(embed=embed, view=view)

            end_time = datetime.datetime.fromisoformat(qinfo["end_time"])
            self.bot.quiz_cog.current_questions[area] = {
                "message_id": msg.id,
                "end_time": end_time,
                "answers": correct_answers,
            }
            self.bot.quiz_cog.answered_users[area].clear()

            delay = max(
                (end_time - datetime.datetime.utcnow()).total_seconds(), 0)
            self.bot.loop.create_task(
                self.bot.quiz_cog.closer.auto_close(area, delay)
            )

            logger.info(
                f"[Restorer] Frage in '{area}' wurde erfolgreich wiederhergestellt.")
        except Exception as e:
            logger.error(f"[Restorer] Fehler in '{area}': {e}", exc_info=True)
            self.state.clear_active_question(area)
