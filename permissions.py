from discord import app_commands, Interaction


def moderator_only():
    async def predicate(interaction: Interaction) -> bool:
        if interaction.user.guild_permissions.manage_guild:
            return True
        await interaction.response.send_message(
            "❌ Du hast keine Berechtigung für diesen Befehl.", ephemeral=True
        )
        return False

    return app_commands.check(predicate)
