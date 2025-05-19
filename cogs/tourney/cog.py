import os
import logging
from datetime import datetime

import discord
from discord import Object
from discord.ext import commands
from discord.app_commands import Option, guilds

from .data_loader import load_tournaments, save_tournaments

# Logger für das Tourney-Cog
logger = logging.getLogger("cogs.tourney.cog")

# Guild-ID aus der Env-Var
GUILD = Object(id=int(os.getenv("server_id")))

# Check: Rolle "Community Mod" ODER Administrator-Rechte
mod_or_admin = commands.check_any(
    commands.has_role("Community Mod"),
    commands.has_guild_permissions(administrator=True)
)


class TourneyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("TourneyCog initialisiert")

    @guilds(GUILD)
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
        logger.info(
            f"{ctx.author} startet /tourney erstellen: name={name}, game={game}, mode={mode}")

        # Datum/Uhrzeit validieren
        try:
            reg_dt = datetime.strptime(registration_closes, "%Y-%m-%d %H:%M")
        except ValueError:
            logger.warning(f"Ungültiges registration_closes: {
                           registration_closes!r}")
            return await ctx.respond(
                "❌ Bitte gib den Anmeldeschluss im Format `YYYY-MM-DD HH:MM` an.",
                ephemeral=True
            )

        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        except ValueError:
            logger.warning(f"Ungültiges start_time: {start_time!r}")
            return await ctx.respond(
                "❌ Bitte gib die Startzeit im Format `YYYY-MM-DD HH:MM` an.",
                ephemeral=True
            )

        # Turnier anlegen
        tournaments = load_tournaments()
        tourney_id = f"tourney_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.debug(f"Erzeugte tourney_id: {tourney_id}")

        new_tourney = {
            "id": tourney_id,
            "name": name,
            "game": game,
            "mode": mode,
            "settings": {
                "registrationCloses": reg_dt.isoformat(),
                "startTime":        start_dt.isoformat()
            },
            "createdBy":            str(ctx.author.id),
            "createdAt":            datetime.utcnow().isoformat(),
            "status":               "registration",
            "participants":         [],
            "matches":              [],
            "forumChannelId":       None,
            "registrationMessageId": None
        }

        tournaments.append(new_tourney)
        save_tournaments(tournaments)
        logger.info(f"Turnier {tourney_id!r} erstellt und gespeichert")

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
