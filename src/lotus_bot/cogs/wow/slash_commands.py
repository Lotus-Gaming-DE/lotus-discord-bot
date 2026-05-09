import discord
from discord import app_commands

from lotus_bot.log_setup import get_logger
from lotus_bot.permissions import moderator_only

from .cog import WoWCog

logger = get_logger(__name__)

wow_group = app_commands.Group(
    name="wow",
    description="WoW Classic Hardcore Befehle",
)


@wow_group.command(name="setup", description="Konfiguriert den WoW-Ankündigungschannel")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(channel="Channel für WoW-Meilensteinmeldungen")
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    logger.info(f"/wow setup by {interaction.user} channel={channel.id}")
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return
    await cog.set_announcement_channel(channel.id)
    await interaction.response.send_message(
        f"✅ WoW-Ankündigungen werden in {channel.mention} gepostet.",
        ephemeral=True,
    )


@wow_group.command(name="status", description="Zeigt den WoW-Tracker Status")
async def status(interaction: discord.Interaction):
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    info = await cog.status()
    channel_id = info.get("channel_id")
    channel_text = f"<#{channel_id}>" if channel_id else "nicht konfiguriert"
    last_scan = info.get("last_scan_at") or "noch nie"
    interval_hours = int(info["poll_interval"]) // 3600
    await interaction.response.send_message(
        "\n".join(
            [
                f"Guild: **{info['guild']}**",
                f"Realm: **{info['realm']}**",
                f"Channel: {channel_text}",
                f"Letzter Scan: {last_scan}",
                f"Mitglieder im Snapshot: {info['member_count']}",
                f"Polling: alle {interval_hours} Stunden",
            ]
        ),
        ephemeral=True,
    )


@wow_group.command(name="scan", description="Prüft den WoW-Roster sofort")
@moderator_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(post="Meilensteine posten, falls welche gefunden werden")
async def scan(interaction: discord.Interaction, post: bool = True):
    logger.info(f"/wow scan by {interaction.user} post={post}")
    cog: WoWCog | None = interaction.client.get_cog("WoWCog")
    if cog is None:
        await interaction.response.send_message(
            "❌ WoW-System nicht verfügbar.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        result = await cog.scan(post=post, persist=post)
    except Exception as exc:
        logger.error("[WoWCommands] Scan failed: %s", exc, exc_info=True)
        await interaction.followup.send("❌ WoW-Scan fehlgeschlagen.")
        return

    mode = "gepostet" if post else "Dry-Run"
    await interaction.followup.send(
        f"{mode}: {result.member_count} Mitglieder geprüft, "
        f"{len(result.milestones)} Meilensteine gefunden, {result.posted} gepostet."
    )
