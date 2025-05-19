import discord
from discord import Option
from discord.ext import commands
from .data_loader import load_tournaments, save_tournaments
from datetime import datetime

# Check: Rolle "Community Mod" ODER Administrator-Berechtigung
mod_or_admin = commands.check_any(
    commands.has_role("Community Mod"),
    commands.has_guild_permissions(administrator=True)
)

class TourneyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="tourney", description="Turnier-Verwaltung")
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
        game: Option(str, "Spiel auswählen",
                     choices=["Warcraft Rumble", "Magic: The Gathering", "Pokémon TCGP"]),
        mode: Option(str, "Modus auswählen",
                     choices=["Single Elimination", "Double Elimination", "Round Robin", "Swiss"]),
        registration_closes: Option(str, "Anmeldeschluss (YYYY-MM-DD HH:MM)"),
        start_time: Option(str, "Startzeit (YYYY-MM-DD HH:MM)")
    ):
        # Datum/Uhrzeit validieren
        try:
            reg_dt = datetime.strptime(registration_closes, "%Y-%m-%d %H:%M")
        except ValueError:
            return await ctx.respond(
                "❌ Nutz das Format `YYYY-MM-DD HH:MM`, z.B. `2025-05-20 18:00`.",
                ephemeral=True
            )
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        except ValueError:
            return await ctx.respond(
                "❌ Nutz das Format `YYYY-MM-DD HH:MM`, z.B. `2025-05-21 19:00`.",
                ephemeral=True
            )

        # Turnier anlegen
        tournaments = load_tournaments()
        tourney_id = f"tourney_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        new_tourney = {
            "id": tourney_id,
            "name": name,
            "game": game,
            "mode": mode,
            "settings": {
                "registrationCloses": reg_dt.isoformat(),
                "startTime": start_dt.isoformat()
            },
            "createdBy": str(ctx.author.id),
            "createdAt": datetime.utcnow().isoformat(),
            "status": "registration",
            "participants": [],
            "matches": [],
            "forumChannelId": None,
            "registrationMessageId": None
        }
        tournaments.append(new_tourney)
        save_tournaments(tournaments)

        # Bestätigung
        await ctx.respond(
            f"✅ Turnier **{name}** (`{tourney_id}`) erstellt!\n"
            f"• Spiel: {game}\n"
            f"• Modus: {mode}\n"
            f"• Anmeldeschluss: {reg_dt.isoformat()}\n"
            f"• Start: {start_dt.isoformat()}",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(TourneyCog(bot))
