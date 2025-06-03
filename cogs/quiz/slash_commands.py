import os
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


def get_area_by_channel(bot: commands.Bot, channel_id: int) -> Optional[str]:
    quiz_cog: QuizCog = bot.get_cog("QuizCog")
    for area, cfg in quiz_cog.bot.quiz_data.items():
        if cfg["channel_id"] == channel_id:
            return area
    return None


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
    await interaction.response.send_message(f"⏱️ Zeitfenster auf **{minutes} Minuten** gesetzt.", ephemeral=True)


@quiz_group.command(name="language", description="Sprache (de / en) für dieses Quiz setzen")
@app_commands.describe(lang="de oder en")
@app_commands.default_permissions(manage_guild=True)
async def language(interaction: discord.Interaction, lang: Literal["de", "en"]):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    data_loader = quiz_cog.bot.data["quiz"]["data_loader"]
    data_loader.set_language(lang)
    questions_by_area = data_loader.questions_by_area
    this_area_dict = questions_by_area.get(area, {})

    state = quiz_cog.bot.quiz_data[area]["question_state"]
    new_generator = QuestionGenerator(
        questions_by_area={area: this_area_dict},
        state_manager=state,
        dynamic_providers=quiz_cog.bot.quiz_data[area]["question_generator"].dynamic_providers
    )

    quiz_cog.bot.quiz_data[area]["question_generator"] = new_generator
    quiz_cog.bot.quiz_data[area]["language"] = lang

    await interaction.response.send_message(f"🌐 Sprache für **{area}** auf **{lang}** gesetzt.", ephemeral=True)


@quiz_group.command(name="ask", description="Sofort eine Quizfrage posten")
@app_commands.default_permissions(manage_guild=True)
async def ask(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    time_window = quiz_cog.bot.quiz_data[area].get(
        "time_window", datetime.timedelta(minutes=15))
    end_time = datetime.datetime.utcnow() + time_window
    interaction.client.loop.create_task(
        quiz_cog.manager.ask_question(area, end_time))
    await interaction.response.send_message("✅ Die Frage wurde erstellt.", ephemeral=False)


@quiz_group.command(name="answer", description="Zeige die richtige Antwort und schließe die Frage")
@app_commands.default_permissions(manage_guild=True)
async def answer(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    question_data = quiz_cog.current_questions.get(area)
    if not question_data:
        await interaction.response.send_message("📭 Aktuell ist keine Frage aktiv.", ephemeral=True)
        return

    try:
        channel = interaction.client.get_channel(
            quiz_cog.bot.quiz_data[area]["channel_id"])
        msg = await channel.fetch_message(question_data["message_id"])
        embed = msg.embeds[0]
        embed.color = discord.Color.red()

        answers = question_data["answers"]
        answer_text = ", ".join(str(a) for a in answers) if isinstance(
            answers, (list, set)) else str(answers)
        embed.add_field(name="Richtige Antwort",
                        value=answer_text, inline=False)
        embed.set_footer(text="✋ Frage durch Mod beendet.")
        await msg.edit(embed=embed, view=None)
    except Exception as e:
        logger.warning(f"[QuizCog] Fehler beim Mod-Beenden der Frage: {e}")

    quiz_cog.current_questions.pop(area, None)
    await interaction.response.send_message("✅ Die Frage wurde beendet.", ephemeral=True)


@quiz_group.command(name="status", description="Status (Restzeit & Nachrichten‐Zähler) der aktuellen Frage anzeigen")
@app_commands.default_permissions(manage_guild=True)
async def status(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    question_data = quiz_cog.current_questions.get(area)
    count = quiz_cog.tracker.get(interaction.channel.id)
    if question_data:
        remaining = int(
            (question_data["end_time"] - datetime.datetime.utcnow()).total_seconds())
        await interaction.response.send_message(
            f"📊 Aktive Frage: noch **{remaining}s**. Nachrichten seit Start: **{count}**.", ephemeral=True
        )
    else:
        await interaction.response.send_message("📊 Aktuell ist keine Frage aktiv.", ephemeral=True)


@quiz_group.command(name="disable", description="Quiz in diesem Channel deaktivieren")
@app_commands.default_permissions(manage_guild=True)
async def disable(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    quiz_cog.bot.quiz_data.pop(area, None)
    await interaction.response.send_message(f"🚫 Quiz für **{area}** deaktiviert.", ephemeral=False)


@quiz_group.command(name="enable", description="Quiz in diesem Channel wieder aktivieren")
@app_commands.describe(area_name="Name der Area (z. B. wcr, d4, ptcgp)", lang="de oder en")
@app_commands.default_permissions(manage_guild=True)
async def enable(interaction: discord.Interaction, area_name: str, lang: Literal["de", "en"] = "de"):
    area = area_name.lower()
    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")

    q_loader = quiz_cog.bot.data["quiz"]["data_loader"]
    q_loader.set_language(lang)
    questions = q_loader.questions_by_area.get(area, {})

    state = QuestionStateManager(f"data/pers/quiz/state_{area}.json")
    generator = QuestionGenerator(
        questions_by_area={area: questions},
        state_manager=state,
        dynamic_providers={}  # optional: anpassen bei Bedarf
    )

    quiz_cog.bot.quiz_data[area] = {
        "channel_id": interaction.channel.id,
        "data_loader": q_loader,
        "question_generator": generator,
        "question_state": state,
        "language": lang,
        "time_window": datetime.timedelta(minutes=15)
    }

    await interaction.response.send_message(f"✅ Quiz für **{area}** aktiviert.", ephemeral=False)


@quiz_group.command(name="reset", description="Setzt die Frage-Historie für diesen Channel zurück")
@app_commands.default_permissions(manage_guild=True)
async def reset(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ Kein Quiz in diesem Channel.", ephemeral=True)
        return

    state = interaction.client.quiz_data[area]["question_state"]
    state.reset_asked_questions(area)
    await interaction.response.send_message(f"♻️ Frageverlauf für **{area}** wurde zurückgesetzt.", ephemeral=True)


@quiz_group.error
async def on_quiz_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.exception(f"[QuizCommands] Fehler: {error}")
