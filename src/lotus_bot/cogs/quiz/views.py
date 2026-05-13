import discord
from discord.ui import View, Modal, TextInput, button, Button

from .utils import check_answer

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)


_DIFFICULTY_POINTS: dict[str, int] = {"easy": 1, "medium": 2, "hard": 4}


def _points_for_difficulty(difficulty: str | None) -> int:
    return _DIFFICULTY_POINTS.get(difficulty or "", 1)


class AnswerModal(Modal, title="Antwort eingeben"):
    answer = TextInput(label="Deine Antwort")

    def __init__(self, area: str, correct_answers: list[str], cog, difficulty: str | None = None) -> None:
        """Modal asking a user for the answer to a quiz question."""
        super().__init__()
        self.area = area
        self.correct_answers = correct_answers
        self.cog = cog
        self.difficulty = difficulty

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
            points = _points_for_difficulty(self.difficulty)
            champion_cog = self.cog.bot.get_cog("ChampionCog")
            if champion_cog:
                await champion_cog.update_user_score(user_id, points, f"Quiz: {self.area}")
                logger.info(
                    f"[Champion] {user.display_name} erhält {points} Punkt(e) für '{self.area}'."
                )
            if hasattr(self.cog, "stats"):
                await self.cog.stats.increment(user_id)

            punkt_text = f"{points} Punkt" if points == 1 else f"{points} Punkte"
            await interaction.response.send_message(
                f"🏆 Richtig! Du erhältst {punkt_text}.", ephemeral=True
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
    def __init__(self, area: str, correct_answers: list[str], cog, difficulty: str | None = None) -> None:
        """Button view opening the ``AnswerModal``."""
        super().__init__(timeout=None)
        self.area = area
        self.correct_answers = correct_answers
        self.cog = cog
        self.difficulty = difficulty

    @button(label="Antworten", style=discord.ButtonStyle.primary)
    async def antworten(self, interaction: discord.Interaction, button: Button) -> None:
        """Show the modal unless the user already answered."""
        user_id = interaction.user.id
        if user_id in self.cog.answered_users[self.area]:
            await interaction.response.send_message(
                "⚠️ Du hast bereits geantwortet.", ephemeral=True
            )
            return

        modal = AnswerModal(self.area, self.correct_answers, self.cog, self.difficulty)
        await interaction.response.send_modal(modal)
