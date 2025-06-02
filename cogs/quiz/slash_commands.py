# cogs/quiz/slash_commands.py

import os
import logging
import datetime
from typing import Literal, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from .cog import QuizCog
from .question_generator import QuestionGenerator

logger = logging.getLogger(__name__)

# Die Guild‐ID als Ganzzahl aus der ENV lesen, damit wir die Befehle nur dort registrieren
SERVER_ID = os.getenv("server_id")
if not SERVER_ID:
    raise ValueError("Environment variable 'server_id' is not set.")
GUILD_ID = int(SERVER_ID)

# Slash‐Command‐Gruppe /quiz
quiz_group = app_commands.Group(
    name="quiz",
    description="Quiz‐Befehle",
    guild_ids=[GUILD_ID]  # Nur in dieser Guild
)


def is_authorized(user: discord.Member) -> bool:
    # Nur Community Mod (Rollenname) oder Administrator dürfen
    return (
        any(r.name == "Community Mod" for r in user.roles)
        or user.guild_permissions.administrator
    )


def get_area_by_channel(bot: commands.Bot, channel_id: int) -> Optional[str]:
    # Sucht in quiz_data die Area, deren channel_id passt
    quiz_cog: QuizCog = bot.get_cog("QuizCog")
    for area, cfg in quiz_cog.bot.quiz_data.items():
        if cfg["channel_id"] == channel_id:
            return area
    return None


async def interaction_checks(
    bot: commands.Bot, interaction: discord.Interaction
) -> Tuple[bool, str]:
    # 1) Autorisierung prüfen
    if not is_authorized(interaction.user):
        return False, "❌ Du hast keine Berechtigung für diesen Befehl."

    # 2) Ist dieser Channel überhaupt als Quiz‐Channel konfiguriert?
    area = get_area_by_channel(bot, interaction.channel.id)
    if not area:
        return False, "❌ In diesem Channel ist kein Quiz konfiguriert."

    return True, area


# ────────────────────────────────────────────────────────────────────────────────

@quiz_group.command(
    name="time",
    description="Zeitfenster (in Minuten) für dieses Quiz setzen"
)
@app_commands.describe(
    minutes="Zeitfenster in Minuten (1–120)"
)
@app_commands.default_permissions(manage_guild=True)
async def time(
    interaction: discord.Interaction,
    minutes: app_commands.Range[int, 1, 120],
):
    ok, area_or_msg = await interaction_checks(interaction.client, interaction)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    logger.info(
        f"[QuizCommands] /quiz time by {interaction.user} → {minutes}min")
    # Ändert global die Zeit, wird von allen Areas gelesen
    quiz_cog.time_window = datetime.timedelta(minutes=minutes)
    await interaction.response.send_message(
        f"⏱️ Zeitfenster auf **{minutes} Minuten** gesetzt.", ephemeral=True
    )


@quiz_group.command(
    name="language",
    description="Sprache (de / en) für dieses Quiz setzen"
)
@app_commands.describe(
    lang="de oder en"
)
@app_commands.default_permissions(manage_guild=True)
async def language(
    interaction: discord.Interaction,
    lang: Literal["de", "en"],
):
    ok, area_or_msg = await interaction_checks(interaction.client, interaction)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    logger.info(
        f"[QuizCommands] /quiz language by {interaction.user} → {area} = {lang}"
    )

    # === HIER: Nur DataLoader updaten, keine eigene JSON‐Logik mehr ===
    data_loader: DataLoader = quiz_cog.bot.data["quiz"]["data_loader"]
    data_loader.set_language(lang)  # intern lädt questions_{lang}.json

    # Jetzt liegen in data_loader.questions_by_area alle relevanten Fragen
    questions_by_area = data_loader.questions_by_area
    asked_questions = data_loader.load_asked_questions()

    # Extrahiere nur 'area'
    this_area_dict = questions_by_area.get(area, {})

    # Baue neuen QuestionGenerator
    new_generator = QuestionGenerator(
        questions_by_area={area: this_area_dict},
        asked_questions=asked_questions,
        dynamic_providers=quiz_cog.bot.quiz_data[area]
        .get("question_generator")
        .dynamic_providers
    )

    # Speichere neuen Generator
    quiz_cog.bot.quiz_data[area]["question_generator"] = new_generator
    quiz_cog.bot.quiz_data[area]["language"] = lang

    # Antwort an den Mod
    await interaction.response.send_message(
        f"🌐 Sprache für **{area}** auf **{lang}** gesetzt.", ephemeral=True
    )


@quiz_group.command(
    name="ask",
    description="Sofort eine Quizfrage posten"
)
@app_commands.default_permissions(manage_guild=True)
async def ask(
    interaction: discord.Interaction,
):
    ok, area_or_msg = await interaction_checks(interaction.client, interaction)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    # Falls die Area in der Zwischenzeit doch rausgenommen wurde, beenden
    if area not in quiz_cog.bot.quiz_data:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    end_time = datetime.datetime.utcnow() + quiz_cog.time_window
    logger.info(f"[QuizCommands] /quiz ask by {interaction.user} in {area}")
    # Frage-Aufgabe im Hintergrund starten (damit wir sofort antworten)
    interaction.client.loop.create_task(quiz_cog.ask_question(area, end_time))

    await interaction.response.send_message(
        "✅ Deine Frage wurde erstellt und läuft bis zum Ende des Zeitfensters.", ephemeral=False
    )


@quiz_group.command(
    name="answer",
    description="Zeige die richtige Antwort und schließe die Frage"
)
@app_commands.default_permissions(manage_guild=True)
async def answer(
    interaction: discord.Interaction,
):
    ok, area_or_msg = await interaction_checks(interaction.client, interaction)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    if area not in quiz_cog.bot.quiz_data:
        # Falls jemand zwischenzeitlich disabled hat, abbrechen
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    question_data = quiz_cog.current_questions.get(area)
    if not question_data:
        await interaction.response.send_message(
            "📭 Aktuell ist keine Frage aktiv.", ephemeral=True
        )
        return

    # 1) Bearbeite Embed (mod-gestoppt)
    try:
        # Hier könnt ihr euren eigenen Text setzen (“per Mod beendet” etc.)
        # Beispiel:
        channel = interaction.client.get_channel(
            quiz_cog.bot.quiz_data[area]["channel_id"])
        msg = await channel.fetch_message(question_data["message_id"])
        embed = msg.embeds[0]
        embed.color = discord.Color.red()
        answers = question_data["answers"]
        if isinstance(answers, (list, set)):
            answer_text = ", ".join(str(a) for a in answers)
        else:
            answer_text = str(answers)
        embed.add_field(name="Richtige Antwort",
                        value=answer_text, inline=False)
        embed.set_footer(text="✋ Frage durch Mod beendet.")
        await msg.edit(embed=embed, view=None)
    except Exception as e:
        logger.warning(f"[QuizCog] Fehler beim Mod-Beenden der Frage: {e}")

    # 2) Antwort direkt zurückmelden (optional – ihr könnt das weglassen, da ja schon im Embed steht)
    # await interaction.response.send_message(
    #     f"☑️ Die Frage wurde per Mod-Befehl beantwortet und beendet.", ephemeral=False
    # )

    # 3) Button-/Timeout-Task der Frage abbrechen, falls aktiv
    #    (z. B. indem ihr current_questions.pop(area) macht oder cancel() auf Timer-Task)
    quiz_cog.current_questions.pop(area, None)

    # 4) Zum Schluss noch die Meldung an den Mod, damit Discord nicht „did not respond“ anzeigt
    await interaction.response.send_message(
        "✅ Die Frage wurde per Mod-Befehl beendet.", ephemeral=True
    )


@quiz_group.command(
    name="status",
    description="Status (Restzeit & Nachrichten‐Zähler) der aktuellen Frage anzeigen"
)
@app_commands.default_permissions(manage_guild=True)
async def status(
    interaction: discord.Interaction,
):
    ok, area_or_msg = await interaction_checks(interaction.client, interaction)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    if area not in quiz_cog.bot.quiz_data:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    question_data = quiz_cog.current_questions.get(area)
    count = quiz_cog.message_counter.get(interaction.channel.id, 0)
    if question_data:
        remaining = int(
            (question_data["end_time"] -
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


@quiz_group.command(
    name="disable",
    description="Quiz in diesem Channel deaktivieren"
)
@app_commands.default_permissions(manage_guild=True)
async def disable(
    interaction: discord.Interaction,
):
    ok, area_or_msg = await interaction_checks(interaction.client, interaction)
    if not ok:
        await interaction.response.send_message(area_or_msg, ephemeral=True)
        return
    area = area_or_msg

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    # Remove area aus quiz_data, Scheduler-Task wird beim nächsten Loop-Ende abbrechen
    quiz_cog.bot.quiz_data.pop(area, None)
    logger.info(
        f"[QuizCommands] /quiz disable by {interaction.user} in {area}")

    await interaction.response.send_message(
        f"🚫 Quiz für **{area}** deaktiviert.", ephemeral=False
    )


@quiz_group.command(
    name="enable",
    description="Quiz in diesem Channel wieder aktivieren"
)
@app_commands.describe(
    area_name="Name der Area (z. B. wcr, d4, ptcgp)",
    lang="de oder en"
)
@app_commands.default_permissions(manage_guild=True)
async def enable(
    interaction: discord.Interaction,
    area_name: str,
    lang: Literal["de", "en"] = "de",
):
    # Rollencheck (Admin/Community Mod)
    if not is_authorized(interaction.user):
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True
        )
        return

    area = area_name.lower()
    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    logger.info(
        f"[QuizCommands] /quiz enable by {interaction.user} → {area} ({lang})")

    # DataLoader aus bot.data["quiz"] wiederholen
    q_loader = quiz_cog.bot.data["quiz"]["data_loader"]
    q_generator = QuestionGenerator(
        questions_by_area=quiz_cog.bot.data["quiz"]["questions_by_area"],
        asked_questions=q_loader.load_asked_questions(),
        dynamic_providers={
            "wcr": quiz_cog.bot.quiz_data.get("wcr", {})
            .get("question_generator")
            .dynamic_providers.get("wcr")
            if quiz_cog.bot.quiz_data.get("wcr")
            else None
        }
    )

    # **WICHTIG**: DataLoader mit abspeichern, damit ask_question() keinen KeyError wirft
    quiz_cog.bot.quiz_data[area] = {
        "channel_id": interaction.channel.id,
        "data_loader": q_loader,
        "question_generator": q_generator,
        "language": lang
    }

    # Neuen Scheduler‐Task starten (falls ihr vorhin disable gemacht hattet)
    interaction.client.loop.create_task(quiz_cog.quiz_scheduler(area))

    await interaction.response.send_message(
        f"✅ Quiz für **{area}** aktiviert.", ephemeral=False
    )


@quiz_group.error
async def on_quiz_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Fängt AppCommand-Fehler (z. B. Range oder Param-Mismatches) auf
    logger.exception(f"[QuizCommands] Fehler: {error}")
    # Discord postet ohnehin eine Default-Fehlermeldung, wenn wir nichts senden.
