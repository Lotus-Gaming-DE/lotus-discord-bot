import discord
from discord import app_commands

from lotus_bot.log_setup import get_logger
from lotus_bot.permissions import moderator_only

logger = get_logger(__name__)

duo_group = app_commands.Group(
    name="duo",
    description="Zusammen leveln – finde einen Level-Partner",
)


@duo_group.command(
    name="status", description="Zeigt deinen Duo-Status (suchst du / im Team)"
)
async def duo_status(interaction: discord.Interaction):
    cog = interaction.client.get_cog("DuoCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ Duo-System nicht verfügbar.", ephemeral=True
        )
        return
    payload = await cog._status_payload(interaction.user.id)
    await interaction.response.send_message(**payload, ephemeral=True)


@duo_group.command(
    name="publish", description="Veröffentlicht/aktualisiert den Duo-Hub (nur Mods)"
)
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
async def duo_publish(interaction: discord.Interaction):
    logger.info(f"/duo publish by {interaction.user}")
    cog = interaction.client.get_cog("DuoCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ Duo-System nicht verfügbar.", ephemeral=True
        )
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        await cog.publish_hub()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("[DuoCommands] Hub-Publish fehlgeschlagen: %s", exc, exc_info=True)
        await interaction.followup.send("❌ Hub-Publish fehlgeschlagen.")
        return
    await interaction.followup.send("✅ Duo-Hub veröffentlicht/aktualisiert.")
