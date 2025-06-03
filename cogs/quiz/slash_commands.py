import os
import json
import logging
import datetime
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .cog import QuizCog
from .question_generator import QuestionGenerator
from .question_state import QuestionStateManager

logger = logging.getLogger(__name__)

SERVER_ID = os.getenv("server_id")
if not SERVER_ID:
    raise ValueError("Environment variable 'server_id' is not set.")
GUILD_ID = int(SERVER_ID)

quiz_group = app_commands.Group(
    name="quiz",
    description="Quiz‐Befehle",
    guild_ids=[GUILD_ID]
)

AREA_CONFIG_PATH = "data/pers/quiz/areas.json"


def get_area_by_channel(bot: commands.Bot, channel_id: int) -> Optional[str]:
    quiz_cog: QuizCog = bot.get_cog("QuizCog")
    for area, cfg in bot.quiz_data.items():
        if cfg["channel_id"] == channel_id:
            return area
    return None


def save_area_config(bot: commands.Bot):
    out = {}
    for area, cfg in bot.quiz_data.items():
        out[area] = {
            "channel_id": cfg["channel_id"],
            "window_timer": int(cfg["time_window"].total_seconds() / 60),
            "language": cfg["language"],
            "active": cfg.get("active", False),
            "max_dynamic_questions": cfg.get("max_dynamic_questions", 5)
        }
    with open(AREA_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


@quiz_group.command(name="time", description="Zeitfenster (in Minuten) für dieses Quiz setzen")
@app_commands.describe(minutes="Zeitfenster in Minuten (1–120)")
@app_commands.default_permissions(manage_guild=True)
async def time(interaction: discord.Interaction, minutes: app_commands.Range[int, 1, 120]):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    interaction.client.quiz_data[area]["time_window"] = datetime.timedelta(
        minutes=minutes)
    save_area_config(interaction.client)

    await interaction.response.send_message(f"⏱️ Zeitfenster auf **{minutes} Minuten** gesetzt.", ephemeral=True)


@quiz_group.command(name="language", description="Sprache (de / en) für dieses Quiz setzen")
@app_commands.describe(lang="de oder en")
@app_commands.default_permissions(manage_guild=True)
async def language(interaction: discord.Interaction, lang: Literal["de", "en"]):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    interaction.client.quiz_data[area]["language"] = lang
    save_area_config(interaction.client)

    await interaction.response.send_message(f"🌐 Sprache für **{area}** auf **{lang}** gesetzt.", ephemeral=True)


@quiz_group.command(name="enable", description="Quiz in diesem Channel aktivieren")
@app_commands.describe(area_name="Name der Area (z. B. wcr, d4, ptcgp)", lang="de oder en")
@app_commands.default_permissions(manage_guild=True)
async def enable(interaction: discord.Interaction, area_name: str, lang: Literal["de", "en"] = "de"):
    area = area_name.lower()
    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")

    if area not in interaction.client.quiz_data:
        await interaction.response.send_message("❌ Diese Area ist nicht bekannt oder nicht geladen.", ephemeral=True)
        return

    cfg = interaction.client.quiz_data[area]
    cfg["channel_id"] = interaction.channel.id
    cfg["language"] = lang
    cfg["active"] = True

    save_area_config(interaction.client)

    await interaction.response.send_message(f"✅ Quiz für **{area}** aktiviert.", ephemeral=False)


@quiz_group.command(name="disable", description="Quiz in diesem Channel deaktivieren")
@app_commands.default_permissions(manage_guild=True)
async def disable(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    cfg = interaction.client.quiz_data[area]
    cfg["active"] = False
    save_area_config(interaction.client)

    await interaction.response.send_message(f"🚫 Quiz für **{area}** deaktiviert.", ephemeral=False)
