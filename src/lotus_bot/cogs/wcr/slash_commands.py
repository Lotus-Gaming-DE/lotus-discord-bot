# pragma: no cover
import discord
from discord import app_commands

from lotus_bot.log_setup import get_logger
from .cog import WCRCog

logger = get_logger(__name__)

wcr_group = app_commands.Group(
    name="wcr",
    description="Befehle für Warcraft Rumble",
)

# Autocomplete-Wrapper


async def _cost_ac(interaction, current):
    """Delegate cost autocomplete to the cog."""
    logger.debug(f"_cost_ac invoked by {interaction.user} current={current}")
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.cost_autocomplete(interaction, current)


async def _speed_ac(interaction, current):
    """Delegate speed autocomplete to the cog."""
    logger.debug(f"_speed_ac invoked by {interaction.user} current={current}")
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.speed_autocomplete(interaction, current)


async def _faction_ac(interaction, current):
    """Delegate faction autocomplete to the cog."""
    logger.debug(f"_faction_ac invoked by {interaction.user} current={current}")
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.faction_autocomplete(interaction, current)


async def _type_ac(interaction, current):
    """Delegate type autocomplete to the cog."""
    logger.debug(f"_type_ac invoked by {interaction.user} current={current}")
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.type_autocomplete(interaction, current)


async def _trait_ac(interaction, current):
    """Delegate trait autocomplete to the cog."""
    logger.debug(f"_trait_ac invoked by {interaction.user} current={current}")
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.trait_autocomplete(interaction, current)


async def _unit_name_ac(interaction, current):
    """Delegate unit name autocomplete to the cog."""
    logger.debug(f"_unit_name_ac invoked by {interaction.user} current={current}")
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    return await cog.unit_name_autocomplete(interaction, current)


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
    public="Antwort öffentlich anzeigen",
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
    public: bool = False,
):
    logger.info(
        f"/wcr filter by {interaction.user} cost={cost} speed={speed} faction={faction} type={type} trait={trait} lang={lang} public={public}"
    )
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    await cog.cmd_filter(interaction, cost, speed, faction, type, trait, lang, public)


@wcr_group.command(
    name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an."
)
@app_commands.describe(
    name="Name des Minis", lang="Sprache", public="Antwort öffentlich anzeigen"
)
async def name(
    interaction: discord.Interaction, name: str, lang: str = "de", public: bool = False
):
    logger.info(
        f"/wcr name by {interaction.user} name={name} lang={lang} public={public}"
    )
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    await cog.cmd_name(interaction, name, lang, public)


@wcr_group.command(
    name="duell",
    description="Lässt zwei Minis virtuell gegeneinander antreten.",
)
@app_commands.describe(
    mini_a="Erstes Mini (Name oder ID)",
    level_a="Level des ersten Minis (1-31, Standard 1)",
    mini_b="Zweites Mini (Name oder ID)",
    level_b="Level des zweiten Minis (1-31, Standard 1)",
    lang="Sprache",
    public="Antwort \u00f6ffentlich anzeigen",
)
@app_commands.autocomplete(mini_a=_unit_name_ac, mini_b=_unit_name_ac)
async def duell(
    interaction: discord.Interaction,
    mini_a: str,
    mini_b: str,
    level_a: app_commands.Range[int, 1, 31] = 1,
    level_b: app_commands.Range[int, 1, 31] = 1,
    lang: str = "de",
    public: bool = False,
):
    logger.info(
        f"/wcr duell by {interaction.user} a={mini_a} la={level_a} b={mini_b} lb={level_b} lang={lang} public={public}"
    )
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    await cog.cmd_duel(interaction, mini_a, mini_b, level_a, level_b, lang, public)


@wcr_group.command(name="debug", description="Zeigt geladene WCR-Daten an.")
@app_commands.checks.has_permissions(manage_guild=True)
async def debug(interaction: discord.Interaction):
    """Gibt Anzahl geladener Einheiten und Kategorien aus."""
    logger.info(f"/wcr debug by {interaction.user}")
    cog: WCRCog = interaction.client.get_cog("WCRCog")
    await cog.cmd_debug(interaction)
