import os
import discord
from discord import app_commands

from .cog import ChampionCog

# ----------------------------
# 1) Guild‐ID einlesen und Gruppe anlegen
# ----------------------------
SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)

champion_group = app_commands.Group(
    name="champion",
    description="Verwalte Champion-Punkte",
    guild_ids=[MAIN_SERVER_ID]  # Nur in der Haupt-Guild verfügbar
)


# Hilfsfunktion: Prüft, ob der Aufrufer Admin oder Community Mod ist
def _is_authorized(user: discord.Member) -> bool:
    return (
        any(r.name == "Community Mod" for r in user.roles)
        or user.guild_permissions.administrator
    )


# ----------------------------
# 2) /champion give
# ----------------------------
@champion_group.command(
    name="give",
    description="Gibt einem User Punkte (nur Mods)"
)
@app_commands.describe(
    user="Der Nutzer, dem Punkte gegeben werden",
    punkte="Anzahl der Punkte",
    grund="Begründung"
)
async def give(
    interaction: discord.Interaction,
    user: discord.Member,
    punkte: int,
    grund: str
):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    if not _is_authorized(interaction.user):
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung.", ephemeral=True
        )
        return

    new_total = await cog.update_user_score(user.id, punkte, grund)
    await interaction.response.send_message(
        f"✅ {user.mention} hat nun insgesamt {new_total} Punkte."
    )


# ----------------------------
# 3) /champion remove
# ----------------------------
@champion_group.command(
    name="remove",
    description="Entfernt Punkte (nur Mods)"
)
@app_commands.describe(
    user="Der Nutzer, von dem Punkte abgezogen werden",
    punkte="Anzahl der Punkte",
    grund="Begründung"
)
async def remove(
    interaction: discord.Interaction,
    user: discord.Member,
    punkte: int,
    grund: str
):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    if not _is_authorized(interaction.user):
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung.", ephemeral=True
        )
        return

    new_total = await cog.update_user_score(user.id, -punkte, grund)
    await interaction.response.send_message(
        f"⚠️ {user.mention} hat nun insgesamt {new_total} Punkte."
    )


# ----------------------------
# 4) /champion set
# ----------------------------
@champion_group.command(
    name="set",
    description="Setzt die Punktzahl eines Users (nur Mods)"
)
@app_commands.describe(
    user="Der Nutzer, dessen Punktzahl gesetzt wird",
    punkte="Neue Gesamtpunktzahl",
    grund="Begründung"
)
async def set_points(
    interaction: discord.Interaction,
    user: discord.Member,
    punkte: int,
    grund: str
):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    if not _is_authorized(interaction.user):
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung.", ephemeral=True
        )
        return

    old_total = await cog.data.get_total(str(user.id))
    delta = punkte - old_total
    new_total = await cog.update_user_score(user.id, delta, grund)
    await interaction.response.send_message(
        f"🔧 {user.mention} wurde auf {new_total} Punkte gesetzt."
    )


# ----------------------------
# 5) /champion reset
# ----------------------------
@champion_group.command(
    name="reset",
    description="Setzt die Punkte eines Nutzers auf 0 (nur Mods)"
)
@app_commands.describe(
    user="Der Nutzer, dessen Punkte zurückgesetzt werden"
)
async def reset(
    interaction: discord.Interaction,
    user: discord.Member
):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    if not _is_authorized(interaction.user):
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung.", ephemeral=True
        )
        return

    old_total = await cog.data.get_total(str(user.id))
    if old_total <= 0:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} hat aktuell keine Punkte zum Zurücksetzen."
        )
        return

    new_total = await cog.update_user_score(user.id, -old_total, "Reset durch Mod")
    await interaction.response.send_message(
        f"🔄 {user.mention} wurde auf 0 Punkte zurückgesetzt."
    )


# ----------------------------
# 6) /champion info
# ----------------------------
@champion_group.command(
    name="info",
    description="Zeigt Deine Punktzahl"
)
async def info(
    interaction: discord.Interaction
):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    user_id_str = str(interaction.user.id)
    total = await cog.data.get_total(user_id_str)
    await interaction.response.send_message(
        f"🏅 Du hast aktuell {total} Punkte."
    )


# ----------------------------
# 7) /champion history
# ----------------------------
@champion_group.command(
    name="history",
    description="Zeigt die Punkte-Historie eines Spielers"
)
@app_commands.describe(
    user="Der Spieler, dessen Historie angezeigt wird"
)
async def history(
    interaction: discord.Interaction,
    user: discord.Member
):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    user_id_str = str(user.id)
    history_list = await cog.data.get_history(user_id_str, limit=10)

    if not history_list:
        await interaction.response.send_message(
            f"📭 {user.display_name} hat noch keine Historie."
        )
        return

    lines = []
    for entry in history_list:
        date_str = entry["date"][:10]  # ISO: YYYY-MM-DD
        delta = entry["delta"]
        sign = "+" if delta > 0 else ""
        lines.append(f"📅 {date_str}: {sign}{delta} – {entry['reason']}")

    text = "\n".join(lines)
    await interaction.response.send_message(
        f"📜 Punkteverlauf von {user.display_name}:\n{text}"
    )


# ----------------------------
# 8) /champion leaderboard
# ----------------------------
@champion_group.command(
    name="leaderboard",
    description="Zeigt die Top 10 (Punkte-Ranking)"
)
@app_commands.describe(
    page="Welche Seite des Leaderboards (10 Einträge pro Seite)"
)
async def leaderboard(
    interaction: discord.Interaction,
    page: int = 1
):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    if page < 1:
        page = 1

    limit = 10
    offset = (page - 1) * limit
    top = await cog.data.get_leaderboard(limit=limit, offset=offset)

    if not top:
        await interaction.response.send_message(
            "🤷 Keine Einträge im Leaderboard."
        )
        return

    entries = []
    for idx, (user_id_str, total) in enumerate(top, start=offset + 1):
        member = interaction.guild.get_member(int(user_id_str))
        name = member.display_name if member else f"Unbekannt ({user_id_str})"
        entries.append(f"{idx}. {name} – {total} Punkte")

    text = "\n".join(entries)
    await interaction.response.send_message(
        f"🏆 **Top {offset+1}–{offset+len(top)}**:\n{text}"
    )
