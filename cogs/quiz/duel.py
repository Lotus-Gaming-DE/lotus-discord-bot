import discord
from discord.ui import View, button, Modal, TextInput, Button
from dataclasses import dataclass
import datetime

from .utils import check_answer
import inspect
from .question_generator import QuestionGenerator
from log_setup import get_logger

logger = get_logger(__name__)


@dataclass
class DuelConfig:
    area: str
    points: int
    mode: str
    timeout: int = 30
    best_of: int | None = None


class DuelQuestionView(View):
    def __init__(
        self,
        challenger: discord.Member,
        opponent: discord.Member,
        correct_answers: list[str],
        timeout: int,
    ) -> None:
        """View handling question answers of a duel round."""
        super().__init__(timeout=timeout)
        self.challenger = challenger
        self.opponent = opponent
        self.players = {challenger.id, opponent.id}
        self.correct_answers = correct_answers
        self.responses: dict[int, tuple[str, datetime.datetime]] = {}
        self.winner_id: int | None = None
        self.message: discord.Message | None = None
        logger.debug(
            f"[DuelQuestionView] init challenger={challenger.id} opponent={opponent.id}"
        )

    @button(label="Antworten", style=discord.ButtonStyle.primary)
    async def answer(self, interaction: discord.Interaction, _: Button) -> None:
        """Collect an answer from one of the duel participants."""
        if interaction.user.id not in self.players:
            logger.debug(
                f"[DuelQuestionView] user {interaction.user.id} tried to answer without joining"
            )
            await interaction.response.send_message(
                "Du bist nicht Teil dieses Duells.", ephemeral=True
            )
            return
        if interaction.user.id in self.responses:
            logger.debug(
                f"[DuelQuestionView] user {interaction.user.id} tried to answer twice"
            )
            await interaction.response.send_message(
                "Du hast bereits geantwortet.", ephemeral=True
            )
            return
        logger.debug(f"Duel answer modal opened by {interaction.user}")
        modal = _DuelAnswerModal(self)
        await interaction.response.send_modal(modal)

    async def on_timeout(self) -> None:
        """Finish the duel round when the timeout is reached."""
        logger.info("DuelQuestionView timed out")
        await self._finish(timed_out=True)

    async def _finish(self, timed_out: bool = False) -> None:
        """Disable buttons, show results and stop the view."""
        for child in self.children:
            child.disabled = True
        self._determine_winner()
        if self.message:
            embed = (
                self.message.embeds[0]
                if self.message.embeds
                else discord.Embed(title="Quiz-Duell")
            )
            embed.color = discord.Color.red()
            embed.add_field(
                name="Richtige Antwort",
                value=", ".join(self.correct_answers),
                inline=False,
            )
            answers = []
            for member in (self.challenger, self.opponent):
                ans = self.responses.get(member.id)
                if ans:
                    start = getattr(self.message, "created_at", None)
                    if start:
                        delta = (ans[1] - start).total_seconds()
                        answers.append(
                            f"{member.display_name}: {ans[0]} ({delta:.1f}s)"
                        )
                    else:
                        answers.append(f"{member.display_name}: {ans[0]}")
                else:
                    answers.append(f"{member.display_name}: –")
            embed.add_field(name="Antworten", value="\n".join(answers), inline=False)
            footer = "⏰ Zeit abgelaufen!" if timed_out else "Runde beendet"
            embed.set_footer(text=footer)
            await self.message.edit(embed=embed, view=self)
        logger.debug(
            f"DuelQuestionView finished, winner={self.winner_id}, responses={self.responses}"
        )
        self.stop()

    def _determine_winner(self) -> None:
        """Evaluate all answers and store the winner ID."""
        results: list[tuple[datetime.datetime, int]] = []
        for uid, (answer, ts) in self.responses.items():
            if check_answer(answer, self.correct_answers):
                results.append((ts, uid))
        results.sort()
        self.winner_id = results[0][1] if results else None


class _DuelAnswerModal(Modal, title="Antwort eingeben"):
    answer = TextInput(label="Deine Antwort")

    def __init__(self, view: DuelQuestionView) -> None:
        """Simple modal used to collect a duel answer."""
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Store the answer and finish if all players responded."""
        if self.view.is_finished():
            await interaction.response.send_message(
                "Die Runde ist bereits beendet.", ephemeral=True
            )
            return
        self.view.responses[interaction.user.id] = (
            self.answer.value,
            interaction.created_at or datetime.datetime.utcnow(),
        )
        logger.debug(
            f"[DuelAnswerModal] user={interaction.user.id} answer='{self.answer.value}'"
        )
        await interaction.response.send_message("Antwort erhalten.", ephemeral=True)
        if len(self.view.responses) >= len(self.view.players):
            await self.view._finish()


class DuelInviteView(View):
    def __init__(self, challenger: discord.Member, cfg: DuelConfig, cog) -> None:
        """View representing a duel invitation with accept button."""
        super().__init__(timeout=60)
        self.challenger = challenger
        self.cfg = cfg
        self.cog = cog
        self.message: discord.Message | None = None
        self.accepted = False
        logger.info(
            f"[DuelInviteView] created by {challenger.display_name} area={cfg.area} points={cfg.points} mode={cfg.mode}"
        )

    async def on_timeout(self) -> None:
        """Remove the view if the invitation timed out."""
        if not self.accepted and self.message:
            logger.info("[DuelInviteView] invitation timed out")
            await self.message.edit(view=None)
            await self.message.channel.send(
                f"{self.challenger.mention}, deine Duellanfrage ist abgelaufen."
            )

    @button(label="Annehmen", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _: Button) -> None:
        """Start the duel if the invitee accepts."""
        if interaction.user.id == self.challenger.id:
            logger.debug(
                f"[DuelInviteView] {interaction.user.id} tried to accept own duel"
            )
            await interaction.response.send_message(
                "Du kannst dein eigenes Duell nicht annehmen.", ephemeral=True
            )
            return
        if self.accepted:
            logger.debug(
                f"[DuelInviteView] {interaction.user.id} tried to accept but already accepted"
            )
            await interaction.response.send_message(
                "Das Duell wurde bereits angenommen.", ephemeral=True
            )
            return
        self.accepted = True
        logger.info(f"Duel accepted by {interaction.user} against {self.challenger}")
        await interaction.response.defer()
        await self.start_duel(interaction)

    async def start_duel(self, interaction: discord.Interaction) -> None:
        """Create the duel thread and run the game."""
        logger.info(
            f"Starting duel {self.challenger.display_name} vs {interaction.user.display_name} in {self.cfg.area} for {self.cfg.points} points"
        )
        champion_cog = self.cog.bot.get_cog("ChampionCog")
        if champion_cog is None:
            await interaction.followup.send(
                "Champion-System nicht verfügbar.", ephemeral=True
            )
            if self.message:
                await self.message.edit(view=None)
            self.stop()
            self.accepted = False
            return

        current_challenger = await champion_cog.data.get_total(str(self.challenger.id))
        logger.debug(
            f"[DuelInviteView] challenger points={current_challenger} required={self.cfg.points}"
        )
        if current_challenger < self.cfg.points:
            await interaction.followup.send(
                "Der Herausforderer hat nicht genug Punkte.", ephemeral=True
            )
            if self.message:
                await self.message.edit(view=None)
            self.stop()
            self.accepted = False
            return

        current_opponent = await champion_cog.data.get_total(str(interaction.user.id))
        logger.debug(
            f"[DuelInviteView] opponent points={current_opponent} required={self.cfg.points}"
        )
        if current_opponent < self.cfg.points:
            await interaction.followup.send(
                "Du hast nicht genug Punkte.", ephemeral=True
            )
            self.accepted = False
            return

        await champion_cog.update_user_score(
            self.challenger.id, -self.cfg.points, "Quiz-Duell Einsatz"
        )
        await champion_cog.update_user_score(
            interaction.user.id, -self.cfg.points, "Quiz-Duell Einsatz"
        )
        logger.info(
            f"[DuelInviteView] deducted {self.cfg.points} points from each participant"
        )
        try:
            thread = await self.message.create_thread(
                name=f"Duel {self.challenger.display_name} vs {interaction.user.display_name}",
                auto_archive_duration=60,
            )
            logger.debug(
                f"[DuelInviteView] thread created: {thread.id if hasattr(thread, 'id') else 'N/A'}"
            )
            if self.message:
                embed = (
                    self.message.embeds[0]
                    if self.message.embeds
                    else discord.Embed(title="Quiz-Duell")
                )
                embed.add_field(name="Gegner", value=interaction.user.mention)
                await self.message.edit(embed=embed, view=None)
        except Exception as e:
            logger.error(f"Failed to create duel thread: {e}", exc_info=True)
            await champion_cog.update_user_score(
                self.challenger.id, self.cfg.points, "Quiz-Duell Rückgabe"
            )
            await champion_cog.update_user_score(
                interaction.user.id, self.cfg.points, "Quiz-Duell Rückgabe"
            )
            await interaction.followup.send(
                "Duell konnte nicht gestartet werden.", ephemeral=True
            )
            if self.message:
                await self.message.edit(view=None)
            self.stop()
            self.accepted = False
            return
        game = QuizDuelGame(
            self.cog,
            thread,
            self.cfg.area,
            self.challenger,
            interaction.user,
            self.cfg.points * 2,
            self.cfg.mode,
            self.message,
            self.cfg.timeout,
            self.cfg.best_of,
        )
        await game.run()
        self.stop()


class QuizDuelGame:
    def __init__(
        self,
        cog,
        thread: discord.Thread,
        area: str,
        challenger: discord.Member,
        opponent: discord.Member,
        pot: int,
        mode: str,
        invite_message: discord.Message | None = None,
        timeout: int = 30,
        best_of: int | None = None,
    ) -> None:
        """Hold state for an ongoing duel game."""

        self.cog = cog
        self.thread = thread
        self.area = area
        self.challenger = challenger
        self.opponent = opponent
        self.mode = mode
        self.pot = pot
        self.invite_message = invite_message
        self.timeout = timeout
        self.best_of = best_of
        self.stake = pot // 2
        self.scores = {challenger.id: 0, opponent.id: 0}
        self.winner_id: int | None = None

    async def run(self) -> None:
        """Run the duel until one player has enough wins."""
        qg: QuestionGenerator = self.cog.bot.quiz_data[self.area].question_generator

        if self.mode == "dynamic":
            logger.info(
                f"QuizDuelGame started between {self.challenger} and {self.opponent} mode=dynamic"
            )
            provider = qg.get_dynamic_provider(self.area)
            if not provider:
                await self.thread.send("Keine Frage generiert. Duell abgebrochen.")
                await self.thread.edit(archived=True)
                return

            questions = provider.generate_all_types()
            logger.debug(
                f"[QuizDuelGame] dynamic questions generated: {len(questions)}"
            )
            if not questions:
                await self.thread.send("Keine Frage generiert. Duell abgebrochen.")
                champion_cog = self.cog.bot.get_cog("ChampionCog")
                if champion_cog:
                    await champion_cog.update_user_score(
                        self.challenger.id, self.stake, "Quiz-Duell Rückgabe"
                    )
                    await champion_cog.update_user_score(
                        self.opponent.id, self.stake, "Quiz-Duell Rückgabe"
                    )
                await self.thread.edit(archived=True)
                return

            total_rounds = len(questions)
            last_correct: dict[int, datetime.datetime | None] = {
                self.challenger.id: None,
                self.opponent.id: None,
            }

            for idx, question in enumerate(questions, start=1):
                answers = (
                    question["antwort"]
                    if isinstance(question["antwort"], list)
                    else [question["antwort"]]
                )
                logger.debug(
                    f"[QuizDuelGame] dynamic question {idx}: {question['frage']}"
                )
                embed = discord.Embed(
                    title=f"Frage {idx}",
                    description=question["frage"],
                    color=discord.Color.blue(),
                )
                view = DuelQuestionView(
                    self.challenger,
                    self.opponent,
                    answers,
                    self.timeout,
                )
                msg = await self.thread.send(embed=embed, view=view)
                view.message = msg
                await view.wait()
                winner_id = view.winner_id
                if winner_id:
                    self.scores[winner_id] += 1
                    resp = view.responses.get(winner_id)
                    ts = resp[1] if resp else None
                    if ts and (
                        last_correct[winner_id] is None or ts > last_correct[winner_id]
                    ):
                        last_correct[winner_id] = ts
                    member = self.cog.bot.get_user(winner_id)
                    if member is None:
                        try:
                            member = await self.cog.bot.fetch_user(winner_id)
                        except Exception:
                            member = None
                    if member is None:
                        if winner_id == self.challenger.id:
                            name = getattr(
                                self.challenger, "display_name", str(winner_id)
                            )
                        elif winner_id == self.opponent.id:
                            name = getattr(
                                self.opponent, "display_name", str(winner_id)
                            )
                        else:
                            name = str(winner_id)
                    else:
                        name = getattr(
                            member,
                            "display_name",
                            getattr(member, "name", str(winner_id)),
                        )
                    logger.debug(f"Round {idx} won by {name}")
                    await self.thread.send(
                        f"✅ {name} gewinnt diese Runde. ({self.scores[self.challenger.id]}:{self.scores[self.opponent.id]})"
                    )
                else:
                    logger.debug(f"Round {idx} no correct answer")
                    await self.thread.send(
                        f"❌ Keine richtige Antwort. ({self.scores[self.challenger.id]}:{self.scores[self.opponent.id]})"
                    )

            c_score = self.scores[self.challenger.id]
            o_score = self.scores[self.opponent.id]

            if c_score == o_score:
                t1 = last_correct[self.challenger.id]
                t2 = last_correct[self.opponent.id]
                if t1 and t2:
                    if t1 > t2:
                        self.winner_id = self.challenger.id
                    elif t2 > t1:
                        self.winner_id = self.opponent.id
            elif c_score > o_score:
                self.winner_id = self.challenger.id
            else:
                self.winner_id = self.opponent.id

            await self._finish()
            return

        # classic sequential modes
        total_rounds = self.best_of or 5
        needed = total_rounds // 2 + 1
        logger.info(
            f"QuizDuelGame started between {self.challenger} and {self.opponent} mode=box rounds={total_rounds}"
        )
        for rnd in range(1, total_rounds + 1):
            question = qg.generate(self.area)
            if inspect.isawaitable(question):
                question = await question
            if not question:
                await self.thread.send("Keine Frage generiert. Duell abgebrochen.")
                champion_cog = self.cog.bot.get_cog("ChampionCog")
                if champion_cog:
                    await champion_cog.update_user_score(
                        self.challenger.id,
                        self.stake,
                        "Quiz-Duell Rückgabe",
                    )
                    await champion_cog.update_user_score(
                        self.opponent.id,
                        self.stake,
                        "Quiz-Duell Rückgabe",
                    )
                await self.thread.edit(archived=True)
                return
            answers = (
                question["antwort"]
                if isinstance(question["antwort"], list)
                else [question["antwort"]]
            )
            logger.debug(
                f"[QuizDuelGame] question round={rnd} text={question['frage']}"
            )
            embed = discord.Embed(
                title=f"Runde {rnd}",
                description=question["frage"],
                color=discord.Color.blue(),
            )
            view = DuelQuestionView(
                self.challenger,
                self.opponent,
                answers,
                self.timeout,
            )
            msg = await self.thread.send(embed=embed, view=view)
            view.message = msg
            await view.wait()
            winner_id = view.winner_id
            if winner_id:
                self.scores[winner_id] += 1
                member = self.cog.bot.get_user(winner_id)
                if member is None:
                    try:
                        member = await self.cog.bot.fetch_user(winner_id)
                    except Exception:
                        member = None
                if member is None:
                    if winner_id == self.challenger.id:
                        name = getattr(self.challenger, "display_name", str(winner_id))
                    elif winner_id == self.opponent.id:
                        name = getattr(self.opponent, "display_name", str(winner_id))
                    else:
                        name = str(winner_id)
                else:
                    name = getattr(
                        member, "display_name", getattr(member, "name", str(winner_id))
                    )
                logger.debug(f"Round {rnd} won by {name}")
                await self.thread.send(
                    f"✅ {name} gewinnt diese Runde. ({self.scores[self.challenger.id]}:{self.scores[self.opponent.id]})"
                )
            else:
                logger.debug(f"Round {rnd} no correct answer")
                await self.thread.send(
                    f"❌ Keine richtige Antwort. ({self.scores[self.challenger.id]}:{self.scores[self.opponent.id]})"
                )
            if (
                self.scores[self.challenger.id] >= needed
                or self.scores[self.opponent.id] >= needed
            ):
                break
        await self._finish()

    async def _finish(self) -> None:
        """Award points to the winner and archive the thread."""
        champion_cog = self.cog.bot.get_cog("ChampionCog")
        if champion_cog is None:
            await self.thread.send(
                "Champion-System nicht verfügbar. Punkte werden nicht verteilt."
            )
            await self.thread.edit(archived=True)
            return

        challenger_score = self.scores[self.challenger.id]
        opponent_score = self.scores[self.opponent.id]
        winner: discord.Member | None = None
        winner_display = None

        if self.winner_id:
            winner = (
                self.challenger
                if self.winner_id == self.challenger.id
                else self.opponent
            )
        elif challenger_score > opponent_score:
            winner = self.challenger
        elif opponent_score > challenger_score:
            winner = self.opponent

        if winner:
            user_obj = self.cog.bot.get_user(winner.id)
            if user_obj is None:
                try:
                    user_obj = await self.cog.bot.fetch_user(winner.id)
                except Exception:
                    user_obj = None
            winner_display = (
                getattr(user_obj, "display_name", getattr(user_obj, "name", None))
                if user_obj
                else getattr(
                    winner, "display_name", getattr(winner, "name", str(winner.id))
                )
            )

        logger.info(
            f"QuizDuelGame finished winner={winner_display if winner else 'None'} score={self.scores}"
        )
        logger.debug(
            f"[QuizDuelGame] challenger_score={challenger_score} opponent_score={opponent_score}"
        )

        if winner:
            await champion_cog.update_user_score(
                winner.id, self.pot, "Quiz-Duell Gewinn"
            )
            await self.thread.send(
                f"🏆 {winner_display} gewinnt das Duell und erhält {self.pot} Punkte!"
            )
            logger.info(f"[QuizDuelGame] awarded {self.pot} points to {winner_display}")
        else:
            refund = self.pot // 2
            await champion_cog.update_user_score(
                self.challenger.id, refund, "Quiz-Duell Rückgabe"
            )
            await champion_cog.update_user_score(
                self.opponent.id, refund, "Quiz-Duell Rückgabe"
            )
            await self.thread.send("Unentschieden. Einsätze zurück an Spieler.")
            logger.info(f"[QuizDuelGame] refunded {refund} points to each participant")

        await self.thread.send(
            f"Endstand: {self.challenger.display_name} {challenger_score} - {opponent_score} {self.opponent.display_name}"
        )
        await self.thread.edit(archived=True)

        if self.invite_message:
            embed = (
                self.invite_message.embeds[0]
                if self.invite_message.embeds
                else discord.Embed(title="Quiz-Duell")
            )
            if winner:
                result_text = (
                    f"{winner_display} gewinnt {self.pot} Punkte"
                    f" ({challenger_score}:{opponent_score})"
                )
            else:
                result_text = f"Unentschieden ({challenger_score}:{opponent_score})"
            embed.add_field(name="Ergebnis", value=result_text)
            await self.invite_message.edit(embed=embed)
