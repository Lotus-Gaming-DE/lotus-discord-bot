import os
import logging
import datetime
from typing import Literal, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from .cog import QuizCog
from .data_loader import DataLoader
from .question_generator import QuestionGenerator

logger = logging.getLogger(__name__)  # e.g. 'cogs.quiz.slash_commands'

SERVER_ID = os.getenv("server_id")
if not SERVER_ID:
    raise ValueError("Environment variable 'server_id' is not set.")
GUILD_ID = int(SERVER_ID)


class QuizCommands(commands.GroupCog, name="quiz", description="Quiz-Befehle"):
    """Slash-Command-Gruppe /quiz …"""

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.quiz_cog: QuizCog = bot.get_cog("QuizCog")

    def is_authorized(self, user: discord.Member) -> bool:
        return (
            any(r.name == "Community Mod" for r in user.roles)
            or user.guild_permissions.administrator
        )

    def get_area_by_channel(self, channel_id: int) -> Optional[str]:
        for area, cfg in self.quiz_cog.area_data.items():
            if cfg["channel_id"] == channel_id:
                return area
        return None

    async def interaction_checks(
        self, interaction: discord.Interaction
    ) -> Tuple[bool, str]:
        if not self.is_authorized(interaction.user):
            return False, "❌ Du hast keine Berechtigung für diesen Befehl."

        area = self.get_area_by_channel(interaction.channel.id)
        if not area:
            return False, "❌ In diesem Channel ist kein Quiz konfiguriert."

        return True, area

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="time", description="Zeitfenster in Minuten setzen")
    async def time(
        self,
        interaction: discord.Interaction,
        minutes: app_commands.Range[int, 1, 120],
    ):
        ok, area_or_msg = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area_or_msg, ephemeral=True)
            return

        logger.info(
            f"[QuizCommands] /quiz time by {interaction.user} -> {minutes}min")
        self.quiz_cog.time_window = datetime.timedelta(minutes=minutes)
        await interaction.response.send_message(
            f"⏱️ Zeitfenster auf **{minutes} Minuten** gesetzt.", ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="language", description="Sprache für dieses Quiz setzen")
    async def language(
        self,
        interaction: discord.Interaction,
        lang: Literal["de", "en"],
    ):
        ok, area_or_msg = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area_or_msg, ephemeral=True)
            return
        area = area_or_msg

        logger.info(
            f"[QuizCommands] /quiz language by {interaction.user} -> {area} = {lang}")
        loader = self.quiz_cog.area_data[area]["data_loader"]
        loader.set_language(lang)
        await interaction.response.send_message(
            f"🌐 Sprache für **{area}** auf **{lang}** gesetzt.", ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="ask", description="Sofortige Frage stellen")
    async def ask(self, interaction: discord.Interaction):
        ok, area_or_msg = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area_or_msg, ephemeral=True)
            return
        area = area_or_msg

        logger.info(
            f"[QuizCommands] /quiz ask by {interaction.user} in {area}")
        end_time = datetime.datetime.utcnow() + self.quiz_cog.time_window
        await self.quiz_cog.ask_question(area, end_time)
        await interaction.response.send_message(
            "✅ Frage gestellt und Timer zurückgesetzt.", ephemeral=False
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="answer", description="Korrekte Antwort anzeigen und Frage schließen"
    )
    async def answer(self, interaction: discord.Interaction):
        ok, area_or_msg = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area_or_msg, ephemeral=True)
            return
        area = area_or_msg

        question = self.quiz_cog.current_questions.get(area)
        if not question:
            await interaction.response.send_message(
                "📭 Aktuell ist keine Frage aktiv.", ephemeral=True
            )
            return

        answers = question["correct_answers"]
        text = ", ".join(f"`{a}`" for a in answers)
        logger.info(
            f"[QuizCommands] /quiz answer by {interaction.user} in {area}")
        await interaction.channel.send(f"📢 Die richtige Antwort ist: {text}")
        await self.quiz_cog.close_question(area)
        await interaction.response.send_message(
            "✅ Antwort veröffentlicht und Frage geschlossen.", ephemeral=False
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="status", description="Status der aktuellen Frage anzeigen")
    async def status(self, interaction: discord.Interaction):
        ok, area_or_msg = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area_or_msg, ephemeral=True)
            return
        area = area_or_msg

        question = self.quiz_cog.current_questions.get(area)
        count = self.quiz_cog.message_counter.get(interaction.channel.id, 0)
        if question:
            remaining = int(
                (question["end_time"] -
                 datetime.datetime.utcnow()).total_seconds()
            )
            await interaction.response.send_message(
                f"📊 Aktive Frage: noch **{remaining}s**. Nachrichten seit Start: **{count}**.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "📊 Aktuell ist keine Frage aktiv.", ephemeral=True
            )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="disable", description="Quiz in diesem Channel deaktivieren")
    async def disable(self, interaction: discord.Interaction):
        ok, area_or_msg = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area_or_msg, ephemeral=True)
            return
        area = area_or_msg

        logger.info(
            f"[QuizCommands] /quiz disable by {interaction.user} in {area}")
        self.quiz_cog.area_data.pop(area, None)
        await interaction.response.send_message(
            f"🚫 Quiz für **{area}** deaktiviert.", ephemeral=False
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="enable", description="Quiz in diesem Channel wieder aktivieren"
    )
    async def enable(
        self,
        interaction: discord.Interaction,
        area_name: str,
        lang: Literal["de", "en"] = "de",
    ):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True
            )
            return

        area = area_name.lower()
        logger.info(
            f"[QuizCommands] /quiz enable by {interaction.user} -> {area} ({lang})")
        cfg = {"channel_id": interaction.channel.id, "language": lang}
        loader = DataLoader()
        loader.set_language(lang)
        gen = QuestionGenerator(loader)
        self.quiz_cog.area_data[area] = {
            "channel_id": interaction.channel.id,
            "language": lang,
            "data_loader": loader,
            "question_generator": gen
        }
        self.bot.loop.create_task(self.quiz_cog.quiz_scheduler(area))

        await interaction.response.send_message(
            f"✅ Quiz für **{area}** aktiviert.", ephemeral=False
        )
