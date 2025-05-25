import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

champion_group = app_commands.Group(
    name="champion", description="Verwalte Champion-Punkte")


class ChampionCommands(commands.Cog):
    def __init__(self, bot, cog):
        self.bot = bot
        self.cog = cog

    @champion_group.command(name="give", description="Gibt einem User Punkte (nur Mods)")
    @app_commands.describe(user="Der Nutzer", punkte="Anzahl der Punkte", grund="Warum?")
    async def give(self, interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Du hast keine Berechtigung.", ephemeral=True)
            return

        total = self.cog.update_user_score(user.id, punkte, grund)
        await interaction.response.send_message(f"✅ {user.mention} hat nun insgesamt {total} Punkte.")

    @champion_group.command(name="remove", description="Entfernt Punkte (nur Mods)")
    @app_commands.describe(user="Der Nutzer", punkte="Anzahl der Punkte", grund="Warum?")
    async def remove(self, interaction: discord.Interaction, user: discord.Member, punkte: int, grund: str):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Du hast keine Berechtigung.", ephemeral=True)
            return

        total = self.cog.update_user_score(user.id, -punkte, grund)
        await interaction.response.send_message(f"⚠️ {user.mention} hat nun insgesamt {total} Punkte.")

    @champion_group.command(name="info", description="Zeigt deine Punktzahl")
    async def info(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = self.cog.points.get(user_id, {"total": 0})
        await interaction.response.send_message(f"🏅 Du hast aktuell {data['total']} Punkte.")

    @champion_group.command(name="history", description="Zeigt die Punkte-Historie eines Spielers")
    @app_commands.describe(user="Der Spieler")
    async def history(self, interaction: discord.Interaction, user: discord.Member):
        user_id = str(user.id)
        history = self.cog.points.get(user_id, {}).get("history", [])
        if not history:
            await interaction.response.send_message(f"📭 {user.display_name} hat noch keine Historie.")
            return

        lines = [
            f"📅 {entry['date'][:10]}: {'+' if entry['delta'] > 0 else ''}{entry['delta']} – {entry['reason']}" for entry in history[-10:]]
        await interaction.response.send_message(f"📜 Punkteverlauf von {user.display_name}:\n" + "\n".join(lines))

    @champion_group.command(name="leaderboard", description="Zeigt die Top 10")
    async def leaderboard(self, interaction: discord.Interaction):
        sorted_users = sorted(self.cog.points.items(),
                              key=lambda x: x[1]["total"], reverse=True)
        top = sorted_users[:10]
        entries = []

        for idx, (user_id, data) in enumerate(top, 1):
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"Unbekannt ({user_id})"
            entries.append(f"{idx}. {name} – {data['total']} Punkte")

        await interaction.response.send_message("🏆 **Top 10 Spieler**:\n" + "\n".join(entries))


async def setup(bot):
    from .cog import ChampionCog
    cog = bot.get_cog("ChampionCog")
    if cog is None:
        cog = ChampionCog(bot)
        await bot.add_cog(cog)
    await bot.add_cog(ChampionCommands(bot, cog))
