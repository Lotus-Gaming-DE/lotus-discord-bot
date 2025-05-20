# cogs/tourney/cog.py

import os
import logging
from datetime import datetime

import discord
from discord import Object
from discord.ext import commands
from discord.app_commands import guilds, Choice

from .data_loader import load_tournaments, save_tournaments

logger = logging.getLogger("cogs.tourney.cog")
GUILD = Object(id=int(os.getenv("server_id")))
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
    @guilds(GUILD)
    @app_commands.choices(
        game=[
            Choice(name="Warcraft Rumble", value="Warcraft Rumble"),
            Choice(name="Magic: The Gathering", value="Magic: The Gathering"),
            Choice(name="Pokémon TCGP", value="Pokémon TCGP")
        ],
        mode=[
            Choice(name="Single Elimination",      value="Single Elimination"),
            Choice(name="Double Elimination",      value="Double Elimination"),
            Choice(name="Round Robin",             value="Round Robin"),
            Choice(name="Swiss",                   value="Swiss")
        ]
    )
    async def erstellen(
        self,
        ctx: commands.Context,
        name: str,
        game: str,
        mode: str,
        registration_closes: str,
        start_time: str
    ):
        logger.info(
            f"{ctx.author} nutzt /tourney erstellen: {name=}, {game=}, {mode=}")

        # Datum/Uhrzeit validieren
        try:
            reg_dt = datetime.strptime(registration_closes, "%Y-%m-%d %H:%M")
        except ValueError:
            logger.warning(
                f"Ungültiges registration_closes-Format: {registration_closes!r}")
            return await ctx.respond(
                "❌ Bitte gib den Anmeldeschluss im Format `YYYY-MM-DD HH:MM` an.",
                ephemeral=True
            )
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        except ValueError:
            logger.warning(f"Ungültiges start_time-Format: {start_time!r}")
            return await ctx.respond(
                "❌ Bitte gib die Startzeit im Format `YYYY-MM-DD HH:MM` an.",
                ephemeral=True
            )

        # Turnier-Daten laden und ID erzeugen
        tournaments = load_tournaments()
        tourney_id = f"tourney_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.debug(f"Erstellte Turnier-ID: {tourney_id}")

        # Neues Turnier-Objekt
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

        # Speichern
        tournaments.append(new_tourney)
        save_tournaments(tournaments)
        logger.info(f"Turnier {tourney_id!r} erstellt und gespeichert")

        # Ephemeral-Bestätigung
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
