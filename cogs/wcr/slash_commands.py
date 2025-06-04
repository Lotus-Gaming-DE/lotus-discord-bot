import discord
from discord import app_commands
from .cog import WCRCog

wcr_group = app_commands.Group(
    name="wcr",
    description="Befehle für Warcraft Rumble",
)

# Autocomplete-Wrapper


async def _cost_ac(interaction, current):
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.cost_autocomplete(interaction, current)


async def _speed_ac(interaction, current):
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.speed_autocomplete(interaction, current)


async def _faction_ac(interaction, current):
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.faction_autocomplete(interaction, current)


async def _type_ac(interaction, current):
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.type_autocomplete(interaction, current)


async def _trait_ac(interaction, current):
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.trait_autocomplete(interaction, current)


@wcr_group.command(
    name="filter", description="Filtert Minis basierend auf verschiedenen Kriterien."
)
@app_commands.describe(
    cost="Kosten des Minis",
    speed="Geschwindigkeit des Minis",
    faction="Fraktion des Minis",
    type="Typ des Minis",
    trait="Merkmal des Minis",
    lang="Sprache",
)
@app_commands.autocomplete(
    cost=_cost_ac, speed=_speed_ac, faction=_faction_ac, type=_type_ac, trait=_trait_ac
)
async def filter(
    interaction: discord.Interaction,
    cost: str = None,
    speed: str = None,
    faction: str = None,
    type: str = None,
    trait: str = None,
    lang: str = "de",
):
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    await cog.cmd_filter(interaction, cost, speed, faction, type, trait, lang)


@wcr_group.command(
    name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an."
)
@app_commands.describe(name="Name des Minis", lang="Sprache")
async def name(interaction: discord.Interaction, name: str, lang: str = "de"):
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    await cog.cmd_name(interaction, name, lang)
