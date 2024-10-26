import discord
from discord.ext import commands
import json


class WCRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.units = self.load_units()
        self.languages = self.load_languages()

    def load_units(self):
        with open('./data/wcr/units.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_languages(self):
        languages = {}
        for lang in ["de", "en"]:
            try:
                with open(f'./data/wcr/locals/{lang}.json', 'r', encoding='utf-8') as f:
                    languages[lang] = json.load(f)
            except FileNotFoundError:
                print(f"Sprachdatei {lang}.json nicht gefunden.")
        return languages

    def get_text_data(self, unit_id, lang):
        """Holt die Namen und Beschreibung basierend auf ID und Sprache."""
        texts = self.languages.get(
            lang, self.languages["de"])  # Fallback auf Deutsch
        unit_text = texts["units"].get(str(unit_id), {})
        return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt")

    @commands.group(name="wcr")
    async def wcr(self, ctx):
        """Gibt Informationen über Warcraft Rumble Minis zurück."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Verwende Unterbefehle wie `cost`, `faction`, `type`, `speed`, oder `name`.")

    @wcr.command(name="cost")
    async def cost(self, ctx, cost: int, lang: str = "de"):
        """Zeigt alle Minis mit den angegebenen Kosten an."""
        if lang not in self.languages:
            await ctx.send("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [unit for unit in self.units if unit["cost"] == cost]
        if not matching_units:
            await ctx.send(f"Keine Minis mit Kosten {cost} gefunden.")
            return

        response = f"**Minis mit Kosten {cost}**:\n"
        for unit in matching_units:
            name, description = self.get_text_data(unit["id"], lang)
            response += f"- **{name}**: {description}\n"

        await ctx.send(response)

    @wcr.command(name="faction")
    async def faction(self, ctx, faction_id: int, lang: str = "de"):
        """Zeigt alle Minis der angegebenen Fraktion an."""
        if lang not in self.languages:
            await ctx.send("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [
            unit for unit in self.units if unit["faction_id"] == faction_id]
        if not matching_units:
            await ctx.send(f"Keine Minis in Fraktion {faction_id} gefunden.")
            return

        response = f"**Minis in Fraktion {faction_id}**:\n"
        for unit in matching_units:
            name, description = self.get_text_data(unit["id"], lang)
            response += f"- **{name}**: {description}\n"

        await ctx.send(response)

    @wcr.command(name="type")
    async def type(self, ctx, type_id: int, lang: str = "de"):
        """Zeigt alle Minis des angegebenen Typs an."""
        if lang not in self.languages:
            await ctx.send("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [
            unit for unit in self.units if unit["type_id"] == type_id]
        if not matching_units:
            await ctx.send(f"Keine Minis mit Typ {type_id} gefunden.")
            return

        response = f"**Minis vom Typ {type_id}**:\n"
        for unit in matching_units:
            name, description = self.get_text_data(unit["id"], lang)
            response += f"- **{name}**: {description}\n"

        await ctx.send(response)

    @wcr.command(name="speed")
    async def speed(self, ctx, speed_id: int, lang: str = "de"):
        """Zeigt alle Minis der angegebenen Geschwindigkeit an."""
        if lang not in self.languages:
            await ctx.send("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [
            unit for unit in self.units if unit["speed_id"] == speed_id]
        if not matching_units:
            await ctx.send(f"Keine Minis mit Geschwindigkeit {speed_id} gefunden.")
            return

        response = f"**Minis mit Geschwindigkeit {speed_id}**:\n"
        for unit in matching_units:
            name, description = self.get_text_data(unit["id"], lang)
            response += f"- **{name}**: {description}\n"

        await ctx.send(response)

    @wcr.command(name="name")
    async def name(self, ctx, name: str, lang: str = "de"):
        """Zeigt Details zu einem Mini basierend auf dem Namen an."""
        if lang not in self.languages:
            await ctx.send("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        # Suche nach dem Namen in der Sprachdatei
        matching_unit = None
        for unit_id, unit_data in self.languages[lang]["units"].items():
            if unit_data["name"].lower() == name.lower():
                matching_unit = next(
                    (u for u in self.units if str(u["id"]) == unit_id), None)
                break

        if not matching_unit:
            await ctx.send(f"Mini mit Namen '{name}' nicht gefunden.")
            return

        unit_name, unit_description = self.get_text_data(
            matching_unit["id"], lang)
        response = f"**{unit_name}**\n{unit_description}\n"
        response += "Details:\n" + \
            "\n".join([f"{key.capitalize()}: {value}" for key,
                      value in matching_unit["stats"].items()])

        await ctx.send(response)


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
