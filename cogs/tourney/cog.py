import os
from discord import Object, app_commands
import discord
from discord.ext import commands
from .data_loader import load_tournaments, save_tournaments
from datetime import datetime

# Guild-Konfiguration
GUILD_ID = int(os.getenv("server_id"))
GUILD = Object(id=GUILD_ID)

# Check: Community Mod ODER Admin
mod_or_admin = commands.check_any(
    commands.has_role("Community Mod"),
    commands.has_guild_permissions(administrator=True)
)


class TourneyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(GUILD)
    @commands.hybrid_group(
        name="tourney",
        description="Turnier-Verwaltung"
    )
    @mod_or_admin
    async def tourney(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @tourney.command(
        name="erstellen",
        description="Neues Turnier anlegen"
    )
    @mod_or_admin
    async def erstellen(
        self,
        ctx: commands.Context,
        name: str,
        game: app_commands.Option(str, "Spiel auswählen",
                                  choices=["Warcraft Rumble", "Magic: The Gathering", "Pokémon TCGP"]),
        mode: app_commands.Option(str, "Modus auswählen",
                                  choices=["Single Elimination", "Double Elimination", "Round Robin", "Swiss"]),
        registration_closes: app_commands.Option(str, "Anmeldeschluss (YYYY-MM-DD HH:MM)"),
        start_time: app_commands.Option(str, "Startzeit (YYYY-MM-DD HH:MM)")
    ):
        # ... dein bisheriger Code ...
        await ctx.respond("✅ Turnier erstellt!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TourneyCog(bot))
