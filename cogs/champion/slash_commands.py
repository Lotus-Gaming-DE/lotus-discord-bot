# cogs/champion/slash_commands.py

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger(__name__)  # cogs.champion.slash_commands

# 1) Erstelle die Command-Gruppe /champion
SERVER_ID = int(os.getenv("server_id"))
champion_group = app_commands.Group(
    name="champion",
    description="Verwalte Champion-Punkte",
    # <- Dadurch weiß Discord sofort, dass alle Subcommands hierhin gehören
    guild_ids=[SERVER_ID]
)


class ChampionCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cog = bot.get_cog("ChampionCog")

    def is_authorized(self, user: discord.Member) -> bool:
        return (
            any(role.name == "Community Mod" for role in user.roles)
            or user.guild_permissions.administrator
        )

    @champion_group.command(
        name="give",
        description="Gibt einem User Punkte (nur Mods)"
    )
    @app_commands.describe(
        user="Der Nutzer, dem Punkte gegeben werden",
        punkte="Anzahl der Punkte",
        grund="Begründung"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        punkte: int,
        grund: str
    ):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung.", ephemeral=True
            )
            return

        new_total = await self.cog.update_user_score(user.id, punkte, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} vergibt +{punkte} an {user} ({grund})"
        )
        await interaction.response.send_message(
            f"✅ {user.mention} hat nun insgesamt {new_total} Punkte."
        )

    @champion_group.command(
        name="remove",
        description="Entfernt Punkte (nur Mods)"
    )
    @app_commands.describe(
        user="Der Nutzer, von dem Punkte abgezogen werden",
        punkte="Anzahl der Punkte",
        grund="Begründung"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        punkte: int,
        grund: str
    ):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung.", ephemeral=True
            )
            return

        new_total = await self.cog.update_user_score(user.id, -punkte, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} zieht {punkte} von {user} ab ({grund})"
        )
        await interaction.response.send_message(
            f"⚠️ {user.mention} hat nun insgesamt {new_total} Punkte."
        )

    @champion_group.command(
        name="set",
        description="Setzt die Punktzahl eines Users (nur Mods)"
    )
    @app_commands.describe(
        user="Der Nutzer, dessen Punktzahl gesetzt wird",
        punkte="Neue Gesamtpunktzahl",
        grund="Begründung"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        punkte: int,
        grund: str
    ):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung.", ephemeral=True
            )
            return

        old_total = await self.cog.data.get_total(str(user.id))
        delta = punkte - old_total
        new_total = await self.cog.update_user_score(user.id, delta, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} setzt {user} von {old_total} auf {punkte} Punkte ({grund})"
        )
        await interaction.response.send_message(
            f"🔧 {user.mention} wurde auf {new_total} Punkte gesetzt."
        )

    @champion_group.command(
        name="reset",
        description="Setzt die Punkte eines Nutzers auf 0 (nur Mods)"
    )
    @app_commands.describe(user="Der Nutzer, dessen Punkte zurückgesetzt werden")
    @app_commands.default_permissions(manage_guild=True)
    async def reset(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung.", ephemeral=True
            )
            return

        old_total = await self.cog.data.get_total(str(user.id))
        if old_total <= 0:
            await interaction.response.send_message(
                f"ℹ️ {user.mention} hat aktuell keine Punkte zum Zurücksetzen."
            )
            return

        new_total = await self.cog.update_user_score(user.id, -old_total, "Reset durch Mod")
        logger.info(
            f"[ChampionCommands] {interaction.user} setzt {user} zurück (von {old_total} auf 0)."
        )
        await interaction.response.send_message(
            f"🔄 {user.mention} wurde auf 0 Punkte zurückgesetzt."
        )

    @champion_group.command(
        name="info",
        description="Zeigt Deine Punktzahl"
    )
    @app_commands.default_permissions(send_messages=True)
    async def info(self, interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)
        total = await self.cog.data.get_total(user_id_str)
        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion info auf."
        )
        await interaction.response.send_message(
            f"🏅 Du hast aktuell {total} Punkte."
        )

    @champion_group.command(
        name="history",
        description="Zeigt die Punkte-Historie eines Spielers"
    )
    @app_commands.describe(user="Der Spieler, dessen Historie angezeigt wird")
    @app_commands.default_permissions(send_messages=True)
    async def history(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        user_id_str = str(user.id)
        history = await self.cog.data.get_history(user_id_str, limit=10)
        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion history für {user} auf."
        )

        if not history:
            await interaction.response.send_message(
                f"📭 {user.display_name} hat noch keine Historie."
            )
            return

        lines = []
        for entry in history:
            date_str = entry["date"][:10]  # ISO: YYYY-MM-DD
            delta = entry["delta"]
            sign = "+" if delta > 0 else ""
            lines.append(f"📅 {date_str}: {sign}{delta} – {entry['reason']}")

        text = "\n".join(lines)
        await interaction.response.send_message(
            f"📜 Punkteverlauf von {user.display_name}:\n{text}"
        )

    @champion_group.command(
        name="leaderboard",
        description="Zeigt die Top 10 (Punkte-Ranking)"
    )
    @app_commands.describe(page="Welche Seite des Leaderboards (10 Einträge pro Seite)")
    @app_commands.default_permissions(send_messages=True)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        page: Optional[int] = 1
    ):
        if page < 1:
            page = 1
        limit = 10
        offset = (page - 1) * limit
        top = await self.cog.data.get_leaderboard(limit=limit, offset=offset)

        if not top:
            await interaction.response.send_message("🤷 Keine Einträge im Leaderboard.")
            return

        entries = []
        for idx, (user_id_str, total) in enumerate(top, start=offset + 1):
            member = interaction.guild.get_member(int(user_id_str))
            name = member.display_name if member else f"Unbekannt ({user_id_str})"
            entries.append(f"{idx}. {name} – {total} Punkte")

        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion leaderboard Page {page} auf."
        )
        text = "\n".join(entries)
        await interaction.response.send_message(
            f"🏆 **Top {offset+1}–{offset+len(top)}**:\n{text}"
        )
