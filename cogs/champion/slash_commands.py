import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger(__name__)  # z. B. 'cogs.champion.slash_commands'

champion_group = app_commands.Group(
    name="champion", description="Verwalte Champion-Punkte"
)


class ChampionCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, cog):
        self.bot = bot
        self.cog = cog

    def is_authorized(self, user: discord.Member) -> bool:
        return (
            any(role.name == "Community Mod" for role in user.roles)
            or user.guild_permissions.administrator
        )

    @champion_group.command(name="give", description="Gibt einem User Punkte (nur Mods)")
    @app_commands.describe(user="Der Nutzer", punkte="Anzahl der Punkte", grund="Warum?")
    async def give(self, interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        total = self.cog.update_user_score(user.id, punkte, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} vergibt +{punkte} an {user} ({grund})")
        await interaction.response.send_message(
            f"✅ {user.mention} hat nun insgesamt {total} Punkte.")

    @champion_group.command(name="remove", description="Entfernt Punkte (nur Mods)")
    @app_commands.describe(user="Der Nutzer", punkte="Anzahl der Punkte", grund="Warum?")
    async def remove(self, interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str):
        if not self.is_authorized(interaction.user):
            await interaction.response.send_message("❌ Du hast keine Berechtigung.", ephemeral=True)
            return

        total = self.cog.update_user_score(user.id, -punkte, grund)
        logger.info(
            f"[ChampionCommands] {interaction.user} zieht {punkte} von {user} ab ({grund})")
        await interaction.response.send_message(
            f"⚠️ {user.mention} hat nun insgesamt {total} Punkte.")

    @champion_group.command(name="info", description="Zeigt deine Punktzahl")
    async def info(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = self.cog.points.get(user_id, {"total": 0})
        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion info auf.")
        await interaction.response.send_message(
            f"🏅 Du hast aktuell {data['total']} Punkte.")

    @champion_group.command(name="history", description="Zeigt die Punkte-Historie eines Spielers")
    @app_commands.describe(user="Der Spieler")
    async def history(self, interaction: discord.Interaction, user: discord.Member):
        user_id = str(user.id)
        history = self.cog.points.get(user_id, {}).get("history", [])
        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion history für {user} auf.")

        if not history:
            await interaction.response.send_message(
                f"📭 {user.display_name} hat noch keine Historie.")
            return

        lines = [
            f"📅 {entry['date'][:10]}: {'+' if entry['delta'] > 0 else ''}{entry['delta']} – {entry['reason']}"
            for entry in history[-10:]
        ]
        await interaction.response.send_message(
            f"📜 Punkteverlauf von {user.display_name}:\n" + "\n".join(lines))

    @champion_group.command(name="leaderboard", description="Zeigt die Top 10")
    async def leaderboard(self, interaction: discord.Interaction):
        sorted_users = sorted(
            self.cog.points.items(), key=lambda x: x[1]["total"], reverse=True)
        top = sorted_users[:10]
        entries = []

        for idx, (user_id, data) in enumerate(top, 1):
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"Unbekannt ({user_id})"
            entries.append(f"{idx}. {name} – {data['total']} Punkte")

        logger.info(
            f"[ChampionCommands] {interaction.user} ruft /champion leaderboard auf.")
        await interaction.response.send_message(
            "🏆 **Top 10 Spieler**:\n" + "\n".join(entries))


async def setup(bot: commands.Bot):
    from .cog import ChampionCog
    cog = bot.get_cog("ChampionCog")
    if cog is None:
        cog = ChampionCog(bot)
        await bot.add_cog(cog)

    await bot.add_cog(ChampionCommands(bot, cog))
    logger.info("[ChampionCommands] Slash-Befehle geladen und registriert.")
