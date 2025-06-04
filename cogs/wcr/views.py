# cogs/wcr/views.py
import discord

from log_setup import get_logger

logger = get_logger(__name__)


class MiniSelectView(discord.ui.View):
    def __init__(self, options, cog, lang) -> None:
        """View presenting a select menu of minis."""
        super().__init__(timeout=60)
        self.add_item(MiniSelect(options, cog, lang))


class MiniSelect(discord.ui.Select):
    def __init__(self, options, cog, lang) -> None:
        """Dropdown to choose a mini."""
        super().__init__(placeholder="Wähle ein Mini aus", options=options, max_values=1)
        self.cog = cog
        self.lang = lang

    async def callback(self, interaction: discord.Interaction) -> None:
        """Send the selected mini details."""
        unit_id = int(self.values[0])
        logger.info(
            f"MiniSelect: {interaction.user} chose id={unit_id} lang={self.lang}"
        )
        await interaction.response.defer(ephemeral=True)
        await self.cog.send_mini_embed(interaction, unit_id, self.lang)
