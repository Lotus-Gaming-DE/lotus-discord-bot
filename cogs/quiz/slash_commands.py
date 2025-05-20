# cogs/quiz/slash_commands.py

import discord
from discord import app_commands
from discord.ext import commands
from typing import Literal


class QuizCommands(commands.GroupCog, name="quiz"):
    def __init__(self, bot: commands.Bot, quiz_cog):
        self.bot = bot
        self.quiz_cog = quiz_cog
        super().__init__()

    def is_authorized(self, user: discord.Member) -> bool:
        return any(r.name == "Community Mod" for r in user.roles) or user.guild_permissions.administrator

    def get_area_by_channel(self, channel_id: int):
        for area, config in self.quiz_cog.areas_config.items():
            if config['channel_id'] == channel_id:
                return area
        return None

    async def interaction_checks(self, interaction: discord.Interaction) -> tuple[bool, str | None]:
        if not self.is_authorized(interaction.user):
            return False, "Du hast keine Berechtigung, diesen Befehl zu verwenden."

        area = self.get_area_by_channel(interaction.channel.id)
        if not area:
            return False, "In diesem Channel ist kein Quiz konfiguriert."

        return True, area

    @app_commands.command(name="time", description="Setze das Zeitfenster für neue Fragen (in Minuten)")
    async def time(self, interaction: discord.Interaction, minuten: app_commands.Range[int, 1, 120]):
        ok, result = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(result, ephemeral=True)
            return

        minutes = minuten
        self.quiz_cog.time_window = discord.utils.utcnow().__class__(minutes=minutes)
        await interaction.response.send_message(f"⏱️ Das Zeitfenster wurde auf {minutes} Minuten gesetzt.", ephemeral=True)

    @app_commands.command(name="language", description="Setze die Sprache für das Quiz")
    async def language(self, interaction: discord.Interaction, sprache: Literal["de", "en"]):
        ok, area = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area, ephemeral=True)
            return

        self.quiz_cog.area_data[area]['data_loader'].set_language(sprache)
        await interaction.response.send_message(f"🌐 Sprache für `{area}` wurde auf **{sprache}** gesetzt.", ephemeral=True)

    @app_commands.command(name="ask", description="Stellt sofort eine neue Frage")
    async def ask(self, interaction: discord.Interaction):
        ok, area = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area, ephemeral=True)
            return

        channel = interaction.channel
        end_time = discord.utils.utcnow() + self.quiz_cog.time_window
        await self.quiz_cog.ask_question(area, end_time)
        await interaction.response.send_message("✅ Frage wurde gestellt und das Zeitfenster neu gestartet.", ephemeral=False)

    @app_commands.command(name="answer", description="Zeigt die Antwort zur aktuellen Frage")
    async def answer(self, interaction: discord.Interaction):
        ok, area = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area, ephemeral=True)
            return

        question = self.quiz_cog.current_questions.get(area)
        if not question:
            await interaction.response.send_message("📭 Es ist aktuell keine Frage aktiv.", ephemeral=True)
            return

        antworten = question['correct_answers']
        antwort_text = ", ".join(f"`{a}`" for a in antworten)
        await interaction.channel.send(f"📢 Die richtige Antwort lautet: {antwort_text}")
        await self.quiz_cog.close_question(area)
        await interaction.response.send_message("✅ Die Antwort wurde veröffentlicht und die Frage geschlossen.", ephemeral=False)

    @app_commands.command(name="status", description="Zeigt den Status des aktuellen Quiz")
    async def status(self, interaction: discord.Interaction):
        ok, area = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area, ephemeral=True)
            return

        question = self.quiz_cog.current_questions.get(area)
        msg_count = self.quiz_cog.message_counter.get(
            interaction.channel.id, 0)
        if question:
            remaining = int(
                (question['end_time'] - discord.utils.utcnow()).total_seconds())
            await interaction.response.send_message(
                f"📊 Eine Frage ist aktiv. Noch {remaining} Sekunden. Nachrichten seit Beginn: {msg_count}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("📊 Derzeit ist keine Frage aktiv.", ephemeral=True)

    @app_commands.command(name="disable", description="Deaktiviert das Quiz für diesen Channel")
    async def disable(self, interaction: discord.Interaction):
        ok, area = await self.interaction_checks(interaction)
        if not ok:
            await interaction.response.send_message(area, ephemeral=True)
            return

        self.quiz_cog.areas_config.pop(area)
        await interaction.response.send_message(f"🚫 Das Quiz für `{area}` wurde deaktiviert.", ephemeral=False)

    @app_commands.command(name="enable", description="Aktiviert das Quiz erneut für diesen Channel")
    async def enable(self, interaction: discord.Interaction, area_name: str, sprache: Literal["de", "en"] = "de"):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message("Du hast keine Berechtigung, diesen Befehl zu verwenden.", ephemeral=True)
            return

        area = area_name.lower()
        self.quiz_cog.areas_config[area] = {
            'channel_id': interaction.channel.id,
            'language': sprache
        }

        data_loader = DataLoader()
        data_loader.set_language(sprache)
        question_generator = QuestionGenerator(data_loader)
        self.quiz_cog.area_data[area] = {
            'data_loader': data_loader,
            'question_generator': question_generator
        }

        self.quiz_cog.bot.loop.create_task(self.quiz_cog.quiz_scheduler(area))

        await interaction.response.send_message(f"✅ Das Quiz wurde für `{area}` aktiviert.", ephemeral=False)
