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

# Die Guild-ID als Ganzzahl aus der ENV lesen, damit wir die Befehle nur dort registrieren
SERVER_ID = os.getenv("server_id")
if not SERVER_ID:
    raise ValueError("Environment variable 'server_id' is not set.")
GUILD_ID = int(SERVER_ID)

# Slash-Command-Gruppe /quiz
quiz_group = app_commands.Group(
    name="quiz",
    description="Quiz-Befehle",
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

    # 2) Ist dieser Channel als Quiz-Channel konfiguriert?
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
        f"[QuizCommands] /quiz language by {interaction.user} → {area} = {lang}")
    # Die Fragegenerator-Einstellungen aktualisieren
    quiz_cog.bot.quiz_data[area]["language"] = lang
    quiz_cog.bot.quiz_data[area]["question_generator"].language = lang
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
    end_time = datetime.datetime.utcnow() + quiz_cog.time_window
    logger.info(f"[QuizCommands] /quiz ask by {interaction.user} in {area}")

    # WICHTIG: Erst die Interaction sofort beantworten (defer),
    # damit wir kein 3-Sekunden-Timeout bekommen.
    await interaction.response.defer(thinking=True)

    # Frage im Hintergrund posten:
    # (die ask_question-Methode selbst sitzt in QuizCog und wartet dann bis end_time,
    # um die Frage ggf. automatisch zu schließen)
    interaction.client.loop.create_task(quiz_cog.ask_question(area, end_time))

    # Jetzt eine finale Follow-Up-Nachricht schicken
    await interaction.followup.send(
        "✅ Deine Frage wurde erstellt und läuft bis zum Ende des Zeitfensters.",
        ephemeral=True
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
    question = quiz_cog.current_questions.get(area)
    if not question:
        await interaction.response.send_message(
            "📭 Aktuell ist keine Frage aktiv.", ephemeral=True
        )
        return

    # Die Liste aller korrekten Antworten aus dem Question-Objekt
    answers = question["answers"]
    text = ", ".join(f"`{a}`" for a in answers)

    logger.info(f"[QuizCommands] /quiz answer by {interaction.user} in {area}")

    # *1. Schritt:* Interaction sofort mit defer() acken,
    # damit Nutzer nicht “The application did not respond” sieht.
    await interaction.response.defer(thinking=True)

    # *2. Schritt:* Öffentliche Nachricht im Quiz-Channel, die die Antwort preisgibt
    channel = interaction.channel
    await channel.send(f"📢 Die richtige Antwort ist: {text}")

    # *3. Schritt:* Jetzt das Embed der Frage dahingehend anpassen, dass
    #             • die Farbe auf Rot wechselt
    #             • ein Feld “Richtige Antwort” mit dem Text (Variable text) eingefügt wird
    #             • der Footer “✋ Frage durch Mod beendet.” gesetzt wird
    #
    # Dazu holen wir uns zunächst die Message anhand von message_id:
    try:
        msg = await channel.fetch_message(question["message_id"])
        embed = msg.embeds[0]

        # Roter Rahmen, um Abschluss zu markieren
        embed.color = discord.Color.red()
        # Footer anpassen, damit klar ist: Mod hat manuell beendet
        embed.set_footer(text="✋ Frage durch Mod beendet.")

        # Feld “Richtige Antwort” einfügen (mit text-Inhalt)
        # (WICHTIG: inline=False, damit es in neuer Zeile erscheint)
        embed.add_field(name="Richtige Antwort", value=text, inline=False)

        # Buttons entfernen (View abwaret)
        await msg.edit(embed=embed, view=None)
    except Exception as e:
        logger.error(
            f"[QuizCommands] Fehler beim Bearbeiten des Frage-Embeds: {e}", exc_info=True)

    # *4. Schritt:* QuizCog internal aufräumen (frage aus current_questions entfernen,
    #             channel_initialized zurücksetzen) – analog zur close_question()
    quiz_cog.current_questions.pop(area, None)
    # Channel darf beim nächsten Fenster erneut Activity-Check überspringen
    cfg = quiz_cog.bot.quiz_data.get(area)
    if cfg:
        cid = cfg["channel_id"]
        quiz_cog.channel_initialized[cid] = False

    # *5. Schritt:* Abschließende Follow-Up-Antwort an den Mod, dass alles getan wurde
    await interaction.followup.send(
        "✅ Die Frage wurde per Mod-Befehl beantwortet und beendet.",
        ephemeral=True
    )


@quiz_group.command(
    name="status",
    description="Status (Restzeit & Nachrichten-Zähler) der aktuellen Frage anzeigen"
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
    question = quiz_cog.current_questions.get(area)
    count = quiz_cog.message_counter.get(interaction.channel.id, 0)
    if question:
        remaining = int(
            (question["end_time"] - datetime.datetime.utcnow()).total_seconds()
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
    logger.info(
        f"[QuizCommands] /quiz disable by {interaction.user} in {area}")
    quiz_cog.bot.quiz_data.pop(area, None)

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
    # Hier reicht ein Rollencheck (Admin/Community Mod); Channel-Check entfällt
    if not is_authorized(interaction.user):
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True
        )
        return

    area = area_name.lower()
    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    logger.info(
        f"[QuizCommands] /quiz enable by {interaction.user} → {area} ({lang})")

    # Frage-Generator neu anlegen (DataLoader/QuestionGenerator)
    q_loader = quiz_cog.bot.data["quiz"]["data_loader"]
    q_generator = QuestionGenerator(
        questions_by_area=quiz_cog.bot.data["quiz"]["questions_by_area"],
        asked_questions=q_loader.load_asked_questions(),
        dynamic_providers={
            "wcr": (
                quiz_cog.bot.quiz_data.get("wcr", {})
                .get("question_generator")
                .dynamic_providers.get("wcr")
                if quiz_cog.bot.quiz_data.get("wcr")
                else None
            )
        }
    )

    quiz_cog.bot.quiz_data[area] = {
        "channel_id": interaction.channel.id,
        "language": lang,
        "question_generator": q_generator
    }
    # Neue Scheduler-Task starten
    quiz_cog.bot.loop.create_task(quiz_cog.quiz_scheduler(area))

    await interaction.response.send_message(
        f"✅ Quiz für **{area}** aktiviert.",
        ephemeral=False
    )


@quiz_group.error
async def on_quiz_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # Fängt grundsätzlich AppCommand-Fehler auf und loggt sie
    logger.exception(f"[QuizCommands] Fehler: {error}")
    # Standard-Antwort an Discord ist ausreichend, daher kein weiteres send_message nötig.


# ─────────── Hinweis ─────────────────────────────────────────────────────────────
# In dieser Datei ist keine eigene setup(...)-Funktion mehr nötig,
# weil die Gruppe `quiz_group` bereits in cogs/quiz/__init__.py registriert wird.
