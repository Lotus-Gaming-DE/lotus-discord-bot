import discord
from discord.ui import View, button, Modal, TextInput, Button
from dataclasses import dataclass
import datetime

from .utils import check_answer
from .question_generator import QuestionGenerator
from log_setup import get_logger

logger = get_logger(__name__)


@dataclass
class DuelConfig:
    area: str
    points: int
    mode: str


class DuelQuestionView(View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, correct_answers: list[str]):
        super().__init__(timeout=20)
        self.challenger = challenger
        self.opponent = opponent
        self.players = {challenger.id, opponent.id}
        self.correct_answers = correct_answers
        self.responses: dict[int, tuple[str, datetime.datetime]] = {}
        self.winner_id: int | None = None
        self.message: discord.Message | None = None

    @button(label="Antworten", style=discord.ButtonStyle.primary)
    async def answer(self, interaction: discord.Interaction, _: Button):
        if interaction.user.id not in self.players:
            await interaction.response.send_message("Du bist nicht Teil dieses Duells.", ephemeral=True)
            return
        if interaction.user.id in self.responses:
            await interaction.response.send_message("Du hast bereits geantwortet.", ephemeral=True)
            return
        logger.debug(
            f"Duel answer modal opened by {interaction.user}"
        )
        modal = _DuelAnswerModal(self)
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        logger.info("DuelQuestionView timed out")
        await self._finish()

    async def _finish(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)
        self._determine_winner()
        logger.debug(f"DuelQuestionView finished, winner={self.winner_id}")
        self.stop()

    def _determine_winner(self):
        results: list[tuple[datetime.datetime, int]] = []
        for uid, (answer, ts) in self.responses.items():
            if check_answer(answer, self.correct_answers):
                results.append((ts, uid))
        results.sort()
        self.winner_id = results[0][1] if results else None


class _DuelAnswerModal(Modal, title="Antwort eingeben"):
    answer = TextInput(label="Deine Antwort")

    def __init__(self, view: DuelQuestionView):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.responses[interaction.user.id] = (self.answer.value, interaction.created_at or datetime.datetime.utcnow())
        await interaction.response.send_message("Antwort erhalten.", ephemeral=True)
        if len(self.view.responses) >= len(self.view.players):
            await self.view._finish()


class DuelInviteView(View):
    def __init__(self, challenger: discord.Member, cfg: DuelConfig, cog):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.cfg = cfg
        self.cog = cog
        self.message: discord.Message | None = None
        self.accepted = False

    async def on_timeout(self):
        if not self.accepted and self.message:
            await self.message.edit(view=None)

    @button(label="Annehmen", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: Button):
        if interaction.user.id == self.challenger.id:
            await interaction.response.send_message("Du kannst dein eigenes Duell nicht annehmen.", ephemeral=True)
            return
        if self.accepted:
            await interaction.response.send_message("Das Duell wurde bereits angenommen.", ephemeral=True)
            return
        self.accepted = True
        logger.info(
            f"Duel accepted by {interaction.user} against {self.challenger}"
        )
        await interaction.response.defer()
        await self.start_duel(interaction)

    async def start_duel(self, interaction: discord.Interaction):
        logger.info(
            f"Starting duel {self.challenger.display_name} vs {interaction.user.display_name} in {self.cfg.area} for {self.cfg.points} points"
        )
        champion_cog = self.cog.bot.get_cog("ChampionCog")
        if champion_cog is None:
            await interaction.followup.send("Champion-System nicht verfügbar.")
            return
        current = await champion_cog.data.get_total(str(self.challenger.id))
        if current < self.cfg.points:
            await interaction.followup.send("Der Herausforderer hat nicht genug Punkte.")
            return
        await champion_cog.update_user_score(self.challenger.id, -self.cfg.points, "Quiz-Duell Einsatz")
        thread = await self.message.create_thread(name=f"Duel {self.challenger.display_name} vs {interaction.user.display_name}")
        await interaction.followup.send(f"{interaction.user.mention} hat das Duell angenommen! Schau hier: {thread.mention}")
        game = QuizDuelGame(self.cog, thread, self.cfg.area, self.challenger, interaction.user, self.cfg.points, self.cfg.mode)
        await game.run()
        self.stop()


class QuizDuelGame:
    def __init__(self, cog, thread: discord.Thread, area: str, challenger: discord.Member, opponent: discord.Member, points: int, mode: str):
        self.cog = cog
        self.thread = thread
        self.area = area
        self.challenger = challenger
        self.opponent = opponent
        self.points = points
        self.mode = mode
        self.scores = {challenger.id: 0, opponent.id: 0}

    async def run(self):
        qg: QuestionGenerator = self.cog.bot.quiz_data[self.area].question_generator
        total_rounds = {"bo3": 3, "bo5": 5}.get(self.mode, 5)
        needed = total_rounds // 2 + 1
        logger.info(
            f"QuizDuelGame started between {self.challenger} and {self.opponent} mode={self.mode} rounds={total_rounds}"
        )
        for rnd in range(1, total_rounds + 1):
            question = qg.generate(self.area)
            if not question:
                await self.thread.send("Keine Frage generiert. Duell abgebrochen.")
                return
            answers = question["antwort"] if isinstance(question["antwort"], list) else [question["antwort"]]
            embed = discord.Embed(title=f"Runde {rnd}", description=question["frage"], color=discord.Color.blue())
            view = DuelQuestionView(self.challenger, self.opponent, answers)
            msg = await self.thread.send(embed=embed, view=view)
            view.message = msg
            await view.wait()
            winner_id = view.winner_id
            if winner_id:
                self.scores[winner_id] += 1
                name = self.cog.bot.get_user(winner_id).display_name
                logger.debug(f"Round {rnd} won by {name}")
                await self.thread.send(f"✅ {name} gewinnt diese Runde. ({self.scores[self.challenger.id]}:{self.scores[self.opponent.id]})")
            else:
                logger.debug(f"Round {rnd} no correct answer")
                await self.thread.send(f"❌ Keine richtige Antwort. ({self.scores[self.challenger.id]}:{self.scores[self.opponent.id]})")
            if self.scores[self.challenger.id] >= needed or self.scores[self.opponent.id] >= needed:
                break
        await self._finish()

    async def _finish(self):
        champion_cog = self.cog.bot.get_cog("ChampionCog")
        if self.scores[self.challenger.id] > self.scores[self.opponent.id]:
            winner = self.challenger
        elif self.scores[self.opponent.id] > self.scores[self.challenger.id]:
            winner = self.opponent
        else:
            winner = None
        logger.info(
            f"QuizDuelGame finished winner={winner.display_name if winner else 'None'} score={self.scores}"
        )
        if winner:
            await champion_cog.update_user_score(winner.id, self.points, "Quiz-Duell Gewinn")
            await self.thread.send(f"🏆 {winner.display_name} gewinnt das Duell und erhält {self.points} Punkte!")
        else:
            await champion_cog.update_user_score(self.challenger.id, self.points, "Quiz-Duell Rückgabe")
            await self.thread.send("Unentschieden. Einsatz zurück an Herausforderer.")
        await self.thread.edit(archived=True)
