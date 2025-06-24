import discord
from discord import app_commands

from lotusbot.log_setup import get_logger
from lotusbot.permissions import moderator_only
from .cog import PTCGPCog

logger = get_logger(__name__)

ptcgp_group = app_commands.Group(
    name="ptcgp",
    description="Verwaltet Pokémon TCG Pocket Karten",
)


@ptcgp_group.command(
    name="update", description="Aktualisiert die lokale Datenbank (nur Mods)"
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
async def update(interaction: discord.Interaction):
    logger.info(f"/ptcgp update by {interaction.user}")
    cog: PTCGPCog = interaction.client.get_cog("PTCGPCog")
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        counts = await cog.update_database()
    except Exception as e:
        await interaction.followup.send(f"❌ {e}")
        return
    await interaction.followup.send(
        f"Pokémon TCG Pocket Karten-Datenbank wurde erfolgreich aktualisiert. "
        f"Es wurden {counts.get('en', 0)} Karten auf Englisch und {counts.get('de', 0)} Karten auf Deutsch geladen."
    )


@ptcgp_group.command(name="stats", description="Zeigt die Anzahl gespeicherter Karten")
async def stats(interaction: discord.Interaction):
    logger.info(f"/ptcgp stats by {interaction.user}")
    cog: PTCGPCog = interaction.client.get_cog("PTCGPCog")
    counts = await cog.data.count_cards()
    await interaction.response.send_message(
        f"In der Datenbank sind {counts.get('en', 0)} Karten auf Englisch und {counts.get('de', 0)} Karten auf Deutsch gespeichert.",
        ephemeral=True,
    )
