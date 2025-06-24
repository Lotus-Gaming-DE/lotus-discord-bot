import datetime
import asyncio
import discord

from lotus_bot.log_setup import get_logger

from .views import AnswerButtonView
from .question_state import QuestionInfo

logger = get_logger(__name__)


class QuestionRestorer:
    def __init__(self, bot, state_manager, create_task) -> None:
        """Restore running questions after a bot restart."""
        self.bot = bot
        self.state = state_manager
        self._create_task = create_task
        self.tasks: list[asyncio.Task] = []

    async def restore_all(self) -> None:
        """Recreate all still active questions from persisted state."""
        for area, _ in self.bot.quiz_data.items():
            active = self.state.get_active_question(area)
            if not active:
                continue
            try:
                end_time = active.end_time
                if end_time > datetime.datetime.utcnow():
                    logger.info(
                        "[Restorer] Wiederhergestellte Frage in '%s' läuft bis %s.",
                        area,
                        end_time,
                    )
                    task = self._create_task(self.repost_question(area, active))
                    self.tasks.append(task)
                else:
                    await self.state.clear_active_question(area)
            except Exception as e:
                logger.error(
                    f"[Restorer] Fehler beim Wiederherstellen von '{area}': {e}",
                    exc_info=True,
                )

    async def repost_question(self, area: str, qinfo: QuestionInfo) -> None:
        """Repost a single question message and restart timers."""
        cfg = self.bot.quiz_data[area]
        channel = await self.bot.fetch_channel(cfg.channel_id)

        if not channel:
            logger.error(f"[Restorer] Channel für '{area}' nicht verfügbar.")
            return

        try:
            try:
                msg = await channel.fetch_message(qinfo.message_id)
            except discord.NotFound:
                logger.warning(
                    f"[Restorer] Ursprüngliche Nachricht für '{area}' nicht mehr vorhanden – lösche Zustand."
                )
                await self.state.clear_active_question(area)
                return

            if msg.embeds and (
                msg.embeds[0].color == discord.Color.red()
                or "Zeit abgelaufen" in msg.embeds[0].footer.text
                or "hat richtig geantwortet" in msg.embeds[0].footer.text
            ):
                logger.info(
                    f"[Restorer] Frage in '{area}' war bereits rot markiert oder hatte Footer – wird nicht wiederhergestellt."
                )
                await self.state.clear_active_question(area)
                return

            correct_answers = qinfo.answers
            frage_text = qinfo.frage or "Frage nicht gespeichert"
            category = qinfo.category

            embed = discord.Embed(
                title=f"Quiz für {area.upper()} (wiederhergestellt)",
                description=frage_text,
                color=discord.Color.blue(),
            )
            embed.add_field(name="Kategorie", value=category, inline=False)
            embed.set_footer(text="Klicke auf 'Antworten', um zu antworten.")

            view = AnswerButtonView(
                area=area, correct_answers=correct_answers, cog=self.bot.quiz_cog
            )
            await msg.edit(embed=embed, view=view)

            end_time = qinfo.end_time
            self.bot.quiz_cog.current_questions[area] = QuestionInfo(
                message_id=msg.id,
                end_time=end_time,
                answers=correct_answers,
                frage=frage_text,
                category=category,
            )
            self.bot.quiz_cog.answered_users[area].clear()

            delay = max((end_time - datetime.datetime.utcnow()).total_seconds(), 0)
            task = self._create_task(self.bot.quiz_cog.closer.auto_close(area, delay))
            self.tasks.append(task)

            logger.info(
                f"[Restorer] Frage in '{area}' wurde erfolgreich wiederhergestellt."
            )
        except Exception as e:
            logger.error(f"[Restorer] Fehler in '{area}': {e}", exc_info=True)
            await self.state.clear_active_question(area)

    def cancel_all(self) -> None:
        """Cancel all running tasks created by the restorer."""
        for t in self.tasks:
            t.cancel()
