# cogs/quiz/slash_commands.py

import logging
import datetime
import os
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .data_loader import DataLoader
from .question_generator import QuestionGenerator
from .cog import QuizCog

logger = logging.getLogger(__name__)
SERVER_ID = os.getenv("server_id")
if not SERVER_ID:
    raise ValueError("Environment variable 'server_id' is not set.")
GUILD_ID = int(SERVER_ID)

quiz_group = app_commands.Group(name="quiz", description="Quiz-Befehle")


def is_authorized(member: discord.Member) -> bool:
    return any(r.name == "Community Mod" for r in member.roles) or member.guild_permissions.administrator


def get_area_by_channel(channel_id: int, cog: QuizCog) -> Optional[str]:
    for area, cfg in cog.area_data.items():
        if cfg["channel_id"] == channel_id:
            return area
    return None


async def interaction_checks(interaction: discord.Interaction, cog: QuizCog) -> tuple[bool, str]:
    if not is_authorized(interaction.user):
        return False, "❌ Du hast keine Berechtigung für diesen Befehl."
    area = get_area_by_channel(interaction.channel.id, cog)
    if not area:
        return False, "❌ In diesem Channel ist kein Quiz konfiguriert."
    return True, area


@quiz_group.command(name="time", description="Zeitfenster in Minuten setzen")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def time(interaction: discord.Interaction, minutes: app_commands.Range[int, 1, 120]):
    cog: QuizCog = interaction.client.get_cog("QuizCog")
    ok, area_or_msg = await interaction_checks(interaction, cog)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return

    cog.time_window = datetime.timedelta(minutes=minutes)
    await interaction.response.send_message(
        f"⏱️ Zeitfenster auf **{minutes} Minuten** gesetzt.", ephemeral=True
    )


@quiz_group.command(name="language", description="Sprache für dieses Quiz setzen")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def language(interaction: discord.Interaction, lang: Literal["de", "en"]):
    cog: QuizCog = interaction.client.get_cog("QuizCog")
    ok, area_or_msg = await interaction_checks(interaction, cog)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg
    loader = cog.area_data[area]["data_loader"]
    loader.set_language(lang)
    await interaction.response.send_message(
        f"🌐 Sprache für **{area}** auf **{lang}** gesetzt.", ephemeral=True
    )


@quiz_group.command(name="ask", description="Sofortige Frage stellen")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def ask(interaction: discord.Interaction):
    cog: QuizCog = interaction.client.get_cog("QuizCog")
    ok, area_or_msg = await interaction_checks(interaction, cog)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg
    end_time = datetime.datetime.utcnow() + cog.time_window
    await cog.ask_question(area, end_time)
    await interaction.response.send_message("✅ Frage gestellt.", ephemeral=False)


@quiz_group.command(name="answer", description="Korrekte Antwort anzeigen und Frage schließen")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def answer(interaction: discord.Interaction):
    cog: QuizCog = interaction.client.get_cog("QuizCog")
    ok, area_or_msg = await interaction_checks(interaction, cog)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg

    question = cog.current_questions.get(area)
    if not question:
        await interaction.response.send_message("📭 Keine aktive Frage.", ephemeral=True)
        return

    answers = question["correct_answers"]
    await interaction.channel.send("📢 Die richtige Antwort ist: " + ", ".join(f"`{a}`" for a in answers))
    await cog.close_question(area)
    await interaction.response.send_message("✅ Frage beendet.", ephemeral=False)


@quiz_group.command(name="status", description="Zeigt Status der aktuellen Frage")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def status(interaction: discord.Interaction):
    cog: QuizCog = interaction.client.get_cog("QuizCog")
    ok, area_or_msg = await interaction_checks(interaction, cog)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg
    question = cog.current_questions.get(area)
    count = cog.message_counter.get(interaction.channel.id, 0)
    if question:
        remaining = int(
            (question["end_time"] - datetime.datetime.utcnow()).total_seconds())
        await interaction.response.send_message(
            f"📊 Noch **{remaining}s** übrig. Aktivität: **{count} Nachrichten**.", ephemeral=True
        )
    else:
        await interaction.response.send_message("📭 Keine aktive Frage.", ephemeral=True)


@quiz_group.command(name="disable", description="Quiz in diesem Channel deaktivieren")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def disable(interaction: discord.Interaction):
    cog: QuizCog = interaction.client.get_cog("QuizCog")
    ok, area_or_msg = await interaction_checks(interaction, cog)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg
    cog.area_data.pop(area, None)
    await interaction.response.send_message(f"🚫 Quiz für **{area}** deaktiviert.", ephemeral=False)


@quiz_group.command(name="enable", description="Quiz für diesen Channel aktivieren")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def enable(interaction: discord.Interaction, area_name: str, lang: Literal["de", "en"] = "de"):
    if not is_authorized(interaction.user):
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung.", ephemeral=True
        )
        return

    cog: QuizCog = interaction.client.get_cog("QuizCog")
    area = area_name.lower()
    loader = DataLoader()
    loader.set_language(lang)
    qgen = QuestionGenerator(loader)
    cog.area_data[area] = {
        "channel_id": interaction.channel.id,
        "language": lang,
        "data_loader": loader,
        "question_generator": qgen
    }
    cog.bot.loop.create_task(cog.quiz_scheduler(area))
    await interaction.response.send_message(f"✅ Quiz für **{area}** aktiviert.", ephemeral=False)
