# pragma: no cover

import json
import datetime

from lotus_bot.log_setup import get_logger
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands

from .cog import QuizCog
from .scheduler import QuizScheduler
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


async def area_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete available quiz areas based on ``current`` text."""
    bot = interaction.client
    current_lower = current.lower()
    matches = [name for name in bot.quiz_data.keys() if current_lower in name.lower()]
    matches.sort()
    return [app_commands.Choice(name=m, value=m) for m in matches[:25]]


@quiz_group.command(
    name="time", description="Zeitfenster (in Minuten) für dieses Quiz setzen"
)
@app_commands.describe(minutes="Zeitfenster in Minuten (1–120)")
@app_commands.default_permissions(manage_guild=True)
async def time(
    interaction: discord.Interaction, minutes: app_commands.Range[int, 1, 120]
):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    interaction.client.quiz_data[area].time_window = datetime.timedelta(minutes=minutes)
    save_area_config(interaction.client)

    await interaction.response.send_message(
        f"⏱️ Zeitfenster auf **{minutes} Minuten** gesetzt.", ephemeral=True
    )


@quiz_group.command(
    name="language", description="Sprache (de / en) für dieses Quiz setzen"
)
@app_commands.describe(lang="de oder en")
@app_commands.default_permissions(manage_guild=True)
async def language(interaction: discord.Interaction, lang: Literal["de", "en"]):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    cfg = interaction.client.quiz_data[area]
    cfg.language = lang

    qg: QuestionGenerator | None = cfg.question_generator
    if qg:
        provider = qg.get_dynamic_provider(area)
        if provider:
            provider.language = lang

    save_area_config(interaction.client)

    await interaction.response.send_message(
        f"🌐 Sprache für **{area}** auf **{lang}** gesetzt.", ephemeral=True
    )


@quiz_group.command(
    name="threshold", description="Aktivitätsschwelle für automatische Fragen setzen"
)
@app_commands.describe(value="Nachrichten bis zur nächsten Frage (1–50)")
@app_commands.default_permissions(manage_guild=True)
async def threshold(
    interaction: discord.Interaction, value: app_commands.Range[int, 1, 50]
):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    interaction.client.quiz_data[area].activity_threshold = value
    save_area_config(interaction.client)

    await interaction.response.send_message(
        f"📈 Aktivitätsschwelle auf **{value}** gesetzt.", ephemeral=True
    )


@quiz_group.command(name="enable", description="Quiz in diesem Channel aktivieren")
@app_commands.describe(
    area_name="Name der Area (z. B. wcr, d4, ptcgp)", lang="de oder en"
)
@app_commands.autocomplete(area_name=area_autocomplete)
@app_commands.default_permissions(manage_guild=True)
async def enable(
    interaction: discord.Interaction, area_name: str, lang: Literal["de", "en"] = "de"
):
    area = area_name.lower()

    if area not in interaction.client.quiz_data:
        await interaction.response.send_message(
            "❌ Diese Area ist nicht bekannt oder nicht geladen.", ephemeral=True
        )
        return

    cfg = interaction.client.quiz_data[area]
    cfg.channel_id = interaction.channel.id
    cfg.language = lang
    cfg.active = True

    qg: QuestionGenerator | None = cfg.question_generator
    if qg:
        provider = qg.get_dynamic_provider(area)
        if provider and getattr(provider, "language", None) != lang:
            provider.language = lang

    quiz_cog: QuizCog | None = interaction.client.get_cog("QuizCog")
    if quiz_cog and area not in quiz_cog.schedulers:
        scheduler = QuizScheduler(
            bot=interaction.client,
            area=area,
            prepare_question_callback=quiz_cog.manager.prepare_question,
            close_question_callback=quiz_cog.closer.close_question,
        )
        scheduler.task = quiz_cog._track_task(scheduler.run())
        quiz_cog.schedulers[area] = scheduler

    save_area_config(interaction.client)

    await interaction.response.send_message(
        f"✅ Quiz für **{area}** aktiviert.", ephemeral=False
    )


@quiz_group.command(name="disable", description="Quiz in diesem Channel deaktivieren")
@app_commands.default_permissions(manage_guild=True)
async def disable(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    cfg = interaction.client.quiz_data[area]
    cfg.active = False

    quiz_cog: QuizCog | None = interaction.client.get_cog("QuizCog")
    if quiz_cog:
        scheduler = quiz_cog.schedulers.pop(area, None)
        if scheduler:
            scheduler.task.cancel()

    save_area_config(interaction.client)

    await interaction.response.send_message(
        f"🚫 Quiz für **{area}** deaktiviert.", ephemeral=False
    )


@quiz_group.command(name="ask", description="Sofort eine Quizfrage posten")
@app_commands.default_permissions(manage_guild=True)
async def ask(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    time_window = interaction.client.quiz_data[area].time_window
    end_time = datetime.datetime.utcnow() + time_window
    await quiz_cog.manager.ask_question(area, end_time)

    await interaction.response.send_message(
        "✅ Die Frage wurde erstellt.", ephemeral=False
    )


@quiz_group.command(
    name="duel", description="Starte ein Quiz-Duell (Best-of-X oder dynamic)"
)
@app_commands.describe(
    punkte="Gesetzte Punkte",
    modus="Modus des Duells (box oder dynamic)",
    best_of="Rundenanzahl für box-Modus",
    timeout="Antwortzeit in Sekunden (10–120)",
)
async def duel(
    interaction: discord.Interaction,
    punkte: app_commands.Range[int, 1, 10000],
    modus: Literal["box", "dynamic"] = "box",
    best_of: app_commands.Range[int, 3, 15] | None = None,
    timeout: app_commands.Range[int, 10, 120] = 30,
):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    qg: QuestionGenerator = interaction.client.quiz_data[area].question_generator
    if modus == "dynamic" and area not in qg.dynamic_providers:
        await interaction.response.send_message(
            "❌ Dieser Modus ist hier nicht verfügbar.", ephemeral=True
        )
        return

    champion_cog = interaction.client.get_cog("ChampionCog")
    if champion_cog is None:
        await interaction.response.send_message(
            "❌ Champion-System nicht verfügbar.", ephemeral=True
        )
        return
    quiz_cog: QuizCog | None = interaction.client.get_cog("QuizCog")
    if quiz_cog and interaction.user.id in quiz_cog.active_duels:
        await interaction.response.send_message(
            "❌ Du bist bereits in einem Duell.", ephemeral=True
        )
        return

    if modus == "box" and best_of is None:
        await interaction.response.send_message(
            "❌ Bitte gib die Rundenzahl an.", ephemeral=True
        )
        return
    if modus == "box" and best_of is not None and best_of % 2 == 0:
        await interaction.response.send_message(
            "❌ Bitte wähle eine ungerade Rundenzahl.", ephemeral=True
        )
        return
    total = await champion_cog.data.get_total(str(interaction.user.id))
    if total < punkte:
        await interaction.response.send_message(
            "❌ Du hast nicht genügend Punkte.", ephemeral=True
        )
        return

    cfg = DuelConfig(
        area=area, points=punkte, mode=modus, timeout=timeout, best_of=best_of
    )
    view = DuelInviteView(interaction.user, cfg, interaction.client.get_cog("QuizCog"))
    embed = discord.Embed(
        title="Quiz-Duell",
        description=f"{interaction.user.mention} fordert einen Gegner heraus!",
        color=discord.Color.orange(),
    )
    embed.add_field(name="Einsatz", value=f"{punkte} Punkte")
    if modus == "box":
        embed.add_field(name="Modus", value=f"Best of {best_of}")
    else:
        embed.add_field(name="Modus", value="dynamic")
    embed.add_field(name="Zeitlimit", value=f"{timeout}s")
    msg = await interaction.channel.send(embed=embed, view=view)
    view.message = msg
    await interaction.response.send_message("Duelleinladung erstellt.", ephemeral=True)


@quiz_group.command(
    name="answer", description="Zeige die richtige Antwort und schließe die Frage"
)
@app_commands.default_permissions(manage_guild=True)
async def answer(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    question_data = quiz_cog.current_questions.get(area)
    if not question_data:
        await interaction.response.send_message(
            "📭 Aktuell ist keine Frage aktiv.", ephemeral=True
        )
        return

    try:
        channel = interaction.client.get_channel(
            quiz_cog.bot.quiz_data[area].channel_id
        )
        msg = await channel.fetch_message(question_data.message_id)
        embed = msg.embeds[0]
        embed.color = discord.Color.red()

        answers = question_data.answers
        answer_text = ", ".join(str(a) for a in answers)
        embed.add_field(name="Richtige Antwort", value=answer_text, inline=False)
        if question_data.source_url:
            label = question_data.source_label or "Quelle"
            embed.add_field(
                name="Quelle",
                value=f"[{label}]({question_data.source_url})",
                inline=False,
            )
        embed.set_footer(text="✋ Frage durch Mod beendet.")
        await msg.edit(embed=embed, view=None)
    except Exception as e:
        logger.warning(f"[QuizCog] Error while manually ending question: {e}")

    quiz_cog.current_questions.pop(area, None)
    await interaction.response.send_message(
        "✅ Die Frage wurde beendet.", ephemeral=True
    )


@quiz_group.command(
    name="status",
    description="Status (Restzeit & Nachrichten‐Zähler) der aktuellen Frage anzeigen",
)
@app_commands.default_permissions(manage_guild=True)
async def status(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ In diesem Channel ist kein Quiz konfiguriert.", ephemeral=True
        )
        return

    quiz_cog: QuizCog = interaction.client.get_cog("QuizCog")
    question_data = quiz_cog.current_questions.get(area)
    count = quiz_cog.tracker.get(interaction.channel.id)
    if question_data:
        remaining = int(
            (question_data.end_time - datetime.datetime.utcnow()).total_seconds()
        )
        await interaction.response.send_message(
            f"📊 Aktive Frage: noch **{remaining}s**. Nachrichten seit Start: **{count}**.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "📊 Aktuell ist keine Frage aktiv.", ephemeral=True
        )


@quiz_group.command(name="stats", description="Zeigt Anzahl richtiger Antworten")
@app_commands.describe(user="Optionaler Nutzer, dessen Statistik gezeigt wird")
async def stats(interaction: discord.Interaction, user: discord.Member | None = None):
    quiz_cog: QuizCog | None = interaction.client.get_cog("QuizCog")
    if quiz_cog is None:
        await interaction.response.send_message(
            "❌ Quiz-System nicht verfügbar.", ephemeral=True
        )
        return

    target = user or interaction.user
    count = quiz_cog.stats.get(target.id)

    if target.id == interaction.user.id and user is None:
        msg = f"📈 Du hast bisher {count} richtige Antworten gegeben."
    else:
        msg = f"📈 {target.display_name} hat bisher {count} richtige Antworten gegeben."
    await interaction.response.send_message(msg, ephemeral=True)


@quiz_group.command(name="duelstats", description="Zeigt deine Duell-Bilanz")
@app_commands.describe(user="Optionaler Nutzer, dessen Statistik gezeigt wird")
async def duelstats(
    interaction: discord.Interaction, user: discord.Member | None = None
):
    champion_cog = interaction.client.get_cog("ChampionCog")
    if champion_cog is None:
        await interaction.response.send_message(
            "❌ Champion-System nicht verfügbar.", ephemeral=True
        )
        return

    target = user or interaction.user
    stats = await champion_cog.data.get_duel_stats(str(target.id))
    wins = stats.get("win", 0)
    losses = stats.get("loss", 0)
    ties = stats.get("tie", 0)

    if target.id == interaction.user.id and user is None:
        msg = f"⚔️ Deine Bilanz: {wins} Siege, {losses} Niederlagen, {ties} Unentschieden."
    else:
        msg = (
            f"⚔️ Bilanz von {target.display_name}: "
            f"{wins} Siege, {losses} Niederlagen, {ties} Unentschieden."
        )
    await interaction.response.send_message(msg, ephemeral=True)


@quiz_group.command(
    name="duelleaderboard",
    description="Rangliste der meisten Duell-Siege",
)
async def duelleaderboard(interaction: discord.Interaction):
    champion_cog = interaction.client.get_cog("ChampionCog")
    if champion_cog is None:
        await interaction.response.send_message(
            "❌ Champion-System nicht verfügbar.", ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)
    top = await champion_cog.data.get_duel_leaderboard(limit=10)
    if not top:
        await interaction.followup.send("🤷 Keine Duelle aufgezeichnet.")
        return

    lines = [
        "```text",
        "Rang Name                 Siege",
        "---- -------------------- -----",
    ]
    rank = 1
    for user_id, wins, _losses, _ties in top:
        member = interaction.guild.get_member(int(user_id))
        if member is None:
            try:
                member = await interaction.guild.fetch_member(int(user_id))
            except discord.NotFound:
                member = None
            except discord.HTTPException:
                member = None
        name = member.display_name if member else f"Unbekannt ({user_id})"
        lines.append(f"{rank:>4} {name:<20} {wins:>5}")
        rank += 1
    lines.append("```")
    await interaction.followup.send("\n".join(lines))


@quiz_group.command(
    name="reset", description="Setzt die Frage-Historie für diesen Channel zurück"
)
@app_commands.default_permissions(manage_guild=True)
async def reset(interaction: discord.Interaction):
    area = get_area_by_channel(interaction.client, interaction.channel.id)
    if not area:
        await interaction.response.send_message(
            "❌ Kein Quiz in diesem Channel.", ephemeral=True
        )
        return

    state = interaction.client.quiz_data[area].question_state
    await state.reset_asked_questions(area)
    await interaction.response.send_message(
        f"♻️ Frageverlauf für **{area}** wurde zurückgesetzt.", ephemeral=True
    )


@quiz_group.error
async def on_quiz_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    logger.exception(f"[QuizCommands] Error: {error}")
