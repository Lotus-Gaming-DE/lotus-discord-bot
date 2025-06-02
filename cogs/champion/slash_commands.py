import os
import discord
from discord import app_commands

from .cog import ChampionCog

SERVER_ID = os.getenv("server_id")
if SERVER_ID is None:
    raise ValueError("Environment variable 'server_id' is not set.")
MAIN_SERVER_ID = int(SERVER_ID)

champion_group = app_commands.Group(
    name="champion",
    description="Verwalte Champion-Punkte",
    guild_ids=[MAIN_SERVER_ID]
)


@champion_group.command(name="give", description="Gibt einem User Punkte (nur Mods)")
@app_commands.describe(user="Der Nutzer, dem Punkte gegeben werden", punkte="Anzahl der Punkte", grund="Begründung")
@app_commands.default_permissions(manage_guild=True)
async def give(interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    new_total = await cog.update_user_score(user.id, punkte, grund)
    await interaction.response.send_message(f"✅ {user.mention} hat nun insgesamt {new_total} Punkte.")


@champion_group.command(name="remove", description="Entfernt Punkte (nur Mods)")
@app_commands.describe(user="Der Nutzer, von dem Punkte abgezogen werden", punkte="Anzahl der Punkte", grund="Begründung")
@app_commands.default_permissions(manage_guild=True)
async def remove(interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    new_total = await cog.update_user_score(user.id, -punkte, grund)
    await interaction.response.send_message(f"⚠️ {user.mention} hat nun insgesamt {new_total} Punkte.")


@champion_group.command(name="set", description="Setzt die Punktzahl eines Users (nur Mods)")
@app_commands.describe(user="Der Nutzer, dessen Punktzahl gesetzt wird", punkte="Neue Gesamtpunktzahl", grund="Begründung")
@app_commands.default_permissions(manage_guild=True)
async def set_points(interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    old_total = await cog.data.get_total(str(user.id))
    delta = punkte - old_total
    new_total = await cog.update_user_score(user.id, delta, grund)
    await interaction.response.send_message(f"🔧 {user.mention} wurde auf {new_total} Punkte gesetzt.")


@champion_group.command(name="reset", description="Setzt die Punkte eines Nutzers auf 0 (nur Mods)")
@app_commands.describe(user="Der Nutzer, dessen Punkte zurückgesetzt werden")
@app_commands.default_permissions(manage_guild=True)
async def reset(interaction: discord.Interaction, user: discord.Member):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    old_total = await cog.data.get_total(str(user.id))
    if old_total <= 0:
        await interaction.response.send_message(f"ℹ️ {user.mention} hat aktuell keine Punkte zum Zurücksetzen.")
        return
    new_total = await cog.update_user_score(user.id, -old_total, "Reset durch Mod")
    await interaction.response.send_message(f"🔄 {user.mention} wurde auf 0 Punkte zurückgesetzt.")


@champion_group.command(name="info", description="Zeigt Deine Punktzahl")
async def info(interaction: discord.Interaction):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    user_id_str = str(interaction.user.id)
    total = await cog.data.get_total(user_id_str)
    await interaction.response.send_message(f"🏅 Du hast aktuell {total} Punkte.")


@champion_group.command(name="history", description="Zeigt die Punkte-Historie eines Spielers")
@app_commands.describe(user="Der Spieler, dessen Historie angezeigt wird")
@app_commands.default_permissions(manage_guild=True)
async def history(interaction: discord.Interaction, user: discord.Member):
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    user_id_str = str(user.id)
    history_list = await cog.data.get_history(user_id_str, limit=10)

    if not history_list:
        await interaction.response.send_message(f"📭 {user.display_name} hat noch keine Historie.")
        return

    lines = []
    for entry in history_list:
        date_str = entry["date"][:10]
        delta = entry["delta"]
        sign = "+" if delta > 0 else ""
        lines.append(f"📅 {date_str}: {sign}{delta} – {entry['reason']}")

    text = "\n".join(lines)
    await interaction.response.send_message(f"📜 Punkteverlauf von {user.display_name}:\n{text}")


@champion_group.command(name="leaderboard", description="Zeigt die Top 30 gruppiert nach Champion-Rolle")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    top = await cog.data.get_leaderboard(limit=30)

    if not top:
        await interaction.followup.send("🤷 Keine Einträge im Leaderboard.")
        return

    # Emojis aus Bot-Daten laden
    emoji_data = interaction.client.data.get("emojis", {})

    icon_map = {
        "Ultimate Champion": emoji_data.get("challenger_5", {}).get("syntax", ""),
        "Epic Champion": emoji_data.get("challenger_4", {}).get("syntax", ""),
        "Renowned Champion": emoji_data.get("challenger_3", {}).get("syntax", ""),
        "Seasoned Champion": emoji_data.get("challenger_2", {}).get("syntax", ""),
        "Emerging Champion": emoji_data.get("challenger_1", {}).get("syntax", ""),
        "Keine Rolle": emoji_data.get("challenger_0", {}).get("syntax", "")
    }

    grouped: dict[str, list[str]] = {}
    rank = 1

    for user_id_str, total in top:
        # Erst aus dem Cache holen
        member = interaction.guild.get_member(int(user_id_str))
        if not member:
            try:
                member = await interaction.guild.fetch_member(int(user_id_str))
            except discord.NotFound:
                member = None

        name = member.display_name if member else f"Unbekannt ({user_id_str})"
        role = cog.get_current_role(total) or "Keine Rolle"
        grouped.setdefault(role, []).append(
            f"  {rank}. {name} – {total} Punkte")
        rank += 1

    role_order = [r[0] for r in cog.roles] + ["Keine Rolle"]

    output = []
    for role_name in role_order:
        if role_name not in grouped:
            continue
        icon = icon_map.get(role_name, "")
        output.append(f"{icon} **{role_name}**")
        output.extend(grouped[role_name])
        output.append("")

    text = "\n".join(output).strip()
    await interaction.followup.send(text)
