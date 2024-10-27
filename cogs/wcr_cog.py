import discord
from discord import app_commands
from discord.ext import commands
import json


class WCRCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.units = self.load_units()
        self.languages = self.load_languages()
        self.pictures = self.load_pictures()
        self.emojis = self.load_emojis()

    def load_units(self):
        try:
            with open('./data/wcr/units.json', 'r', encoding='utf-8') as f:
                print("Units erfolgreich geladen.")
                return json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden von units.json: {e}")
            return {}

    def load_languages(self):
        languages = {}
        for lang in ["de", "en"]:
            try:
                with open(f'./data/wcr/locals/{lang}.json', 'r', encoding='utf-8') as f:
                    languages[lang] = json.load(f)
                print(f"Sprachdatei für {lang} erfolgreich geladen.")
            except FileNotFoundError:
                print(f"Sprachdatei {lang}.json nicht gefunden.")
            except Exception as e:
                print(f"Fehler beim Laden der Sprachdatei {lang}: {e}")
        return languages

    def load_pictures(self):
        try:
            with open('./data/wcr/pictures.json', 'r', encoding='utf-8') as f:
                print("Pictures erfolgreich geladen.")
                return json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden von pictures.json: {e}")
            return {}

    def load_emojis(self):
        try:
            with open('./data/emojis.json', 'r', encoding='utf-8') as emoji_file:
                print("Emojis erfolgreich geladen.")
                return json.load(emoji_file)
        except Exception as e:
            print(f"Fehler beim Laden von emojis.json: {e}")
            return {}

    def get_text_data(self, unit_id, lang):
        texts = self.languages.get(lang, self.languages["de"])
        unit_text = texts["units"].get(str(unit_id), {})
        return unit_text.get("name", "Unbekannt"), unit_text.get("description", "Beschreibung fehlt")

    def get_pose_url(self, unit_id):
        """Gibt die pose-URL des Minis zurück, falls vorhanden."""
        return self.pictures["units"].get(str(unit_id), {}).get("pose", "")

    async def send_embed(self, interaction, title, description, fields, inline_fields, image_url=None):
        embed = discord.Embed(
            title=title, description=description, color=0x3498db)
        if image_url:
            embed.set_thumbnail(url=image_url)
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
        for name, value in inline_fields:
            embed.add_field(name=name, value=value, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="name", description="Zeigt Details zu einem Mini basierend auf dem Namen an.")
    async def name(self, interaction: discord.Interaction, name: str, lang: str = "de"):
        print(f"Befehl /name ausgeführt mit Name: {name} und Sprache: {lang}")

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

        # Erstelle dynamisch die Felder für vorhandene Statistiken
        fields = [
            (f"{self.emojis.get('wcr_cost', {}).get('syntax', '')
                } Kosten", str(matching_unit.get("cost", "N/A"))),
            (f"{self.emojis.get('wcr_speed', {}).get('syntax', '')
                } Geschwindigkeit", str(matching_unit.get("speed_id", "N/A"))),
        ]

        # Füge nur Statistiken hinzu, die tatsächlich einen Wert haben
        if stats.get("health"):
            fields.append((f"{self.emojis.get('wcr_health', {}).get(
                'syntax', '')} Gesundheit", str(stats["health"])))
        if stats.get("damage"):
            fields.append((f"{self.emojis.get('wcr_damage', {}).get(
                'syntax', '')} Schaden", str(stats["damage"])))
        if stats.get("dps"):
            fields.append(
                (f"{self.emojis.get('wcr_dps', {}).get('syntax', '')} DPS", str(stats["dps"])))
        if stats.get("attack_speed"):
            fields.append((f"{self.emojis.get('wcr_attack_speed', {}).get(
                'syntax', '')} Angriffsgeschwindigkeit", str(stats["attack_speed"])))
        if stats.get("range"):
            fields.append((f"{self.emojis.get('wcr_range', {}).get(
                'syntax', '')} Reichweite", str(stats["range"])))
        if stats.get("duration"):
            fields.append((f"{self.emojis.get('wcr_duration', {}).get(
                'syntax', '')} Dauer", str(stats["duration"])))

        # Inline-Felder für Talente vorbereiten
        traits_ids = matching_unit.get("traits_ids", [])
        inline_fields = []
        for trait_id in traits_ids[:3]:  # Beschränkung auf maximal 3 Talente
            trait_name, trait_description = self.get_text_data(trait_id, lang)
            inline_fields.append((trait_name, trait_description))

        # Sende das Embed
        await self.send_embed(
            interaction,
            unit_name,
            unit_description,
            fields,
            inline_fields,
            self.get_pose_url(matching_unit["id"])
        )


async def setup(bot):
    await bot.add_cog(WCRCog(bot))
