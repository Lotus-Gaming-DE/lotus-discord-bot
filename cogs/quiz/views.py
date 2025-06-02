import logging
import discord
from discord.ui import View, Modal, TextInput, button, Button

from .utils import check_answer

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

        eingabe = self.answer.value.strip()
        self.cog.answered_users[self.area].add(user_id)

        if check_answer(eingabe, self.correct_answers):
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
                correct_answer=eingabe
            )
            logger.info(
                f"[Quiz] {user.name} hat richtig geantwortet in '{self.area}': {eingabe}"
            )
        else:
            await interaction.response.send_message(
                "❌ Das ist leider falsch.", ephemeral=True
            )
            logger.info(
                f"[Quiz] {user.name} hat falsch geantwortet in '{self.area}': {eingabe}"
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
