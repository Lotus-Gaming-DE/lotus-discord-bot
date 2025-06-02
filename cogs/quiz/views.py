# cogs/quiz/views.py

import logging
import discord
from discord.ui import View, Modal, TextInput, button, Button
from .question_state import remove_question

logger = logging.getLogger(__name__)


class AnswerModal(Modal, title="Antwort eingeben"):
    answer = TextInput(label="Deine Antwort")

    def __init__(self, area: str, correct_answers: list[str], cog):
        super().__init__()
        self.area = area
        self.correct_answers = correct_answers
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        user_id = user.id

        if user_id in self.cog.answered_users[self.area]:
            await interaction.response.send_message(
                "⚠️ Du hast bereits geantwortet.", ephemeral=True
            )
            return

        eingabe = self.answer.value.strip().lower()
        self.cog.answered_users[self.area].add(user_id)

        matched = next(
            (a for a in self.correct_answers if a.lower() == eingabe), None)

        if matched is not None:
            # Punkt im Champion-System vergeben
            champion_cog = self.cog.bot.get_cog("ChampionCog")
            if champion_cog:
                await champion_cog.update_user_score(user_id, 1, f"Quiz: {self.area}")

            await interaction.response.send_message(
                "🏆 Richtig! Du erhältst einen Punkt.", ephemeral=True
            )
            await self.cog.close_question(
                area=self.area,
                timed_out=False,
                winner=user,
                correct_answer=matched
            )
            logger.info(
                f"[Quiz] {user.name} hat richtig geantwortet in '{self.area}': {matched}"
            )
        else:
            await interaction.response.send_message(
                "❌ Das ist leider falsch.", ephemeral=True
            )
            logger.info(
                f"[Quiz] {user.name} hat falsch geantwortet in '{self.area}': {self.answer.value.strip()}"
            )


class AnswerButtonView(View):
    def __init__(self, area: str, correct_answers: list[str], cog):
        super().__init__(timeout=None)
        self.area = area
        self.correct_answers = correct_answers
        self.cog = cog

    @button(label="Antworten", style=discord.ButtonStyle.primary)
    async def antworten(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id in self.cog.answered_users[self.area]:
            await interaction.response.send_message(
                "⚠️ Du hast bereits geantwortet.", ephemeral=True
            )
            return

        modal = AnswerModal(self.area, self.correct_answers, self.cog)
        await interaction.response.send_modal(modal)


async def send_quiz_message(channel: discord.TextChannel, area: str, question: dict, view: View) -> discord.Message:
    """
    Sendet eine Quizfrage in den Channel mit Embed und Button.
    """
    embed = discord.Embed(
        title=f"Quiz für {area.upper()}",
        description=question["frage"],
        color=discord.Color.blue()
    )
    embed.add_field(name="Kategorie", value=question.get(
        "category", "–"), inline=False)
    embed.set_footer(text="Klicke auf 'Antworten', um zu antworten.")

    msg = await channel.send(embed=embed, view=view)
    logger.info(
        f"[views] Quizfrage für '{area}' gesendet: {question['frage']}")
    return msg


async def update_quiz_message(
    message: discord.Message,
    timed_out: bool,
    winner: discord.User = None,
    correct_answers: list[str] = None
):
    """
    Aktualisiert die Frage mit roter Farbe, Footer und richtiger Antwort.
    """
    try:
        embed = message.embeds[0]
        embed.color = discord.Color.red()

        if timed_out:
            footer_text = "⏰ Zeit abgelaufen!"
        elif winner:
            footer_text = f"✅ {winner.display_name} hat richtig geantwortet!"
        else:
            footer_text = "✋ Frage wurde manuell beendet."

        embed.set_footer(text=footer_text)

        if correct_answers:
            embed.add_field(
                name="Richtige Antwort",
                value=", ".join(correct_answers),
                inline=False
            )

        await message.edit(embed=embed, view=None)
        logger.info("[views] Quizfrage wurde aktualisiert.")
    except Exception as e:
        logger.error(
            f"[views] Fehler beim Aktualisieren der Quizfrage: {e}", exc_info=True)
