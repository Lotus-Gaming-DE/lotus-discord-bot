# cogs/quiz/cog.py

import logging
import random
import asyncio
import datetime
from collections import defaultdict

import discord
from discord.ext import commands
from discord.ui import View, Modal, TextInput, button, Button

from .utils import check_answer
from .wcr_question_provider import WCRQuestionProvider

logger = logging.getLogger(__name__)


class AnswerModal(Modal, title="Antwort eingeben"):
    answer = TextInput(label="Deine Antwort")

    def __init__(self, area: str, correct_answers: set, data_loader, cog):
        super().__init__()
        self.area = area
        self.correct_answers = correct_answers
        self.data_loader = data_loader
        self.cog: QuizCog = cog

    async def on_submit(self, interaction: discord.Interaction):
        eingabe = self.answer.value.strip()
        user_id = interaction.user.id

        if user_id in self.cog.answered_users[self.area]:
            await interaction.response.send_message(
                "⚠️ Du hast bereits geantwortet.", ephemeral=True
            )
            return

        if eingabe.lower() in (a.lower() for a in self.correct_answers):
            scores = self.data_loader.load_scores()
            scores[str(user_id)] = scores.get(str(user_id), 0) + 1
            self.data_loader.save_scores(scores)
            await interaction.response.send_message(
                "🏆 Richtig! Du erhältst einen Punkt.", ephemeral=True
            )
            await self.cog.close_question(self.area)
            logger.info(
                f"[QuizCog] {interaction.user} richtig in '{self.area}': {eingabe}")
        else:
            self.cog.answered_users[self.area].add(user_id)
            await interaction.response.send_message(
                "❌ Falsch.", ephemeral=True
            )
            logger.info(
                f"[QuizCog] {interaction.user} falsch in '{self.area}': {eingabe}")


class AnswerButtonView(View):
    def __init__(self, area: str, correct_answers: set, data_loader, cog):
        super().__init__(timeout=None)
        self.area = area
        self.correct_answers = correct_answers
        self.data_loader = data_loader
        self.cog: QuizCog = cog

    @button(label="Antworten", style=discord.ButtonStyle.primary)
    async def answer_button(self, interaction: discord.Interaction, button: Button):
        # Jetzt ist 'interaction' korrekt das Interaction-Objekt, nicht der Button
        user_id = interaction.user.id
        if user_id in self.cog.answered_users[self.area]:
            await interaction.response.send_message(
                "⚠️ Du hast bereits geantwortet.", ephemeral=True
            )
            return

        modal = AnswerModal(
            self.area,
            self.correct_answers,
            self.data_loader,
            self.cog
        )
        await interaction.response.send_modal(modal)


class QuizCog(commands.Cog):
    """Core quiz logic: scheduling, asking and checking answers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Merkt sich aktuell laufende Fragen pro Area
        self.current_questions: dict[str, dict] = {}
        # Wer bereits bei der laufenden Frage geantwortet hat (pro Area)
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        # Zähler echter User-Nachrichten pro Channel (live hochgezählt in on_message)
        self.message_counter: dict[int, int] = defaultdict(int)
        # Merkt, ob Channel schon initialisiert wurde (History geprüft)
        self.channel_initialized: dict[int, bool] = defaultdict(bool)
        # Wenn <10 Nachrichten, merken wir uns hier, dass wir später freigeben müssen
        self.awaiting_activity: dict[int, tuple[str, datetime.datetime]] = {}

        # Nur für WCR: wie viele dynamische Fragen max pro Lauf
        self.max_wcr_dynamic_questions = 5
        self.wcr_question_count = 0

        # Zeitfenster für Quiz (z.B. 15 Minuten)
        self.time_window = datetime.timedelta(minutes=15)

        # Scheduler für jede konfigurierte Area starten
        for area in self.bot.quiz_data.keys():
            self.bot.loop.create_task(self.quiz_scheduler(area))

        # Einmalig History prüfen, Counter setzen
        self.bot.loop.create_task(self._initialize_message_counters())

    async def _initialize_message_counters(self):
        """
        Initialisiert Nachrichtenzähler für alle Areas, indem
        die letzten 20 Nachrichten durchsucht werden und
        echte User-Nachrichten seit der letzten Quizfrage gezählt werden.
        Falls keine alte Frage gefunden wird, setzen wir Counter = 10,
        damit sofort eine neue Frage möglich ist.
        """
        await self.bot.wait_until_ready()

        for area, cfg in self.bot.quiz_data.items():
            channel_id = cfg["channel_id"]

            try:
                channel = await self.bot.fetch_channel(channel_id)
                if not channel:
                    logger.warning(
                        f"[QuizCog] Channel-ID {channel_id} für Area '{area}' nicht gefunden."
                    )
                    continue
            except Exception as e:
                logger.warning(
                    f"[QuizCog] Channel-ID {channel_id} für Area '{area}' nicht gefunden: {e}"
                )
                continue

            try:
                messages = []
                async for msg in channel.history(limit=20, oldest_first=False):
                    messages.append(msg)

                # Suche nach der letzten Quizfrage (Embed-Titel "Quiz für AREA")
                quiz_index = next(
                    (
                        i
                        for i, msg in enumerate(messages)
                        if msg.author.id == self.bot.user.id
                        and msg.embeds
                        and msg.embeds[0].title.startswith(f"Quiz für {area.upper()}")
                    ),
                    None,
                )

                if quiz_index is not None:
                    # Count echte User-Messages nach letzter Frage
                    real_messages = [
                        msg for msg in messages[:quiz_index] if not msg.author.bot
                    ]
                    count = len(real_messages)
                    self.message_counter[channel.id] = count
                    self.channel_initialized[channel.id] = True
                    logger.info(
                        f"[QuizCog] Nachrichtenzähler für {channel.name} gesetzt: {count} (nach letzter Quizfrage)"
                    )
                else:
                    # Keine Quizfrage gefunden → Counter = 10 (sofort aktiv genug)
                    self.message_counter[channel.id] = 10
                    self.channel_initialized[channel.id] = True
                    logger.info(
                        f"[QuizCog] Keine Quizfrage gefunden in {channel.name}, Zähler absichtlich auf 10 gesetzt."
                    )
            except discord.Forbidden:
                logger.error(
                    f"[QuizCog] Keine Berechtigung, um History in {channel.name} zu lesen."
                )
            except Exception as e:
                logger.error(
                    f"[QuizCog] Fehler beim Lesen des Verlaufs in {channel.name}: {e}",
                    exc_info=True,
                )

            # Entferne abgelaufene Fragen (falls vorhanden)
            question = self.current_questions.get(area)
            if question and datetime.datetime.utcnow() > question["end_time"]:
                logger.info(
                    f"[QuizCog] Entferne abgelaufene Frage für '{area}' beim Start."
                )
                self.current_questions.pop(area, None)
                self.channel_initialized[channel.id] = True

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("[QuizCog] Cog bereit.")

    async def quiz_scheduler(self, area: str):
        """
        Startet für jede Area ein sich wiederholendes Zeitfenster:
        - Berechnet ein Zeitfenster (jetzt bis jetzt+time_window)
        - Wählt innerhalb der ersten Hälfte einen zufälligen Zeitpunkt, um Fragen‐Logik aufzurufen
        - Wartet bis zum Ende des Fensters, räumt auf und startet Schleife neu
        """
        await self.bot.wait_until_ready()
        while True:
            now = datetime.datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + self.time_window

            logger.info(
                f"[QuizCog] Time window für '{area}' bis {window_end.strftime('%H:%M:%S')}"
            )

            # Zufälliger Zeitpunkt in der ersten Hälfte des Fensters
            latest = window_start + (self.time_window / 2)
            delta = (latest - now).total_seconds()
            next_time = now + datetime.timedelta(
                seconds=random.uniform(0, delta)
            ) if delta > 0 else now

            # Kurze zusätzliche Zufallsverzögerung (bis zu Hälfte des Fensters)
            delay = random.uniform(0, (self.time_window.total_seconds() / 2))
            actual_post_time = next_time + datetime.timedelta(seconds=delay)

            # **Logging des genauen Frage‐Zeitpunkts**
            logger.info(
                f"[QuizCog] Für '{area}' geplante Frage ungefähr um {actual_post_time.strftime('%H:%M:%S')}"
            )

            # Bis zum geplanten Zeitpunkt warten
            await asyncio.sleep(max((next_time - now).total_seconds(), 0))
            # Dann noch Verzögerung abwarten
            await asyncio.sleep(delay)

            # Versuche, eine Frage zu stellen
            await self.prepare_question(area, window_end)

            # Warte bis Ende des Fensters
            seconds_to_end = (
                window_end - datetime.datetime.utcnow()).total_seconds()
            if seconds_to_end > 0:
                await asyncio.sleep(seconds_to_end)

            # Nach Ende des Fensters: aufräumen
            cid = self.bot.quiz_data[area]["channel_id"]
            self.awaiting_activity.pop(cid, None)

            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def prepare_question(self, area: str, end_time: datetime.datetime):
        """
        Prüft, ob im entsprechenden Channel genügend Nachrichten
        (>=10) seit letzter Frage gepostet wurden. Wenn ja, stellt
        ask_question; andernfalls merkt sich, dass gewartet werden muss.
        """
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            logger.error(
                f"[QuizCog] Channel für Area '{area}' nicht gefunden.")
            return

        # Wenn bereits eine Frage aktiv, nichts tun
        if area in self.current_questions:
            logger.warning(f"[QuizCog] Frage für '{area}' läuft bereits.")
            return

        cid = channel.id

        # Erster Start (nach Init): einfach aktiv genug, ohne Aktivitätscheck
        if not self.channel_initialized[cid]:
            self.channel_initialized[cid] = True
            logger.info(
                f"[QuizCog] Erster Start in {channel.name}, überspringe Aktivitätsprüfung."
            )
        # Falls Counter <10, merken und verschieben
        elif self.message_counter[cid] < 10:
            logger.info(
                f"[QuizCog] Zu wenig Aktivität in {channel.name}, verschiebe Frage."
            )
            self.awaiting_activity[cid] = (area, end_time)
            return

        # Wenn genügend Aktivität, neue Frage stellen
        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime):
        """
        Sendet die Quizfrage (dynamisch für WCR oder aus JSON)
        und startet Timer, damit später close_question aufgerufen wird.
        """
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        qg = cfg["question_generator"]

        # Dynamische WCR-Fragen begrenzen
        if area == "wcr" and self.wcr_question_count < self.max_wcr_dynamic_questions:
            qd = qg.generate_dynamic_question("wcr")
            self.wcr_question_count += 1
        else:
            qd = qg.generate_question_from_json(area)
            if area == "wcr":
                self.wcr_question_count = 0

        if not qd:
            logger.warning(f"[QuizCog] Keine Frage generiert für '{area}'.")
            return

        frage_text = qd["frage"]
        correct_answers = set(qd["antwort"])
        data_loader = cfg["data_loader"]

        embed = discord.Embed(
            title=f"Quiz für {area.upper()}",
            description=frage_text,
            color=discord.Color.blue()
        )
        embed.add_field(name="Kategorie", value=qd.get(
            "category", "–"), inline=False)
        embed.set_footer(text="Klicke auf 'Antworten', um zu antworten.")

        view = AnswerButtonView(
            area=area,
            correct_answers=correct_answers,
            data_loader=data_loader,
            cog=self
        )

        sent_msg = await channel.send(embed=embed, view=view)

        # Frage speichern: message_id, Endzeitpunkt und korrekte Antworten
        self.current_questions[area] = {
            "message_id": sent_msg.id,
            "end_time": end_time,
            "answers": correct_answers
        }
        # Zurücksetzen: wer schon geantwortet hat
        self.answered_users[area].clear()
        # Counter im Channel zurücksetzen (wir zählen erst wieder ab hier neu)
        self.message_counter[channel.id] = 0
        # Falls bis geradehin eine verspätete Freigabe geplant war, aufräumen
        self.awaiting_activity.pop(channel.id, None)

        logger.info(f"[QuizCog] Frage gesendet in '{area}': {frage_text}")

        # Timer bis close_question (Timeout)
        now = datetime.datetime.utcnow()
        verbleibende = (end_time - now).total_seconds()
        await asyncio.sleep(max(verbleibende, 0))
        await self.close_question(area, timed_out=True)

    async def close_question(self, area: str, timed_out: bool = False):
        """
        Schließt die aktuell laufende Frage (beim Timeout oder korrekter Antwort).
        """
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if area not in self.current_questions:
            return

        qinfo = self.current_questions.pop(area)
        try:
            msg = await channel.fetch_message(qinfo["message_id"])
            footer = " ⏰ Zeit abgelaufen!" if timed_out else " ✅ Richtig beantwortet!"
            embed = msg.embeds[0]
            embed.color = discord.Color.red()
            embed.set_footer(text=embed.footer.text + footer)
            # Remove die View (Buttons), damit niemand mehr klicken kann
            await msg.edit(embed=embed, view=None)
        except Exception as e:
            logger.warning(
                f"[QuizCog] Beim Schließen der Frage für '{area}' ist ein Fehler aufgetreten: {e}"
            )

        # Channel darf beim nächsten Fenster erneut Activity-Check überspringen
        self.channel_initialized[cfg["channel_id"]] = False
        logger.info(
            f"[QuizCog] Frage beendet in '{area}'{' (Timeout)' if timed_out else ''}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Zählt echte User-Nachrichten pro Channel (live increment)
        und überprüft nur Interrupts für verspätete Freigaben.
        Antworten erfolgen ausschließlich über die Buttons/Modals.
        """
        if message.author.bot:
            return

        cid = message.channel.id
        # Live-Zähler: Erhöhe bei jeder User-Nachricht
        self.message_counter[cid] += 1
        logger.debug(
            f"[QuizCog] Counter für {message.channel.name}: {self.message_counter[cid]}")

        # Verspätete Freigabe: Wenn zuvor <10 Nachrichten & jetzt ≥10
        if cid in self.awaiting_activity and self.message_counter[cid] >= 10:
            area, end_time = self.awaiting_activity[cid]
            await self.ask_question(area, end_time)
