import discord
from discord import app_commands

from log_setup import get_logger
from permissions import moderator_only
from .cog import ChampionCog

logger = get_logger(__name__)

champion_group = app_commands.Group(
    name="champion", description="Verwalte Champion-Punkte"
)


@champion_group.command(name="give", description="Gibt einem User Punkte (nur Mods)")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(
    user="Der Nutzer, dem Punkte gegeben werden",
    punkte="Anzahl der Punkte",
    grund="Begründung",
)
async def give(
    interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str
):
    """Verleiht einem Nutzer Punkte."""

    logger.info(
        f"/champion give by {interaction.user} -> {user} ({punkte} Punkte, Grund: {grund})"
    )

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    new_total = await cog.update_user_score(user.id, punkte, grund)
    await interaction.response.send_message(
        f"✅ {user.mention} hat nun insgesamt {new_total} Punkte.",
        ephemeral=True,
    )


@champion_group.command(name="remove", description="Entfernt Punkte (nur Mods)")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(
    user="Der Nutzer, von dem Punkte abgezogen werden",
    punkte="Anzahl der Punkte",
    grund="Begründung",
)
async def remove(
    interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str
):
    """Zieht einem Nutzer Punkte ab."""

    logger.info(
        f"/champion remove by {interaction.user} -> {user} ({punkte} Punkte, Grund: {grund})"
    )

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    new_total = await cog.update_user_score(user.id, -punkte, grund)
    await interaction.response.send_message(
        f"⚠️ {user.mention} hat nun insgesamt {new_total} Punkte.",
        ephemeral=True,
    )


@champion_group.command(
    name="set", description="Setzt die Punktzahl eines Users (nur Mods)"
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(
    user="Der Nutzer, dessen Punktzahl gesetzt wird",
    punkte="Neue Gesamtpunktzahl",
    grund="Begründung",
)
async def set_points(
    interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str
):
    """Setzt die Punktzahl eines Nutzers direkt."""

    logger.info(
        f"/champion set by {interaction.user} -> {user} ({punkte} Punkte, Grund: {grund})"
    )

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    old_total = await cog.data.get_total(str(user.id))
    delta = punkte - old_total
    new_total = await cog.update_user_score(user.id, delta, grund)
    await interaction.response.send_message(
        f"🔧 {user.mention} wurde auf {new_total} Punkte gesetzt.",
        ephemeral=True,
    )


@champion_group.command(
    name="reset", description="Setzt die Punkte eines Nutzers auf 0 (nur Mods)"
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(user="Der Nutzer, dessen Punkte zurückgesetzt werden")
async def reset(interaction: discord.Interaction, user: discord.Member):
    """Setzt die Punkte eines Nutzers auf null."""

    logger.info(f"/champion reset by {interaction.user} for {user}")

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    old_total = await cog.data.get_total(str(user.id))
    if old_total <= 0:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} hat aktuell keine Punkte zum Zurücksetzen.",
            ephemeral=True,
        )
        return
    await cog.update_user_score(user.id, -old_total, "Reset durch Mod")
    await interaction.response.send_message(
        f"🔄 {user.mention} wurde auf 0 Punkte zurückgesetzt.",
        ephemeral=True,
    )


@champion_group.command(name="score", description="Zeigt die Punktzahl eines Nutzers")
@app_commands.describe(user="Der Nutzer, dessen Punkte angezeigt werden")
async def score(interaction: discord.Interaction, user: discord.Member | None = None):
    """Zeigt deinen oder einen fremden Punktestand an."""
    logger.info(
        f"/champion score by {interaction.user} target={user or interaction.user}"
    )
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    target = user or interaction.user
    total = await cog.data.get_total(str(target.id))
    if user is None or target.id == interaction.user.id:
        await interaction.response.send_message(
            f"🏅 Du hast aktuell {total} Punkte.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"🏅 {target.display_name} hat aktuell {total} Punkte.",
            ephemeral=True,
        )


@champion_group.command(
    name="myhistory", description="Zeigt Deinen eigenen Punkteverlauf"
)
async def myhistory(interaction: discord.Interaction):
    """Zeigt deinen eigenen Punkteverlauf."""
    logger.info(f"/champion myhistory by {interaction.user}")
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    user_id_str = str(interaction.user.id)
    history_list = await cog.data.get_history(user_id_str, limit=10)
    total = await cog.data.get_total(user_id_str)

    if not history_list:
        await interaction.response.send_message(
            "📭 Du hast noch keine Historie.", ephemeral=True
        )
        return

    lines = []
    for entry in history_list:
        date_str = entry["date"][:10]
        delta = entry["delta"]
        sign = "+" if delta > 0 else ""
        lines.append(f"📅 {date_str}: {sign}{delta} – {entry['reason']}")

    text = "\n".join(lines)
    text += f"\nAktueller Stand: {total} Punkte."
    await interaction.response.send_message(
        f"📜 Dein Punkteverlauf:\n{text}",
        ephemeral=True,
    )


@champion_group.command(
    name="history", description="Zeigt die Punkte-Historie eines Spielers"
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(user="Der Spieler, dessen Historie angezeigt wird")
async def history(interaction: discord.Interaction, user: discord.Member):
    """Zeigt den Punkteverlauf eines anderen Nutzers."""
    logger.info(f"/champion history by {interaction.user} target={user}")

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    user_id_str = str(user.id)
    history_list = await cog.data.get_history(user_id_str, limit=10)
    total = await cog.data.get_total(user_id_str)

    if not history_list:
        await interaction.response.send_message(
            f"📭 {user.display_name} hat noch keine Historie.",
            ephemeral=True,
        )
        return

    lines = []
    for entry in history_list:
        date_str = entry["date"][:10]
        delta = entry["delta"]
        sign = "+" if delta > 0 else ""
        lines.append(f"📅 {date_str}: {sign}{delta} – {entry['reason']}")

    text = "\n".join(lines)
    text += f"\nAktueller Stand: {total} Punkte."
    await interaction.response.send_message(
        f"📜 Punkteverlauf von {user.display_name}:\n{text}",
        ephemeral=True,
    )


@champion_group.command(
    name="leaderboard",
    description="Zeigt die Top 30 gruppiert nach Champion-Rolle als Tabelle",
)
async def leaderboard(interaction: discord.Interaction):
    """Zeigt die besten Punktestände nach Rolle gruppiert."""
    logger.info(f"/champion leaderboard requested by {interaction.user}")
    await interaction.response.defer(thinking=True)

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    top = await cog.data.get_leaderboard(limit=30)

    if not top:
        await interaction.followup.send("🤷 Keine Einträge im Leaderboard.")
        return

    # Emojis laden. ``emoji_data`` ist ein Dict {name: syntax}
    emoji_data = interaction.client.data.get("emojis", {})
    icon_map = {
        "Ultimate Champion": emoji_data.get("challenger_5", ""),
        "Epic Champion": emoji_data.get("challenger_4", ""),
        "Renowned Champion": emoji_data.get("challenger_3", ""),
        "Seasoned Champion": emoji_data.get("challenger_2", ""),
        "Emerging Champion": emoji_data.get("challenger_1", ""),
        "Champion": emoji_data.get("challenger_0", ""),
    }

    grouped: dict[str, list[tuple[int, str, int]]] = {}
    rank = 1

    for user_id_str, total in top:
        member = interaction.guild.get_member(int(user_id_str))
        if member is None:
            try:
                member = await interaction.guild.fetch_member(int(user_id_str))
            except discord.NotFound:
                member = None
            except discord.HTTPException as e:
                logger.warning(
                    f"[ChampionCog] Fehler beim Laden von Member {user_id_str}: {e}",
                    exc_info=True,
                )
                member = None

        name = member.display_name if member else f"Unbekannt ({user_id_str})"
        role_obj = cog.get_current_role(total)
        role_name = role_obj.name if role_obj else "Champion"
        grouped.setdefault(role_name, []).append((rank, name, total))
        rank += 1

    role_order = [r.name for r in cog.roles] + ["Champion"]

    output = []
    for role_name in role_order:
        if role_name not in grouped:
            continue

        icon = icon_map.get(role_name, "")
        output.append(f"{icon} **{role_name}**")

        lines = [
            "```text",
            "Rang Name                 Punkte",
            "---- -------------------- ------",
        ]
        for rank, name, score in grouped[role_name]:
            lines.append(f"{rank:>4} {name:<20} {score:>6}")
        lines.append("```")
        output.append("\n".join(lines))

    await interaction.followup.send("\n".join(output))


@champion_group.command(
    name="roles", description="Listet alle Champion-Rollen und ihre Schwellen"
)
async def roles(interaction: discord.Interaction):
    """Listet alle Champion-Rollen mit ihren Schwellen."""
    logger.info(f"/champion roles requested by {interaction.user}")
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    lines = []
    for role in cog.roles:
        lines.append(f"{role.name}: ab {role.threshold} Punkte")
    lines.append(
        "Champion: unter {0} Punkte".format(cog.roles[-1].threshold if cog.roles else 0)
    )
    await interaction.response.send_message("\n".join(lines))


@champion_group.command(
    name="rank", description="Zeigt den Rang eines Nutzers im Leaderboard"
)
@app_commands.describe(user="Der Nutzer, dessen Rang angezeigt wird")
async def rank(interaction: discord.Interaction, user: discord.Member | None = None):
    """Zeigt den Rang eines Nutzers in der Bestenliste."""
    logger.info(
        f"/champion rank by {interaction.user} target={user or interaction.user}"
    )
    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    target = user or interaction.user
    result = await cog.data.get_rank(str(target.id))

    if result is None:
        if target.id == interaction.user.id:
            await interaction.response.send_message("🤷 Du hast noch keine Punkte.")
        else:
            await interaction.response.send_message(
                f"🤷 {target.display_name} hat noch keine Punkte."
            )
        return

    rank_num, total = result
    if target.id == interaction.user.id and user is None:
        await interaction.response.send_message(
            f"🏆 Du bist Rang {rank_num} mit {total} Punkten."
        )
    else:
        await interaction.response.send_message(
            f"🏆 {target.display_name} ist Rang {rank_num} mit {total} Punkten."
        )


@champion_group.command(
    name="clean", description="Entfernt Einträge ehemaliger Mitglieder (nur Mods)"
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
async def clean(interaction: discord.Interaction):
    """Entfernt ehemalige Mitglieder aus der Datenbank."""
    logger.info(f"/champion clean requested by {interaction.user}")
    await interaction.response.defer(thinking=True)

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    all_ids = await cog.data.get_all_user_ids()

    removed = 0
    for user_id_str in all_ids:
        member = interaction.guild.get_member(int(user_id_str))
        if member is None:
            try:
                await interaction.guild.fetch_member(int(user_id_str))
            except discord.NotFound:
                await cog.data.delete_user(user_id_str)
                removed += 1
            except discord.HTTPException as e:
                logger.warning(
                    f"[ChampionCog] Fehler beim Prüfen von Member {user_id_str}: {e}",
                    exc_info=True,
                )

    await interaction.followup.send(
        f"🧹 Entfernte {removed} Einträge aus der Datenbank.",
        ephemeral=True,
    )


@app_commands.command(
    name="syncroles",
    description="Synchronisiert Champion-Rollen für alle gespeicherten Nutzer (nur Mods)",
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
async def syncroles(interaction: discord.Interaction):
    """Synchronisiert die Champion-Rollen aller gespeicherten Nutzer."""
    logger.info(f"/syncroles requested by {interaction.user}")
    await interaction.response.defer(thinking=True)

    cog: ChampionCog = interaction.client.get_cog("ChampionCog")
    user_ids = await cog.data.get_all_user_ids()
    processed = 0
    for user_id_str in user_ids:
        total = await cog.data.get_total(user_id_str)
        await cog._apply_champion_role(user_id_str, total)
        processed += 1

    await interaction.followup.send(
        f"🔄 Synchronisierte Rollen für {processed} Nutzer.",
        ephemeral=True,
    )
