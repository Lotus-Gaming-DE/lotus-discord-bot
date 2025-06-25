import discord
from discord.ui import View, Modal, TextInput, button, Button

from .utils import check_answer

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


class AnswerModal(Modal, title="Antwort eingeben"):
    answer = TextInput(label="Deine Antwort")

    def __init__(self, area: str, correct_answers: list[str], cog) -> None:
        """Modal asking a user for the answer to a quiz question."""
        super().__init__()
        self.area = area
        self.correct_answers = correct_answers
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the submitted answer and award points if correct."""
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
                logger.info(
                    f"[Champion] {user.display_name} erhält 1 Punkt für '{self.area}'."
                )
            if hasattr(self.cog, "stats"):
                await self.cog.stats.increment(user_id)

            await interaction.response.send_message(
                "🏆 Richtig! Du erhältst einen Punkt.", ephemeral=True
            )

            qinfo = self.cog.current_questions.get(self.area)
            if qinfo:
                await self.cog.closer.close_question(
                    area=self.area,
                    qinfo=qinfo,
                    timed_out=False,
                    winner=user,
                    correct_answer=eingabe,
                )

            logger.info(
                f"[Quiz] {user.display_name} hat richtig geantwortet in '{self.area}': {eingabe}"
            )
        else:
            await interaction.response.send_message(
                "❌ Das ist leider falsch.", ephemeral=True
            )
            logger.info(
                f"[Quiz] {user.display_name} hat falsch geantwortet in '{self.area}': {eingabe}"
            )


class AnswerButtonView(View):
    def __init__(self, area: str, correct_answers: list[str], cog) -> None:
        """Button view opening the ``AnswerModal``."""
        super().__init__(timeout=None)
        self.area = area
        self.correct_answers = correct_answers
        self.cog = cog

    @button(label="Antworten", style=discord.ButtonStyle.primary)
    async def antworten(self, interaction: discord.Interaction, button: Button) -> None:
        """Show the modal unless the user already answered."""
        user_id = interaction.user.id
        if user_id in self.cog.answered_users[self.area]:
            await interaction.response.send_message(
                "⚠️ Du hast bereits geantwortet.", ephemeral=True
            )
            return

        modal = AnswerModal(self.area, self.correct_answers, self.cog)
        await interaction.response.send_modal(modal)
