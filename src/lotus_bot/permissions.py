from discord import app_commands, Interaction
from discord.app_commands import MissingPermissions


def owner_only():
    """Return a check ensuring only the server owner can use the command."""

    async def predicate(interaction: Interaction) -> bool:
        if (
            interaction.guild is None
            or interaction.user.id != interaction.guild.owner_id
        ):
            await interaction.response.send_message(
                "🚫 Dieser Command ist nur für den Server-Owner.", ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)


def moderator_only():
    """Return a check ensuring ``manage_guild`` and sending a message on failure."""

    base = app_commands.checks.has_permissions(manage_guild=True)
    dummy = base(lambda i: None)
    base_predicate = dummy.__discord_app_commands_checks__[0]

    async def predicate(interaction: Interaction) -> bool:
        try:
            return base_predicate(interaction)
        except MissingPermissions:
            await interaction.response.send_message(
                "❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True
            )
            return False

    return app_commands.check(predicate)
