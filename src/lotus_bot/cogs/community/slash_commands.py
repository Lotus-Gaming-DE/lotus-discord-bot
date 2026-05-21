import discord
from discord import app_commands

from lotus_bot.log_setup import get_logger
from lotus_bot.permissions import moderator_only

from .cog import CommunityCog

logger = get_logger(__name__)

community_group = app_commands.Group(
    name="community",
    description="Community-Verwaltung",
)


@community_group.command(
    name="setup",
    description="Setzt den Channel für das Community-Info-Panel",
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(channel="Channel in dem das Info-Panel gepostet wird")
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    logger.info(f"/community setup by {interaction.user} channel={channel.id}")
    cog: CommunityCog | None = interaction.client.get_cog("CommunityCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ Community-System nicht verfügbar.", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        await cog.publish_panel(channel)
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning(
            "[CommunityCommands] Panel-Publish fehlgeschlagen: %s", exc, exc_info=True
        )
        await interaction.followup.send(
            "❌ Panel konnte nicht gepostet werden. Bitte Bot-Rechte im Channel prüfen.",
        )
        return
    await interaction.followup.send(
        f"✅ Community-Panel in {channel.mention} gepostet und gespeichert.",
    )
