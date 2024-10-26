import discord
from discord import app_commands
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
        texts = self.languages.get(lang, self.languages["de"])
        unit_text = texts["units"].get(str(unit_id), {})
        return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt")

    async def send_embed(self, interaction, title, description, fields):
        embed = discord.Embed(
            title=title, description=description, color=0x3498db)
        embed.set_thumbnail(
            url="https://i.ibb.co/GdWrTKT/Lotus-Gaming.jpg")  # Beispielbild
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cost", description="Zeigt alle Minis mit den angegebenen Kosten an.")
    async def cost(self, interaction: discord.Interaction, cost: int, lang: str = "de"):
        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [unit for unit in self.units if unit["cost"] == cost]
        if not matching_units:
            await interaction.response.send_message(f"Keine Minis mit Kosten {cost} gefunden.")
            return

        fields = [(self.get_text_data(unit["id"], lang)[0], self.get_text_data(
            unit["id"], lang)[1]) for unit in matching_units]
        await self.send_embed(interaction, f"Minis mit Kosten {cost}", "Liste der Minis:", fields)

    @app_commands.command(name="faction", description="Zeigt alle Minis der angegebenen Fraktion an.")
    async def faction(self, interaction: discord.Interaction, faction_id: int, lang: str = "de"):
        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [
            unit for unit in self.units if unit["faction_id"] == faction_id]
        if not matching_units:
            await interaction.response.send_message(f"Keine Minis in Fraktion {faction_id} gefunden.")
            return

        fields = [(self.get_text_data(unit["id"], lang)[0], self.get_text_data(
            unit["id"], lang)[1]) for unit in matching_units]
        await self.send_embed(interaction, f"Minis in Fraktion {faction_id}", "Liste der Minis:", fields)

    @app_commands.command(name="type", description="Zeigt alle Minis des angegebenen Typs an.")
    async def type(self, interaction: discord.Interaction, type_id: int, lang: str = "de"):
        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [
            unit for unit in self.units if unit["type_id"] == type_id]
        if not matching_units:
            await interaction.response.send_message(f"Keine Minis mit Typ {type_id} gefunden.")
            return

        fields = [(self.get_text_data(unit["id"], lang)[0], self.get_text_data(
            unit["id"], lang)[1]) for unit in matching_units]
        await self.send_embed(interaction, f"Minis vom Typ {type_id}", "Liste der Minis:", fields)

    @app_commands.command(name="speed", description="Zeigt alle Minis der angegebenen Geschwindigkeit an.")
    async def speed(self, interaction: discord.Interaction, speed_id: int, lang: str = "de"):
        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_units = [
            unit for unit in self.units if unit["speed_id"] == speed_id]
        if not matching_units:
            await interaction.response.send_message(f"Keine Minis mit Geschwindigkeit {speed_id} gefunden.")
            return

        fields = [(self.get_text_data(unit["id"], lang)[0], self.get_text_data(
            unit["id"], lang)[1]) for unit in matching_units]
        await self.send_embed(interaction, f"Minis mit Geschwindigkeit {speed_id}", "Liste der Minis:", fields)

    @app_commands.command(name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an.")
    async def name(self, interaction: discord.Interaction, name: str, lang: str = "de"):
        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        matching_unit = None
        for unit_id, unit_data in self.languages[lang]["units"].items():
            if unit_data["name"].lower() == name.lower():
                matching_unit = next(
                    (u for u in self.units if str(u["id"]) == unit_id), None)
                break

        if not matching_unit:
            await interaction.response.send_message(f"Mini mit Namen '{name}' nicht gefunden.")
            return

        unit_name, unit_description = self.get_text_data(
            matching_unit["id"], lang)
        stats = matching_unit["stats"]
        fields = [(key.capitalize(), str(value))
                  for key, value in stats.items()]

        await self.send_embed(interaction, unit_name, unit_description, fields)


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
