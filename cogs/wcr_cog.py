import discord
from discord import app_commands
from discord.ext import commands
import json


class WCRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.units = self.load_units()
        self.languages = self.load_languages()
        self.pictures = self.load_pictures()  # Lade die Bilderdaten

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

    def load_pictures(self):
        with open('./data/wcr/pictures.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_text_data(self, unit_id, lang):
        texts = self.languages.get(lang, self.languages["de"])
        unit_text = texts["units"].get(str(unit_id), {})
        return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt")

    def get_pose_url(self, unit_id):
        """Gibt die pose-URL des Minis zurück, falls vorhanden."""
        return self.pictures["units"].get(str(unit_id), {}).get("pose", "")

    async def send_embed(self, interaction, title, description, fields, image_url=None):
        embed = discord.Embed(
            title=title, description=description, color=0x3498db)
        if image_url:
            embed.set_thumbnail(url=image_url)
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
        # Beispielbild von erstem passenden Mini
        pose_url = self.get_pose_url(matching_units[0]["id"])
        await self.send_embed(interaction, f"Minis mit Kosten {cost}", "Liste der Minis:", fields, pose_url)

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
        pose_url = self.get_pose_url(matching_units[0]["id"])
        await self.send_embed(interaction, f"Minis in Fraktion {faction_id}", "Liste der Minis:", fields, pose_url)

    @app_commands.command(name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an.")
    async def name(self, interaction: discord.Interaction, name: str, lang: str = "de"):
        if lang not in self.languages:
            await interaction.response.send_message("Sprache nicht unterstützt. Verfügbar: de, en.")
            return

        # Suche nach dem Namen in der Sprachdatei
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

        pose_url = self.get_pose_url(matching_unit["id"])
        await self.send_embed(interaction, unit_name, unit_description, fields, pose_url)


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
