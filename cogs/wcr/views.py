# cogs/wcr/views.py
import discord

from log_setup import get_logger

logger = get_logger(__name__)


class MiniSelectView(discord.ui.View):
    def __init__(self, options, cog, lang) -> None:
        """View presenting a select menu of minis."""
        super().__init__(timeout=60)
        self.add_item(MiniSelect(options, cog, lang))

    async def on_timeout(self) -> None:
        """Disable the select when the view times out."""
        for child in self.children:
            child.disabled = True
        self.stop()


class MiniSelect(discord.ui.Select):
    def __init__(self, options, cog, lang) -> None:
        """Dropdown to choose a mini."""
        super().__init__(placeholder="Wähle ein Mini aus", options=options, max_values=1)
        self.cog = cog
        self.lang = lang

    async def callback(self, interaction: discord.Interaction) -> None:
        """Send the selected mini details or an error if timed out."""
        if self.view.is_finished():
            await interaction.response.send_message(
                "Auswahl nicht mehr verfügbar.", ephemeral=True
            )
            return
        unit_id = int(self.values[0])
        logger.info(
            f"MiniSelect: {interaction.user} chose id={unit_id} lang={self.lang}"
        )
        await interaction.response.defer(ephemeral=True)
        await self.cog.send_mini_embed(interaction, unit_id, self.lang)
