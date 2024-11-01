# cogs/wcr/views.py
import discord


class MiniSelectView(discord.ui.View):
    def __init__(self, options, cog, lang):
        super().__init__(timeout=60)
        self.add_item(MiniSelect(options, cog, lang))


class MiniSelect(discord.ui.Select):
    def __init__(self, options, cog, lang):
        super().__init__(placeholder="Wähle ein Mini aus", options=options, max_values=1)
        self.cog = cog
        self.lang = lang

    async def callback(self, interaction: discord.Interaction):
        unit_id = int(self.values[0])
        await interaction.response.defer(ephemeral=True)
        await self.cog.send_mini_embed(interaction, unit_id, self.lang)
