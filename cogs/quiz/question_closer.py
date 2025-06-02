import logging
import discord

logger = logging.getLogger(__name__)


class QuestionCloser:
    def __init__(self, bot, state):
        self.bot = bot
        self.state = state

    async def close_question(self, area: str, qinfo: dict = None, timed_out=False, winner: discord.User = None, correct_answer: str = None):
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])

        try:
            # Hole ggf. aktuelle Frage
            if not qinfo:
                qinfo = self.bot.quiz_cog.current_questions.get(area)
                if not qinfo:
                    logger.warning(
                        f"[Closer] Keine aktive Frage für '{area}' gefunden.")
                    return

            msg = await channel.fetch_message(qinfo["message_id"])
            embed = msg.embeds[0]
            embed.color = discord.Color.red()

            if timed_out:
                footer = "⏰ Zeit abgelaufen!"
            elif winner:
                footer = f"✅ {winner.display_name} hat gewonnen."
            else:
                footer = "✋ Frage durch Mod beendet."

            embed.set_footer(text=footer)
            embed.add_field(name="Richtige Antwort", value=", ".join(
                qinfo["answers"]), inline=False)
            await msg.edit(embed=embed, view=None)

            logger.info(f"[Closer] Frage in '{area}' geschlossen: {footer}")
        except Exception as e:
            logger.warning(
                f"[Closer] Fehler beim Schließen der Frage in '{area}': {e}", exc_info=True)

        self.bot.quiz_cog.current_questions.pop(area, None)
        self.state.clear_active_question(area)
        self.bot.quiz_cog.tracker.set_initialized(cfg["channel_id"])
