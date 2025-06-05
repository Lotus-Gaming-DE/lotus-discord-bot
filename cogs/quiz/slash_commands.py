# cogs/quiz/slash_commands.py

import json
import datetime

from log_setup import get_logger
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .cog import QuizCog
from .question_generator import QuestionGenerator
from .duel import DuelInviteView, DuelConfig

logger = get_logger(__name__)

quiz_group = app_commands.Group(
    name="quiz",
    description="Quiz‐Befehle",
)

AREA_CONFIG_PATH = "data/pers/quiz/areas.json"


def get_area_by_channel(bot: commands.Bot, channel_id: int) -> Optional[str]:
    """Return the quiz area configured for the given channel."""
    for area, cfg in bot.quiz_data.items():
        if cfg.channel_id == channel_id:
            return area
    return None


def save_area_config(bot: commands.Bot):
    """Persist ``bot.quiz_data`` to ``AREA_CONFIG_PATH``."""
    out = {}
    for area, cfg in bot.quiz_data.items():
        out[area] = {
            "channel_id": cfg.channel_id,
            "window_timer": int(cfg.time_window.total_seconds() / 60),
            "language": cfg.language,
            "active": cfg.active,
            "activity_threshold": cfg.activity_threshold,
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

    interaction.client.quiz_data[area].time_window = datetime.timedelta(
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

    interaction.client.quiz_data[area].language = lang
    save_area_config(interaction.client)

    await interaction.response.send_message(f"🌐 Sprache für **{area}** auf **{lang}** gesetzt.", ephemeral=True)


@quiz_group.command(name="threshold", description="Aktivitätsschwelle für automatische Fragen setzen")
@app_commands.describe(value="Nachrichten bis zur nächsten Frage (1–50)")
@app_commands.default_permissions(manage_guild=True)
async def threshold(interaction: discord.Interaction, value: app_commands.Range[int, 1, 50]):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    interaction.client.quiz_data[area].activity_threshold = value
    save_area_config(interaction.client)

    await interaction.response.send_message(f"📈 Aktivitätsschwelle auf **{value}** gesetzt.", ephemeral=True)


@quiz_group.command(name="enable", description="Quiz in diesem Channel aktivieren")
@app_commands.describe(area_name="Name der Area (z. B. wcr, d4, ptcgp)", lang="de oder en")
@app_commands.default_permissions(manage_guild=True)
async def enable(interaction: discord.Interaction, area_name: str, lang: Literal["de", "en"] = "de"):
    area = area_name.lower()

    if area not in interaction.client.quiz_data:
        await interaction.response.send_message("❌ Diese Area ist nicht bekannt oder nicht geladen.", ephemeral=True)
        return

    cfg = interaction.client.quiz_data[area]
    cfg.channel_id = interaction.channel.id
    cfg.language = lang
    cfg.active = True

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
    cfg.active = False
    save_area_config(interaction.client)

    await interaction.response.send_message(f"🚫 Quiz für **{area}** deaktiviert.", ephemeral=False)


@quiz_group.command(name="ask", description="Sofort eine Quizfrage posten")
@app_commands.default_permissions(manage_guild=True)
async def ask(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    time_window = interaction.client.quiz_data[area].time_window
    end_time = datetime.datetime.utcnow() + time_window
    await quiz_cog.manager.ask_question(area, end_time)

    await interaction.response.send_message("✅ Die Frage wurde erstellt.", ephemeral=False)


@quiz_group.command(name="duel", description="Starte ein Quiz-Duell (bo3, bo5, dynamic)")
@app_commands.describe(punkte="Gesetzte Punkte", modus="bo3, bo5 oder dynamic")
async def duel(interaction: discord.Interaction, punkte: app_commands.Range[int, 1, 10000], modus: Literal["bo3", "bo5", "dynamic"] = "bo3"):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True)
        return

    qg: QuestionGenerator = interaction.client.quiz_data[area].question_generator
    if modus == "dynamic" and area not in qg.dynamic_providers:
        await interaction.response.send_message("❌ Dieser Modus ist hier nicht verfügbar.", ephemeral=True)
        return

    champion_cog = interaction.client.get_cog("ChampionCog")
    if champion_cog is None:
        await interaction.response.send_message("❌ Champion-System nicht verfügbar.", ephemeral=True)
        return
    total = await champion_cog.data.get_total(str(interaction.user.id))
    if total < punkte:
        await interaction.response.send_message("❌ Du hast nicht genügend Punkte.", ephemeral=True)
        return

    cfg = DuelConfig(area=area, points=punkte, mode=modus)
    view = DuelInviteView(interaction.user, cfg, interaction.client.get_cog("QuizCog"))
    embed = discord.Embed(title="Quiz-Duell", description=f"{interaction.user.mention} fordert einen Gegner heraus!", color=discord.Color.orange())
    embed.add_field(name="Einsatz", value=f"{punkte} Punkte")
    embed.add_field(name="Modus", value=modus)
    msg = await interaction.channel.send(embed=embed, view=view)
    view.message = msg
    await interaction.response.send_message("Duelleinladung erstellt.", ephemeral=True)


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
            quiz_cog.bot.quiz_data[area].channel_id)
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


@quiz_group.command(name="reset", description="Setzt die Frage-Historie für diesen Channel zurück")
@app_commands.default_permissions(manage_guild=True)
async def reset(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message("❌ Kein Quiz in diesem Channel.", ephemeral=True)
        return

    state = interaction.client.quiz_data[area].question_state
    state.reset_asked_questions(area)
    await interaction.response.send_message(f"♻️ Frageverlauf für **{area}** wurde zurückgesetzt.", ephemeral=True)


@quiz_group.error
async def on_quiz_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    logger.exception(f"[QuizCommands] Fehler: {error}")
