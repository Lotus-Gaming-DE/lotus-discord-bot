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

        # Prüfen, ob Antwort korrekt (case-insensitive)
        matched = next(
            (a for a in self.correct_answers if a.lower() == eingabe.lower()), None
        )

        if matched is not None:
            # Punktestand updaten
            scores = self.data_loader.load_scores()
            scores[str(user_id)] = scores.get(str(user_id), 0) + 1
            self.data_loader.save_scores(scores)

            await interaction.response.send_message(
                "🏆 Richtig! Du erhältst einen Punkt.", ephemeral=True
            )
            # Frage schließen (mit Winner und korrekter Antwort)
            await self.cog.close_question(
                area=self.area,
                timed_out=False,
                winner=interaction.user,
                correct_answer=matched
            )
            logger.info(
                f"[QuizCog] {interaction.user} richtig in '{self.area}': {matched}"
            )
        else:
            self.cog.answered_users[self.area].add(user_id)
            await interaction.response.send_message(
                "❌ Falsch.", ephemeral=True
            )
            logger.info(
                f"[QuizCog] {interaction.user} falsch in '{self.area}': {eingabe}"
            )


class AnswerButtonView(View):
    def __init__(self, area: str, correct_answers: set, data_loader, cog):
        super().__init__(timeout=None)
        self.area = area
        self.correct_answers = correct_answers
        self.data_loader = data_loader
        self.cog: QuizCog = cog

    @button(label="Antworten", style=discord.ButtonStyle.primary)
    async def answer_button(self, interaction: discord.Interaction, button: Button):
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
    """Core-Quiz-Logic: Scheduling, Fragen posten, Antworten verarbeiten"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Aktuell laufende Fragen pro Area
        self.current_questions: dict[str, dict] = {}
        # Welche Nutzer bereits geantwortet haben (pro Area)
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        # Zähler echter User-Nachrichten pro Channel
        self.message_counter: dict[int, int] = defaultdict(int)
        # Haben wir in diesem Channel bereits die History geprüft?
        self.channel_initialized: dict[int, bool] = defaultdict(bool)
        # Wenn <10 Nachrichten, merken wir uns (area, end_time), bis es 10 werden
        self.awaiting_activity: dict[int, tuple[str, datetime.datetime]] = {}

        # Für WCR-dynamische Fragen: maximal 5 pro Zyklus
        self.max_wcr_dynamic_questions = 5
        self.wcr_question_count = 0

        # Standard-Zeitfenster: 15 Minuten
        self.time_window = datetime.timedelta(minutes=15)

        # Für jede konfigurierte Area sofort den Scheduler-Loop starten
        for area in self.bot.quiz_data.keys():
            self.bot.loop.create_task(self.quiz_scheduler(area))

        # Einmalig: Nachrichtenzähler initialisieren (sobald Bot ready)
        self.bot.loop.create_task(self._initialize_message_counters())

    async def _initialize_message_counters(self):
        """
        Wir prüfen die letzten 20 Nachrichten in jedem Quiz-Channel,
        zählen die User-Nachrichten seit der letzten Quizfrage und
        setzen dann self.message_counter dort.
        Wenn keine alte Frage gefunden → Counter=10 (sofort posten).
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

                # Suche nach der letzten Quizfrage (Embed-Titel „Quiz für AREA“)
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
                    # Echte User-Nachrichten nach dieser Embed
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
                    # Keine Quizfrage gefunden → sofort aktiv (Counter=10)
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

            # Falls beim Start noch eine abgelaufene Frage existiert, entfernen
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
        Für jede Area läuft fortlaufend:
         1) Neues Zeitfenster [jetzt, jetzt + self.time_window]
         2) Wähle zufälligen Zeitpunkt in erster Hälfte
         3) Warte bis dahin + leichte Zufallsverzögerung
         4) Rufe prepare_question(area, window_end) auf
         5) Warte bis window_end, rufe close_question wenn nötig
         6) Neu starten
        """
        # ── Falls Area inzwischen deaktiviert wurde, sofort abbrechen
        await self.bot.wait_until_ready()
        if area not in self.bot.quiz_data:
            return

        while True:
            now = datetime.datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + self.time_window

            logger.info(
                f"[QuizCog] Time window für '{area}' bis {window_end.strftime('%H:%M:%S')}"
            )

            # Zufälliger Zeitpunkt in erster Hälfte
            latest = window_start + (self.time_window / 2)
            delta = (latest - now).total_seconds()
            next_time = (
                now + datetime.timedelta(seconds=random.uniform(0, delta))
                if delta > 0
                else now
            )

            # Zusätzliche Zufallsverzögerung (bis zu Hälfte des Fensters)
            delay = random.uniform(0, (self.time_window.total_seconds() / 2))
            actual_post_time = next_time + datetime.timedelta(seconds=delay)

            logger.info(
                f"[QuizCog] Für '{area}' geplante Frage ungefähr um {actual_post_time.strftime('%H:%M:%S')}"
            )

            # Warte bis zum ersten Zeitpunkt
            await asyncio.sleep(max((next_time - now).total_seconds(), 0))
            # Warte dann noch die „delay“
            await asyncio.sleep(delay)

            # ── Falls Area inzwischen deaktiviert wurde, abbrechen
            if area not in self.bot.quiz_data:
                return

            # Versuche, Frage zu stellen
            await self.prepare_question(area, window_end)

            # Warte bis Ende des Fensters
            seconds_to_end = (
                window_end - datetime.datetime.utcnow()).total_seconds()
            if seconds_to_end > 0:
                await asyncio.sleep(seconds_to_end)

            # Nach Ende: ggf. offene Frage schließen
            cid = self.bot.quiz_data[area]["channel_id"]
            self.awaiting_activity.pop(cid, None)
            if area in self.current_questions:
                await self.close_question(area, timed_out=True)

    async def prepare_question(self, area: str, end_time: datetime.datetime):
        """
        Wenn im Channel ≥ 10 User-Nachrichten seit letzter Frage,
        wird ask_question aufgerufen. Sonst merken wir uns „awaiting_activity“.
        """
        # ── Falls Area inzwischen deaktiviert wurde, sofort abbrechen
        if area not in self.bot.quiz_data:
            return

        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if not channel:
            logger.error(
                f"[QuizCog] Channel für Area '{area}' nicht gefunden."
            )
            return

        # Wenn bereits aktive Frage, abbrechen
        if area in self.current_questions:
            logger.warning(f"[QuizCog] Frage für '{area}' läuft bereits.")
            return

        cid = channel.id

        # Erster Start: skip Activity-Check
        if not self.channel_initialized[cid]:
            self.channel_initialized[cid] = True
            logger.info(
                f"[QuizCog] Erster Start in {channel.name}, überspringe Aktivitätsprüfung."
            )
        # Wenn <10 Nachrichten, auf später verschieben
        elif self.message_counter[cid] < 10:
            logger.info(
                f"[QuizCog] Zu wenig Aktivität in {channel.name} ({self.message_counter[cid]} Nachrichten), verschiebe Frage."
            )
            self.awaiting_activity[cid] = (area, end_time)
            return

        # Ansonsten: neue Frage
        await self.ask_question(area, end_time)

    async def ask_question(self, area: str, end_time: datetime.datetime):
        """
        Baut das Embed + Button-View, postet es und speichert qinfo.
        Dann wartet es bis end_time und ruft close_question(area, timed_out=True).
        """
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        qg = cfg["question_generator"]

        # Dynamische WCR-Fragen nur bis max_wcr_dynamic_questions
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

        # ── Hier passt der neue Block, um aus List oder String immer ein Set[str] zu machen:
        raw_answer = qd["antwort"]
        if isinstance(raw_answer, list):
            correct_answers = raw_answer  # Belasse es als List
        else:
            correct_answers = [raw_answer]

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

        # Speichern: message_id, Endzeit, Antworten
        self.current_questions[area] = {
            "message_id": sent_msg.id,
            "end_time": end_time,
            "answers": correct_answers
        }
        self.answered_users[area].clear()
        self.message_counter[channel.id] = 0
        self.awaiting_activity.pop(channel.id, None)

        logger.info(f"[QuizCog] Frage gesendet in '{area}': {frage_text}")

        now = datetime.datetime.utcnow()
        verbleibende = (end_time - now).total_seconds()
        await asyncio.sleep(max(verbleibende, 0))
        await self.close_question(area, timed_out=True)

    async def close_question(
        self,
        area: str,
        timed_out: bool = False,
        winner: discord.User = None,
        correct_answer: str = None
    ):
        """
        Schließt die laufende Frage:
        • Rot färben, Footer aktualisieren, Winner-Name einfügen
        • Richtige Antwort als eigenes Field hinzufügen
        • Buttons/View entfernen
        """
        cfg = self.bot.quiz_data[area]
        channel = self.bot.get_channel(cfg["channel_id"])
        if area not in self.current_questions:
            return

        qinfo = self.current_questions.pop(area)
        try:
            msg = await channel.fetch_message(qinfo["message_id"])
            embed = msg.embeds[0]
            embed.color = discord.Color.red()

            # 1) Footer-Text anpassen
            if timed_out:
                footer_text = "⏰ Zeit abgelaufen!"
            else:
                footer_text = "✅ Richtig beantwortet!"
            if winner:
                footer_text += f" • {winner.display_name} hat gewonnen."
            # Falls per Mod-Befehl beendet (winner=None, correct_answer=None):
            if not timed_out and winner is None and correct_answer is None:
                footer_text = "✋ Frage durch Mod beendet."
            embed.set_footer(text=footer_text)

            # 2) „Richtige Antwort“ sauber formatieren (kein Set sichtbar)
            answers_list = qinfo["answers"]
            ans_text = ", ".join(answers_list)
            embed.add_field(name="Richtige Antwort",
                            value=ans_text, inline=False)

            # 3) Entferne die Button-View und editiere das Embed
            await msg.edit(embed=embed, view=None)
        except Exception as e:
            logger.warning(
                f"[QuizCog] Fehler beim Schließen der Frage für '{area}': {e}"
            )

        # Kanal für das nächste Zeitfenster wieder neu initialisieren
        self.channel_initialized[cfg["channel_id"]] = False

        # 4) Logging:
        if timed_out:
            logger.info(
                f"[QuizCog] Frage in '{area}' (Timeout) beendet; richtige Antwort: {', '.join(qinfo['answers'])}"
            )
        elif winner:
            logger.info(
                f"[QuizCog] Frage in '{area}' richtig beantwortet von "
                f"{winner.display_name}: {correct_answer}"
            )
        else:
            # Mod hat die Frage manuell beendet
            logger.info(
                f"[QuizCog] Frage in '{area}' per Mod-Befehl beendet; Antwort(en): {', '.join(qinfo['answers'])}"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Erhöht den Live-Nachrichten-Zähler;
        wenn wir zuvor <10 Nachrichten hatten und jetzt ≥10,
        rufen wir ask_question(…) auf.
        Antworten selbst laufen über Buttons/Modals (nicht hier).
        """
        if message.author.bot:
            return

        cid = message.channel.id
        # Live-Zähler hochzählen
        self.message_counter[cid] += 1
        logger.debug(
            f"[QuizCog] Counter für {message.channel.name}: {self.message_counter[cid]}"
        )

        # Wenn gerade „awaiting_activity“ aktiv war und nun ≥10 Nachrichten:
        if cid in self.awaiting_activity and self.message_counter[cid] >= 10:
            area, end_time = self.awaiting_activity[cid]
            await self.ask_question(area, end_time)
