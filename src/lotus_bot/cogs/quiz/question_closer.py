import discord
import asyncio

from lotus_bot.log_setup import get_logger
from .question_state import QuestionInfo


class QuestionCloser:
    def __init__(self, bot, state) -> None:
        """Handle closing of quiz questions and cleaning up state."""
        self.bot = bot
        self.state = state

    async def close_question(
        self,
        area: str,
        qinfo: QuestionInfo,
        timed_out: bool = False,
        winner: discord.User | None = None,
        correct_answer: str | None = None,
    ) -> None:
        logger = get_logger(__name__, area=area)
        """Mark a question as closed and update the original message."""
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg.channel_id)

        try:
            msg = await channel.fetch_message(qinfo.message_id)
            embed = msg.embeds[0]
            embed.color = discord.Color.red()

            if timed_out:
                footer = "⏰ Zeit abgelaufen!"
            elif winner:
                footer = f"✅ {winner.display_name} hat gewonnen."
            else:
                footer = "✋ Frage durch Mod beendet."

            embed.set_footer(text=footer)
            embed.add_field(
                name="Richtige Antwort", value=", ".join(qinfo.answers), inline=False
            )
            if winner and correct_answer is not None:
                embed.add_field(
                    name="Eingegebene Antwort", value=correct_answer, inline=False
                )
            await msg.edit(embed=embed, view=None)

            logger.info(f"[Closer] Frage in '{area}' geschlossen: {footer}")
        except Exception as e:
            logger.warning(
                f"[Closer] Fehler beim Schließen der Frage in '{area}': {e}",
                exc_info=True,
            )

        self.bot.quiz_cog.current_questions.pop(area, None)
        await self.state.clear_active_question(area)
        self.bot.quiz_cog.tracker.set_initialized(cfg.channel_id)

    async def auto_close(self, area: str, delay: float) -> None:
        """Automatically close ``area`` after ``delay`` seconds."""
        await asyncio.sleep(delay)
        qinfo = self.bot.quiz_cog.current_questions.get(area)
        if qinfo:
            await self.close_question(area=area, qinfo=qinfo, timed_out=True)
